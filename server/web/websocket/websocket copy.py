import os
import time
from pathlib import Path
from typing import List, Optional
from fastapi import WebSocketDisconnect

# Web sockets
import asyncio
import shutil

# Import modules
from server.web.common import LOGGER
from server.utils.settings import AppSettings
# Windows-specific imports
if os.name == 'nt':
    try:
        from winpty import PtyProcess
    except ImportError:
        raise ImportError("Please install pywinpty: pip install pywinpty")
else:
    try:
        import termios
    except ImportError:
        raise ImportError("Must be running on a Unix-like system to use termios")

class WebSetup:
    """Class to handle PowerShell web setup with WebSocket communication"""
    
    def __init__(self):
        """
        Initialize WebSetup instance
        
        Args:
            directory: Working directory for the PowerShell process
            file: PowerShell script file to execute
            pre_commands: Commands to execute before the main script
        """
        self._process = None
        self._tasks = []
        self._input_queue = asyncio.Queue()
        self._stdin_ready_set_time = time.monotonic()
        self._stdin_ready = asyncio.Event()
        # Load all OS-dependent configuration
        self._load_os()

    @property
    def prompt(self) -> str:
        """Get the prompt symbol"""
        if self.is_windows():
            return 'PS>'
        return '$'

    @property
    def commands(self) -> List[str]:
        """Get the command list"""
        commands = []
        commands += [f"cd {self.directory}"]
        if not self.is_windows():
            commands += [f"chmod +x {self.file}"]
        commands += [f"{self.exec_path} {' '.join(self.args)}"]
        return commands

    def is_windows(self) -> bool:
        """Check if running on Windows"""
        return os.name == 'nt'
    
    def _load_os(self) -> None:
        """
        Load and configure all OS-dependent setup
        Sets self.env, self.exec_path, and self.args
        """
        # Get working directory folder
        server_path = os.getcwd()
        self.directory = Path(server_path).resolve().parent

        # Set up environment variables
        self.env = os.environ.copy()
        self.env['PYTHONIOENCODING'] = 'utf-8'
        self.env['PYTHONUTF8'] = '1'
        
        # Get shell executable path based on OS
        if self.is_windows():
            self.file = './setup.ps1'
            self.exec_path = shutil.which('powershell.exe') or shutil.which('pwsh.exe')
            # Build Windows command arguments
            self.args = ['-NoProfile', '-ExecutionPolicy', 'Bypass']
            if self.file:
                self.args.extend(['-File', self.file])
        else:
            self.file = './setup.sh'
            self.exec_path = shutil.which('bash') or shutil.which('sh')
            # Build Linux command arguments - just the filename
            self.args = [self.file] if self.file else []
        
        # Linux-only: chmod script to be executable for current user
        if not self.is_windows() and self.file:
            current_permissions = os.stat(self.file).st_mode
            os.chmod(self.file, current_permissions | os.stat.S_IXUSR)

    async def start_process(self) -> bool:
        """
        Start shell subprocess
        
        Returns:
            bool: True if process started successfully, False otherwise
        """
        
        if not self.exec_path:
            LOGGER.error("Shell executable not found")
            return False
        
        # Start process with configured environment, executable, and args
        self._process = await asyncio.create_subprocess_exec(
            self.exec_path,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.directory if self.directory else None,
            env=self.env
        )
        
        LOGGER.debug(f"✅ Process created with PID: {self._process.pid}")
        return True
    
    async def _read_stdout(self, websocket):
        """Read from stdout and send to WebSocket"""
        try:
            while True:
                self._stdin_ready_set_time = time.monotonic()
                self._stdin_ready.set()
                line = await self._process.stdout.readline()
                self._stdin_ready.clear()
                if not line:
                    LOGGER.debug("stdout: End of stream")
                    break
                try:
                    decoded_line = line.decode('utf-8', errors='replace').rstrip('\n')
                    if decoded_line is not None:
                        LOGGER.debug(f"📤 Sending output: {decoded_line}")
                        await websocket.send_json({
                            "type": "output",
                            "message": decoded_line
                        })
                except Exception as e:
                    LOGGER.error(f"Error decoding stdout: {e}")
        except Exception as e:
            LOGGER.error(f"Error in read_stdout: {e}")
    
    async def _read_stderr(self, websocket):
        """Read from stderr and send to WebSocket"""
        try:
            while True:
                self._stdin_ready.set()
                self._stdin_ready_set_time = time.monotonic()
                line = await self._process.stderr.readline()
                self._stdin_ready.clear()
                if not line:
                    LOGGER.debug("stderr: End of stream")
                    break
                try:
                    decoded_line = line.decode('utf-8', errors='replace').rstrip('\n')
                    if decoded_line:
                        LOGGER.debug(f"📤 Sending stderr: {decoded_line}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"[STDERR] {decoded_line}"
                        })
                except Exception as e:
                    LOGGER.error(f"Error decoding stderr: {e}")
        except Exception as e:
            LOGGER.error(f"Error in read_stderr: {e}")
    
    async def _stdin_writer(self, text: Optional[str] = None):
        """Write text to stdin with proper formatting"""
        await asyncio.sleep(2)
        # self._process.stdin.write('\r\n'.encode('utf-8'))
        await self._process.stdin.drain()
        while self._process.returncode is None:
            try:
                # Get next queued value
                text = await self._input_queue.get()
                # Wait until stdout prints, then check again in 1 second to see if its ready
                while True:
                    await self._stdin_ready.wait()
                    ready_timestamp = self._stdin_ready_set_time
                    sleep_time = 1 + max(0, 1 - (time.monotonic() - ready_timestamp))
                    LOGGER.debug(f"time.monotonic()={time.monotonic()}, ready_timestamp={ready_timestamp}, sleep_time={sleep_time}")
                    # Sleep at least 1 second to allow stdout to print
                    await asyncio.sleep(sleep_time)
                    # Ensure the timestamp didn't update while sleeping
                    if (self._stdin_ready.is_set() and self._stdin_ready_set_time == ready_timestamp):
                        break

                try:
                    LOGGER.debug(f"Incoming raw text: {repr(text)}")
                    stripped_text = text.strip('\r\n\f')
                    bytes_data = stripped_text.encode("utf-8")
                    nl = '\n'.encode('utf-8')
                    fn = '\n\f'.encode('utf-8')

                    self._process.stdin.write(nl)
                    self._process.stdin.write(bytes_data)
                    self._process.stdin.write(nl)
                    await self._process.stdin.drain()
                    await asyncio.sleep(.5)
                    await self._process.stdin.drain()
                finally:
                    self._input_queue.task_done()

            except asyncio.CancelledError:
                break

            except Exception as e:
                LOGGER.error(f"Error writing stdin: {e}")
        return

    async def _handle_input(self, websocket):
        """Handle user input from WebSocket"""
        try:
            while self._process.returncode is None:
                try:
                    # Wait for input from the WebSocket
                    text = await websocket.receive_text()

                    LOGGER.debug(f"📥 Input queued: {text}")
                    await self._input_queue.put(text)
                    
                except WebSocketDisconnect:
                    LOGGER.debug("WebSocket disconnected")
                    break
                except Exception as e:
                    LOGGER.error(f"Error in handle_input: {e}")
                    break
        except Exception as e:
            LOGGER.error(f"Error in handle_input: {e}")
    
    async def cleanup(self):
        """Clean up resources"""
        # Cancel tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close process
        if self._process:
            try:
                self._process.terminate()
                await self._process.wait()
            except:
                pass
    
    async def run_websocket_handler(self, websocket):
        """
        Main WebSocket handler
        
        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        
        try:
            # Send initial connection messages
            await websocket.send_json({
                "type": "system",
                "message": "✅ Connected to PowerShell session"
            })
            
            if self.directory:
                await websocket.send_json({
                    "type": "system",
                    "message": f"📁 Working directory: {self.directory}"
                })
            
            await websocket.send_json({
                "type": "system",
                "message": "💡 Interactive terminal ready for input."
            })
            await websocket.send_json({
                "type": "system",
                "message": "━"*80
            })
            
            LOGGER.info(f"📄 Running script: {self.file}")
            LOGGER.info(f"🔧 Starting PowerShell in: {self.directory}")
            
            # Start process
            if not await self.start_process():
                await websocket.send_json({
                    "type": "error",
                    "message": "PowerShell executable not found" if self.is_windows() else "Shell executable not found."
                })
                return
            
            # Create and run tasks
            self._tasks = [
                asyncio.create_task(self._read_stdout(websocket)),
                asyncio.create_task(self._read_stderr(websocket)),
                asyncio.create_task(self._handle_input(websocket)),
                asyncio.create_task(self._stdin_writer(websocket)),
            ]
            
            # Wait for process to exit
            return_code = await self._process.wait()
            LOGGER.debug(f"✅ Process completed with exit code: {return_code}")
            
            # Send exit code
            await websocket.send_json({
                "type": "exit",
                "code": return_code
            })
            
            LOGGER.debug(f"✅ Setup command completed with exit code: {return_code}")

            # Force reload the new configuration after the setup is complete
            LOGGER.info("🔄 Reloading configuration after setup")
            AppSettings(filename='settings.yaml').load()
            
        except WebSocketDisconnect:
            LOGGER.debug("WebSocket disconnected")
        except Exception as e:
            LOGGER.error(f"❌ Error in WebSocket setup: {e}")
            import traceback
            LOGGER.error(f"Traceback: {traceback.format_exc()}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error: {str(e)}"
                })
            except:
                pass
        finally:
            await self.cleanup()
            try:
                await websocket.close()
            except:
                pass