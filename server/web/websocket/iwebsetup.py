from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import json
import re
import asyncio
import signal
from contextlib import suppress
from fastapi import WebSocketDisconnect

from server.web.common import LOGGER
from server.utils.settings import AppSettings


@dataclass
class OSConfig:
    is_windows: bool
    directory: str
    file: str
    exec_path: str
    shell_name: str
    prompt: str
    newline: str
    env: Dict[str, str] = field(default_factory=dict)
    args: List[str] = field(default_factory=list)
    on_preload: Optional[Callable[[], bool]] = None
    preload_script: Optional[str] = None
    terminal_encoding: str = 'utf-8'


class IWebSetup:
    """Interface for WebSetup implementations"""
    
    def __init__(self, os_config: OSConfig):
        self.os_config = os_config
        
        # Common instance attributes
        self._process = None
        self._tasks = []
        self._read_buffer = ''
        self._process_running = False
        self._websocket = None
        self._input_queue = asyncio.Queue()
        self._shutdown_event = asyncio.Event()
        self._seen_initial_vt = False

    @property
    def nl(self):
        return self.os_config.newline

    @abstractmethod
    async def start_process(self) -> bool:
        """Start the OS-specific subprocess"""
        pass

    @abstractmethod
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C signal"""
        pass

    @abstractmethod
    async def _read_output(self):
        """Read from process output and send to WebSocket"""
        pass

    @abstractmethod
    async def _stdin_writer(self):
        """Write text to stdin"""
        pass

    @abstractmethod
    async def cleanup(self):
        """Clean up resources - OS-specific cleanup"""
        pass

    @abstractmethod
    def _is_process_alive(self) -> bool:
        """Check if process is still alive"""
        pass

    @abstractmethod
    def _send_interrupt_to_process(self):
        """Send interrupt signal to the process"""
        pass

    @abstractmethod
    def _get_process_exit_code(self) -> int:
        """Get the process exit code"""
        pass

    @abstractmethod
    def _kill_process(self):
        """Force kill the process"""
        pass

    async def _common_cleanup(self):
        """Common cleanup operations - called by child classes"""
        LOGGER.debug("Running common cleanup...")
        self._shutdown_event.set()
        self._process_running = False

        # Cancel all running tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        
        self._read_buffer = ''
        LOGGER.debug("Common cleanup complete.")

    async def _process_output_data(self, data: str):
        """Process output data and send to WebSocket"""
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

        # Strip all terminal initialization/control sequences once
        if not self._seen_initial_vt:
            data = VT_ESCAPE.sub('', data)
            if data.strip():
                self._seen_initial_vt = True
        
        # Remove ANSI escape sequences
        clean_line = LINE_ESCAPE.sub('', data)
        encoded_line = clean_line.encode(self.os_config.terminal_encoding, errors="replace").decode("utf-8", errors="replace")
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

    async def _handle_input(self):
        """Handle user input from WebSocket"""
        try:
            while not self._shutdown_event.is_set():
                if not self._process or not self._is_process_alive():
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
                                self._send_interrupt_to_process()
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

    async def _send_initial_messages(self):
        """Send initial connection messages to WebSocket"""
        await self._websocket.send_json({
            "type": "system",
            "message": f"✅ Connected to {self.os_config.shell_name} session"
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

    async def _run_preload_script(self):
        """Run the preload script if defined"""
        if self.os_config.on_preload:
            LOGGER.info("🔄 Running preload script...")
            try:
                import inspect
                if inspect.iscoroutinefunction(self.os_config.on_preload):
                    result = await self.os_config.on_preload()
                else:
                    result = self.os_config.on_preload()
                
                if result is False:
                    LOGGER.warning("Preload script returned False, proceeding anyway...")
                else:
                    LOGGER.debug("✅ Preload script completed successfully")
            except Exception as e:
                LOGGER.error(f"❌ Error in preload script: {e}")

    async def _handle_process_completion(self, return_code: int):
        """Handle process completion"""
        LOGGER.debug(f"✅ Process completed with exit code: {return_code}")
        try:
            await self._websocket.send_json({
                "type": "exit",
                "code": return_code
            })
        except Exception:
            pass
        
        LOGGER.debug(f"✅ Setup command completed with exit code: {return_code}")

        if return_code == 0:
            LOGGER.info("🔄 Reloading configuration after setup")
            AppSettings(filename='settings.yaml').load()

    async def run(self, websocket):
        """
        Main WebSocket handler
        """
        self._websocket = websocket
        await self._websocket.accept()
        
        # Set up signal handler for Ctrl+C
        original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            # Send initial connection messages
            await self._send_initial_messages()
            
            shell_name = "PowerShell" if self.os_config.is_windows else "bash"
            LOGGER.info(f"📄 Running script: {self.os_config.file}")
            LOGGER.info(f"🔧 Starting {shell_name} in: {self.os_config.directory}")
            
            # Run preload script if defined
            await self._run_preload_script()
            
            # Start process
            if not await self.start_process():
                shell_name = "PowerShell" if self.os_config.is_windows else "bash"
                await self._websocket.send_json({
                    "type": "error",
                    "message": f"{shell_name} executable not found"
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
            
            # Handle process completion
            if self._process:
                return_code = self._get_process_exit_code()
                await self._handle_process_completion(return_code)
            
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