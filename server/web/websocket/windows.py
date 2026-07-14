import asyncio
from contextlib import suppress
import errno

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
        super().__init__(os_config)
        self._process = None  # Explicitly typed for Windows

    # -------------------------------------------------------------------------
    # Process Lifecycle Methods (Required by IWebSetup)
    # -------------------------------------------------------------------------
    def _is_process_alive(self) -> bool:
        """Check if winpty process is still alive."""
        return self._process is not None and self._process.isalive()

    def _send_interrupt_to_process(self):
        """Send Ctrl+C to the winpty process."""
        if self._is_process_alive():
            try:
                self._process.write('\x03')
                LOGGER.info("✅ Sent Ctrl+C to PowerShell")
            except Exception as e:
                LOGGER.error(f"Error sending Ctrl+C: {e}")

    def _get_process_exit_code(self) -> int:
        """Get the winpty process exit code."""
        return getattr(self._process, 'exitstatus', 0)

    def _kill_process(self):
        """Force kill the winpty process."""
        if self._is_process_alive():
            try:
                self._process.kill()
            except Exception as e:
                LOGGER.error(f"Error killing process: {e}")

    async def start_process(self) -> bool:
        """Start PowerShell subprocess using winpty."""
        if not self.os_config.exec_path:
            LOGGER.error("PowerShell executable not found")
            return False
        
        try:
            self._process = PtyProcess.spawn(
                [self.os_config.exec_path] + self.os_config.args,
                cwd=str(self.os_config.directory) if self.os_config.directory else None,
                env=self.os_config.env,
                dimensions=(24, 80)
            )
            
            self._process_running = True
            LOGGER.debug(f"✅ Process created with PID: {self._process.pid}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to start PowerShell: {e}")
            return False

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C signal."""
        LOGGER.info("🔴 Ctrl+C received, stopping PowerShell process...")
        self._send_interrupt_to_process()
        self._shutdown_event.set()
        self._process_running = False

    # -------------------------------------------------------------------------
    # I/O Methods (Required by IWebSetup)
    # -------------------------------------------------------------------------
    async def _read_output(self):
        """Read from winpty output and send to WebSocket."""
        try:
            while not self._shutdown_event.is_set() and self._is_process_alive():
                data = await asyncio.to_thread(self._process.read)
                
                if data:
                    await self._process_output_data(data)
                else:
                    await asyncio.sleep(0.01)
                    
        except asyncio.CancelledError:
            LOGGER.debug("Output reader task was cancelled.")
        except OSError as e:
            if e.errno == errno.EIO:
                LOGGER.debug("PTY closed (I/O error), stopping output reader.")
            else:
                LOGGER.error(f"OS error in _read_output: {e}")
        except Exception as e:
            if "EOF" in str(e) or "closed" in str(e).lower():
                LOGGER.debug("Output stream ended.")
            else:
                LOGGER.error(f"Error in _read_output: {e}")
        finally:
            self._process_running = False
            self._shutdown_event.set()

    async def _stdin_writer(self):
        """Write text to stdin using winpty."""
        await asyncio.sleep(2)  # Wait for PowerShell to initialize
        
        while not self._shutdown_event.is_set() and self._is_process_alive():
            try:
                text = await asyncio.wait_for(self._input_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            
            await self._send_echo(text)
            await self._write_to_process(text)
            self._input_queue.task_done()
        
        LOGGER.debug("Stdin writer finished")
        self._shutdown_event.set()

    # -------------------------------------------------------------------------
    # Helper Methods (Windows-specific)
    # -------------------------------------------------------------------------
    async def _send_echo(self, text: str):
        """Send echo back to frontend."""
        if self._websocket:
            await self._safe_send_json({
                "type": "echo",
                "message": text
            })

    async def _write_to_process(self, text: str):
        """Write text to the winpty process."""
        try:
            LOGGER.debug(f"Incoming raw text: {repr(text)}")
            stripped_text = text.strip(self.nl)
            LOGGER.debug(f"Processed text: {repr(stripped_text)}")
            
            if stripped_text:
                self._process.write(stripped_text)
                self._process.write(self.nl)  # CRLF for Windows
            else:
                self._process.write(self.nl)  # Empty command
            
            await asyncio.sleep(0.1)  # Allow processing
            
        except Exception as e:
            LOGGER.error(f"Error writing to winpty: {e}")

    def _is_eof_error(self, e: Exception) -> bool:
        """Check if exception indicates EOF or closed stream."""
        error_str = str(e).lower()
        return "eof" in error_str or "closed" in error_str

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------
    async def cleanup(self):
        """Clean up Windows-specific resources."""
        await super().cleanup()
        
        if not self._process:
            return
        
        try:
            if self._process.isalive():
                self._process.terminate()
                await asyncio.sleep(1)
                
                if self._process.isalive():
                    self._kill_process()
        except Exception as e:
            LOGGER.error(f"Error during process cleanup: {e}")
        finally:
            self._process = None