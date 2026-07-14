# windows.py
import asyncio
from contextlib import suppress

# Windows-specific imports
try:
    from winpty import PtyProcess
except ImportError:
    raise ImportError("Please install pywinpty: pip install pywinpty")

# Import modules
from server.web.common import LOGGER
from server.web.websocket.iwebsetup import IWebSetup, OSConfig


class WebSetupWindows(IWebSetup):
    """Class to handle PowerShell web setup with WebSocket communication"""
    
    def __init__(self, os_config: OSConfig):
        """
        Initialize WebSetup instance.
        Sets instance attributes from the already-loaded class config.
        """
        # Call parent __init__
        super().__init__(os_config)
        # No Windows-specific instance attributes needed beyond what's in parent

    def _is_process_alive(self) -> bool:
        """Check if winpty process is still alive"""
        return self._process is not None and self._process.isalive()

    def _send_interrupt_to_process(self):
        """Send Ctrl+C to the winpty process"""
        if self._process and self._process.isalive():
            try:
                self._process.write('\x03')
                LOGGER.info("✅ Sent Ctrl+C to PowerShell")
            except Exception as e:
                LOGGER.error(f"Error sending Ctrl+C: {e}")

    def _get_process_exit_code(self) -> int:
        """Get the winpty process exit code"""
        return self._process.exitstatus if hasattr(self._process, 'exitstatus') else 0

    def _kill_process(self):
        """Force kill the winpty process"""
        if self._process and self._process.isalive():
            try:
                self._process.kill()
            except Exception as e:
                LOGGER.error(f"Error killing process: {e}")

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
        self._send_interrupt_to_process()
        # Set shutdown event to break out of loops
        self._shutdown_event.set()
        self._process_running = False

    async def _read_output(self):
        """
        Read from winpty output and send to WebSocket.
        Winpty combines stdout and stderr, so we read from the same stream.
        """
        try:
            while not self._shutdown_event.is_set():
                # Check if process is still alive
                if not self._is_process_alive():
                    LOGGER.debug("Process is no longer alive, stopping output reader.")
                    break

                try:
                    # Read from winpty - returns string directly
                    # Using asyncio.to_thread to make it non-blocking
                    data = await asyncio.to_thread(self._process.read)

                    if data:
                        # Process the output data using the base class method
                        # Note: Windows uses windows-1252 encoding
                        # We'll handle the encoding in the base class method
                        await self._process_output_data(data)
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
            if not self._is_process_alive():
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

    async def cleanup(self):
        """Clean up Windows-specific resources"""
        # Call the common cleanup first
        await self._common_cleanup()
        
        # Now do Windows-specific cleanup
        if self._process:
            try:
                if self._process.isalive():
                    self._process.terminate()
                    await asyncio.sleep(1)
                    if self._process.isalive():
                        self._kill_process()
            except Exception as e:
                LOGGER.error(f"Error during process cleanup: {e}")
            self._process = None