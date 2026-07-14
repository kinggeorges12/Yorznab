# windows.py
import json
import re
from fastapi import WebSocketDisconnect
from contextlib import suppress

# Web sockets
import signal
import asyncio

# Windows-specific imports
try:
    from winpty import PtyProcess
except ImportError:
    raise ImportError("Please install pywinpty: pip install pywinpty")

# Import modules
from server.web.common import LOGGER
from server.utils.settings import AppSettings
from server.web.websocket.iwebsetup import IWebSetup, OSConfig

class WebSetupWindows(IWebSetup):
    """Class to handle PowerShell web setup with WebSocket communication"""
    
    def __init__(self, os_config: OSConfig):
        """
        Initialize WebSetup instance.
        Sets instance attributes from the already-loaded class config.
        """
        # Call parent __init__ FIRST
        super().__init__(os_config)

        # Instance-specific attributes
        self._process = None
        self._tasks = []
        self._read_buffer = ''
        self._process_running = False
        self._websocket = None
        self._input_queue = asyncio.Queue()
        self._shutdown_event = asyncio.Event()

    async def start_process(self) -> bool:
        """
        Start PowerShell subprocess using winpty
        
        Returns:
            bool: True if process started successfully, False otherwise
        """
        
        if not self.os_config.exec_path:
            LOGGER.error("PowerShell executable not found")
            return False
        
        try:
            # Start PowerShell with winpty for proper pseudo-terminal support
            self._process = PtyProcess.spawn(
                [self.os_config.exec_path] + self.os_config.args,
                cwd=str(self.os_config.directory) if self.os_config.directory else None,
                env=self.os_config.env,
                dimensions=(24, 80)  # Set initial terminal dimensions
            )
            
            self._process_running = True
            LOGGER.debug(f"✅ Process created with PID: {self._process.pid}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to start PowerShell: {e}")
            return False
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C signal"""
        LOGGER.info("🔴 Ctrl+C received, stopping PowerShell process...")
        if self._process and self._process.isalive():
            try:
                # Send Ctrl+C to the winpty process
                self._process.write('\x03')
                LOGGER.info("✅ Sent Ctrl+C to PowerShell")
            except Exception as e:
                LOGGER.error(f"Error sending Ctrl+C: {e}")
        # Set shutdown event to break out of loops
        self._shutdown_event.set()
        self._process_running = False
    
    async def _read_output(self):
        """
        Read from winpty output and send to WebSocket.
        Winpty combines stdout and stderr, so we read from the same stream.
        """

        self._seen_initial_vt = False  # Flag to track if we've seen initial VT sequences
        VT_ESCAPE = re.compile(
            r"""
            \x1B
            (?:
                \[[0-?]*[ -/]*[@-~]      # CSI sequences: ESC[...letter
                |
                \][^\x07]*(?:\x07|\x1B\\) # OSC sequences
                |
                [@-_]                     # Single ESC commands
            )
            """,
            re.VERBOSE
        )
        RESET_CODES = re.compile(r'(?:\x1b\[0m)+')
        CURSOR_POSITIONS = re.compile(r'\x1b\[(\d+);(\d+)H')
        LINE_ESCAPE = re.compile(f'(?:{RESET_CODES.pattern})|(?:{CURSOR_POSITIONS.pattern})')
        VT_NL = '\n'

        try:
            while not self._shutdown_event.is_set():
                # Check if process is still alive
                if not self._process or not self._process.isalive():
                    LOGGER.debug("Process is no longer alive, stopping output reader.")
                    break

                try:
                    # Read from winpty - returns string directly
                    # Using asyncio.to_thread to make it non-blocking
                    data = await asyncio.to_thread(self._process.read)

                    if data:

                        # Strip all terminal initialization/control sequences once
                        if not self._seen_initial_vt:
                            data = VT_ESCAPE.sub('', data)
                            # Once we have actual printable output, stop startup stripping
                            if data.strip():
                                self._seen_initial_vt = True
                        
                        # Remove ANSI escape sequences
                        clean_line = LINE_ESCAPE.sub('', data)
                        encoded_line = clean_line.encode("windows-1252", errors="replace").decode("utf-8", errors="replace")
                        self._read_buffer += encoded_line
                        
                        # Process complete lines
                        while VT_NL in self._read_buffer:
                            line, self._read_buffer = self._read_buffer.split(VT_NL, 1)
                            if self._websocket:
                                try:
                                    LOGGER.debug(f"📤 Sending output: {line}")
                                    await self._websocket.send_json({
                                        "type": "output",
                                        "message": line
                                    })
                                except Exception as e:
                                    LOGGER.error(f"Failed to send WebSocket message: {e}")
                                    self._shutdown_event.set()
                                    return
                    else:
                        # No data available, small delay to prevent busy loop
                        await asyncio.sleep(0.01)
                        
                except Exception as e:
                    if "EOF" in str(e) or "closed" in str(e).lower():
                        LOGGER.debug("Output stream: End of stream")
                        break
                    LOGGER.error(f"Error reading from winpty: {e}")
                    await asyncio.sleep(0.1)
                    
        except asyncio.CancelledError:
            LOGGER.debug("Output reader task was cancelled.")
        except Exception as e:
            LOGGER.error(f"Error in _read_output: {e}")
        finally:
            self._process_running = False
            self._shutdown_event.set()
    
    async def _stdin_writer(self):
        """Write text to stdin using winpty"""
        await asyncio.sleep(2)  # Wait for PowerShell to initialize
        
        while not self._shutdown_event.is_set():
            if not self._process or not self._process.isalive():
                break

            try:
                # Get next queued value with timeout to check for shutdown
                try:
                    text = await asyncio.wait_for(self._input_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                
                # Send echo back to frontend to acknowledge receipt
                if self._websocket:
                    try:
                        await self._websocket.send_json({
                            "type": "echo",
                            "message": text
                        })
                    except Exception as e:
                        LOGGER.error(f"Failed to send echo: {e}")

                try:
                    LOGGER.debug(f"Incoming raw text: {repr(text)}")
                    
                    # Just strip newlines and carriage returns
                    stripped_text = text.strip(self.nl)
                    
                    LOGGER.debug(f"Processed text: {repr(stripped_text)}")
                    
                    # Write to winpty - just the command plus newline
                    if stripped_text:
                        self._process.write(stripped_text)
                        self._process.write(self.nl)  # Use CRLF for Windows
                    else:
                        # Empty command - just send newline
                        self._process.write(self.nl)
                    
                    # Small delay to allow processing
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    LOGGER.error(f"Error writing to winpty: {e}")
                finally:
                    self._input_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                LOGGER.error(f"Error in _stdin_writer: {e}")
                await asyncio.sleep(0.1)
        
        LOGGER.debug("Stdin writer finished")
        self._shutdown_event.set()
        
    async def _handle_input(self):
        """Handle user input from WebSocket"""
        try:
            while not self._shutdown_event.is_set():
                if not self._process or not self._process.isalive():
                    break
                    
                try:
                    # Wait for input from the WebSocket with timeout
                    try:
                        data = await asyncio.wait_for(self._websocket.receive_text(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    
                    # Parse JSON message
                    try:
                        json_data = json.loads(data)
                        if json_data.get('type') == 'input':
                            text = json_data.get('message', '')
                            LOGGER.debug(f"📥 Input received: {text}")
                            
                            # Handle Ctrl+C from frontend
                            if text == '\x03' or text == 'Ctrl+C':
                                LOGGER.debug("🔴 Ctrl+C detected from frontend, sending interrupt")
                                if self._process and self._process.isalive():
                                    self._process.write('\x03')
                                continue
                            
                            await self._input_queue.put(text)
                        elif json_data.get('type') == 'ready':
                            LOGGER.debug("🟢 Client ready message received")
                            continue
                    except json.JSONDecodeError:
                        # Fallback for plain text messages
                        text = data
                        LOGGER.debug(f"📥 Input received (plain text): {text}")
                        await self._input_queue.put(text)
                    
                except WebSocketDisconnect:
                    LOGGER.debug("WebSocket disconnected")
                    break
                except Exception as e:
                    LOGGER.error(f"Error in handle_input: {e}")
                    break
        except asyncio.CancelledError:
            LOGGER.debug("_handle_input task was cancelled.")
        except Exception as e:
            LOGGER.error(f"Error in _handle_input: {e}")
        finally:
            self._shutdown_event.set()
    
    async def cleanup(self):
        """Clean up resources"""
        LOGGER.debug("Running cleanup...")
        # Set shutdown event to signal all tasks to stop
        self._shutdown_event.set()
        self._process_running = False

        # Cancel all running tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        
        # Close the winpty process
        if self._process:
            try:
                if self._process.isalive():
                    self._process.terminate()
                    await asyncio.sleep(1)
                    if self._process.isalive():
                        self._process.kill()
            except Exception as e:
                LOGGER.error(f"Error during process cleanup: {e}")
            self._process = None
        
        self._read_buffer = ''
        LOGGER.debug("Cleanup complete.")
    
    async def run(self, websocket):
        """
        Main WebSocket handler
        
        Args:
            websocket: WebSocket connection
        """
        self._websocket = websocket
        await self._websocket.accept()
        
        # Set up signal handler for Ctrl+C
        original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            # Send initial connection messages
            await self._websocket.send_json({
                "type": "system",
                "message": "✅ Connected to PowerShell session"
            })
            
            if self.os_config.directory:
                await self._websocket.send_json({
                    "type": "system",
                    "message": f"📁 Working directory: {self.os_config.directory}"
                })
            
            await self._websocket.send_json({
                "type": "system",
                "message": "💡 Interactive terminal loading..."
            })
            await self._websocket.send_json({
                "type": "system",
                "message": "━"*80
            })
            await self._websocket.send_json({
                "type": "system",
                "message": ""
            })
            
            LOGGER.info(f"📄 Running script: {self.os_config.file}")
            LOGGER.info(f"🔧 Starting PowerShell in: {self.os_config.directory}")
            
            # Start process
            if not await self.start_process():
                await self._websocket.send_json({
                    "type": "error",
                    "message": "PowerShell executable not found"
                })
                return
            
            # Create and run tasks
            self._tasks = [
                asyncio.create_task(self._read_output()),
                asyncio.create_task(self._handle_input()),
                asyncio.create_task(self._stdin_writer()),
            ]
            
            # Wait for shutdown event (triggered by disconnect or process exit)
            await self._shutdown_event.wait()
            
            # Send exit code if process is still around
            if self._process:
                return_code = self._process.exitstatus if hasattr(self._process, 'exitstatus') else 0
                LOGGER.debug(f"✅ Process completed with exit code: {return_code}")
                try:
                    await self._websocket.send_json({
                        "type": "exit",
                        "code": return_code
                    })
                except Exception:
                    pass
                
                LOGGER.debug(f"✅ Setup command completed with exit code: {return_code}")

                # Force reload the new configuration after the setup is complete
                if return_code == 0:
                    LOGGER.info("🔄 Reloading configuration after setup")
                    AppSettings(filename='settings.yaml').load()
            
        except WebSocketDisconnect:
            LOGGER.debug("WebSocket disconnected")
        except Exception as e:
            LOGGER.error(f"❌ Error in WebSocket setup: {e}")
            import traceback
            LOGGER.error(f"Traceback: {traceback.format_exc()}")
            try:
                await self._websocket.send_json({
                    "type": "error",
                    "message": f"Error: {str(e)}"
                })
            except:
                pass
        finally:
            # Restore original signal handler
            signal.signal(signal.SIGINT, original_sigint_handler)
            await self.cleanup()
            try:
                await self._websocket.close()
            except:
                pass