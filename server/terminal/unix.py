import os
import signal
import asyncio
import pty
import subprocess
import errno

# Import modules
from server.web.common import LOGGER
from server.terminal.iwebsetup import IWebSetup, OSConfig


class WebSetupUnix(IWebSetup):
    """Class to handle bash web setup with WebSocket communication"""
    
    def __init__(self, os_config: OSConfig):
        super().__init__(os_config)
        self._pty_controller_fd = None

    # -------------------------------------------------------------------------
    # Process Lifecycle Methods (Required by IWebSetup)
    # -------------------------------------------------------------------------
    def _is_process_alive(self) -> bool:
        """Check if process is still alive."""
        return self._process is not None and self._process.poll() is None

    def _send_interrupt_to_process(self):
        """Send Ctrl+C to the process."""
        if self._is_process_alive():
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGINT)
                LOGGER.info("✅ Sent SIGINT to process")
            except Exception as e:
                LOGGER.error(f"Error sending Ctrl+C: {e}")

    def _get_process_exit_code(self) -> int:
        """Get the process exit code."""
        return_code = self._process.poll()
        return return_code if return_code is not None else 0

    def _kill_process(self):
        """Force kill the process."""
        if self._is_process_alive():
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                LOGGER.info(f"✅ Force killed process {self._process.pid}")
            except Exception as e:
                LOGGER.error(f"Error killing process: {e}")

    async def start_process(self) -> bool:
        """Start bash subprocess with PTY."""
        if not self.os_config.exec_path:
            LOGGER.error("Bash executable not found")
            return False
        
        try:
            self._pty_controller_fd, terminal_fd = pty.openpty()
            
            self._process = subprocess.Popen(
                [self.os_config.exec_path] + self.os_config.args,
                cwd=str(self.os_config.directory) if self.os_config.directory else None,
                env=self.os_config.env,
                stdin=terminal_fd,
                stdout=terminal_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
                close_fds=True
            )
            
            os.close(terminal_fd)
            self._process_running = True
            LOGGER.debug(f"✅ Process created with PID: {self._process.pid}")
            return True
            
        except Exception as e:
            LOGGER.error(f"Failed to start bash: {e}")
            return False

    # -------------------------------------------------------------------------
    # PTY Helpers
    # -------------------------------------------------------------------------
    def _read_from_pty(self) -> str:
        """Read data from PTY controller."""
        try:
            data = os.read(self._pty_controller_fd, 4096)
            return data.decode('utf-8', errors='replace') if data else ''
        except OSError as e:
            if e.errno == errno.EBADF:
                return ''  # PTY already closed
            raise

    def _write_to_pty(self, text: str):
        """Write data to PTY controller."""
        try:
            os.write(self._pty_controller_fd, text.encode('utf-8'))
        except OSError as e:
            LOGGER.error(f"Error writing to pty: {e}")

    def _close_pty(self):
        """Close PTY controller file descriptor."""
        if self._pty_controller_fd:
            try:
                os.close(self._pty_controller_fd)
            except Exception:
                pass
            self._pty_controller_fd = None

    def _is_eof_error(self, e: Exception) -> bool:
        """Check if exception indicates EOF or closed stream."""
        error_str = str(e).lower()
        return "eof" in error_str or "closed" in error_str

    # -------------------------------------------------------------------------
    # I/O Methods (Required by IWebSetup)
    # -------------------------------------------------------------------------
    async def _read_output(self):
        """Read from PTY output and send to WebSocket."""
        try:
            while not self._shutdown_event.is_set() and self._is_process_alive():
                data = await asyncio.to_thread(self._read_from_pty)
                
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
            if self._is_eof_error(e):
                LOGGER.debug("Output stream ended.")
            else:
                LOGGER.error(f"Error reading from pty: {e}")
        finally:
            self._shutdown_event.set()

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _clean_output(self, data: str) -> str:
        """No cleaning necessary for Unix."""
        return data

    async def _write_to_process(self, text: str):
        """Write text to PTY with proper newline handling."""
        try:
            LOGGER.debug(f"Incoming raw text: {repr(text)}")
            stripped_text = text.strip(self.nl)
            LOGGER.debug(f"Processed text: {repr(stripped_text)}")
            
            if stripped_text:
                self._write_to_pty(stripped_text)
                self._write_to_pty(self.nl)
            else:
                self._write_to_pty(self.nl)  # Empty command
            
            await asyncio.sleep(0.1)  # Allow processing
            
        except Exception as e:
            LOGGER.error(f"Error writing to pty: {e}")

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------
    async def cleanup(self):
        """Clean up Unix-specific resources."""
        await super().cleanup()

        LOGGER.debug("Unix cleanup started")
        
        try:
            # Try graceful shutdown with SIGINT first
            self._send_interrupt_to_process()
            await asyncio.sleep(.5)
            
            # If still alive, try SIGTERM
            if self._is_process_alive():
                LOGGER.info("Process didn't respond to SIGINT, attempting SIGTERM...")
                try:
                    self._process.kill()
                    LOGGER.debug("Killed subprocess")
                except Exception as e:
                    LOGGER.error(f"Error killing subprocess: {e}")
                
        except Exception as e:
            LOGGER.error(f"Error killing subprocess: {e}")
            # Last resort: try to kill
            if self._is_process_alive():
                try:
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                except Exception as kill_e:
                    LOGGER.error(f"Failed to kill process during error recovery: {kill_e}")
        finally:
            self._process = None
            # Clean up PTY
            self._close_pty()
        