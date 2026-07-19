import asyncio
from contextlib import suppress
import errno
import signal
import os
import subprocess
import sys

from fastapi import WebSocketDisconnect

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
        self._process = None
        self._process_pid = None

    # -------------------------------------------------------------------------
    # Process Lifecycle Methods (Required by IWebSetup)
    # -------------------------------------------------------------------------
    def _is_process_alive(self) -> bool:
        """Check if winpty process is still alive."""
        if self._process is None:
            return False
        try:
            return self._process.isalive()
        except Exception:
            return False

    def _send_interrupt_to_process(self):
        """Send Ctrl+C to the winpty process."""
        if self._is_process_alive():
            try:
                self._process.write('\x03')
                self._process.write('\x03')
                self._process.write('\x03')
                LOGGER.info("✅ Sent Ctrl+C to PowerShell")
            except Exception as e:
                LOGGER.error(f"Error sending Ctrl+C: {e}")

    def _get_process_exit_code(self) -> int:
        """Get the winpty process exit code."""
        if self._process is None:
            return 0
        try:
            return getattr(self._process, 'exitstatus', 0)
        except Exception:
            return 0

    def _kill_process(self):
        """Force kill the winpty process."""
        if not self._is_process_alive():
            return
        
        try:
            self._process.kill()
            LOGGER.info(f"✅ Killed process {self._process.pid} via winpty.kill()")
        except Exception as e:
            LOGGER.error(f"Error killing process via winpty: {e}")

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
            
            self._process_pid = self._process.pid
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

    # -------------------------------------------------------------------------
    # I/O Methods (Required by IWebSetup)
    # -------------------------------------------------------------------------
    async def _read_output(self):
        """Read from winpty output and send to WebSocket."""
        try:
            while not self._shutdown_event.is_set() and self._is_process_alive():
                try:
                    data = await asyncio.wait_for(
                        asyncio.to_thread(self._process.read),
                        timeout=0.5
                    )
                    
                    if data:
                        await self._process_output_data(data)
                    else:
                        await asyncio.sleep(0.01)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    if "EOF" in str(e) or "closed" in str(e).lower():
                        break
                    raise
                    
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
            stripped_text = text.strip(self.nl)
            
            if stripped_text:
                self._process.write(stripped_text)
                self._process.write(self.nl)
            else:
                self._process.write(self.nl)
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            LOGGER.error(f"Error writing to winpty: {e}")

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------
    async def cleanup(self):
        """Clean up Windows-specific resources."""
        
        LOGGER.debug("Windows cleanup started")
        
        # Close winpty process - this breaks the read loop
        if self._process:
            try:
                self._process.close()
                LOGGER.debug("Winpty process closed")
            except Exception as e:
                LOGGER.error(f"Error closing winpty: {e}")
        
        # Call base cleanup (sets shutdown event, cancels tasks)
        await super().cleanup()