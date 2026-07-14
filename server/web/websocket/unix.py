import os
import signal
import asyncio
import pty
import subprocess
import errno

# Import modules
from server.web.common import LOGGER
from server.web.websocket.iwebsetup import IWebSetup, OSConfig


class WebSetupUnix(IWebSetup):
    """Class to handle bash web setup with WebSocket communication"""
    
    def __init__(self, os_config: OSConfig):
        super().__init__(os_config)
        self._pty_controller_fd = None

    def _is_process_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _send_interrupt_to_process(self):
        if self._process and self._process.poll() is None:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGINT)
            except Exception as e:
                LOGGER.error(f"Error sending Ctrl+C: {e}")

    def _get_process_exit_code(self) -> int:
        return_code = self._process.poll()
        return return_code if return_code is not None else 0

    def _kill_process(self):
        if self._process and self._process.poll() is None:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
            except Exception as e:
                LOGGER.error(f"Error killing process: {e}")

    async def start_process(self) -> bool:
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

    def _signal_handler(self, signum, frame):
        LOGGER.info("🔴 Ctrl+C received, stopping bash process...")
        self._send_interrupt_to_process()
        self._shutdown_event.set()
        self._process_running = False

    def _read_from_pty(self) -> str:
        try:
            data = os.read(self._pty_controller_fd, 4096)
            if data:
                return data.decode('utf-8', errors='replace')
            return ''
        except OSError as e:
            if e.errno == errno.EBADF:  # EBADF
                return ''
            raise

    def _write_to_pty(self, text: str):
        try:
            os.write(self._pty_controller_fd, text.encode('utf-8'))
        except OSError as e:
            LOGGER.error(f"Error writing to pty: {e}")

    async def _read_output(self):
        try:
            while not self._shutdown_event.is_set():
                if not self._is_process_alive():
                    LOGGER.debug("Process is no longer alive, stopping output reader.")
                    break

                try:
                    data = await asyncio.to_thread(self._read_from_pty)
                    if data:
                        await self._process_output_data(data)
                    else:
                        await asyncio.sleep(0.01)
                        
                except OSError as e:
                    if e.errno == errno.EIO:  # Input/output error (5)
                        LOGGER.debug("PTY closed (I/O error), stopping output reader.")
                        break
                    raise
                except Exception as e:
                    if "EOF" in str(e) or "closed" in str(e).lower():
                        LOGGER.debug("Output stream: End of stream")
                        break
                    raise
                    
        except asyncio.CancelledError:
            LOGGER.debug("Output reader task was cancelled.")
        except Exception as e:
            LOGGER.error(f"Error reading from pty: {e}")
        finally:
            self._process_running = False
            self._shutdown_event.set()

    async def _stdin_writer(self):
        await asyncio.sleep(2)
        
        while not self._shutdown_event.is_set():
            if not self._is_process_alive():
                break

            try:
                try:
                    text = await asyncio.wait_for(self._input_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                
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
                    stripped_text = text.strip(self.nl)
                    LOGGER.debug(f"Processed text: {repr(stripped_text)}")
                    
                    if stripped_text:
                        self._write_to_pty(stripped_text)
                        self._write_to_pty(self.nl)
                    else:
                        self._write_to_pty(self.nl)
                    
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    LOGGER.error(f"Error writing to pty: {e}")
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
        """Clean up resources - Unix-specific cleanup"""
        # Call the common cleanup first
        await super().cleanup()
        
        # Now do Unix-specific cleanup
        if self._process:
            try:
                if self._process.poll() is None:
                    try:
                        os.killpg(os.getpgid(self._process.pid), signal.SIGHUP)
                        await asyncio.sleep(1)
                    except:
                        pass
                    
                    if self._process.poll() is None:
                        self._kill_process()
            except Exception as e:
                LOGGER.error(f"Error during process cleanup: {e}")
            self._process = None
        
        if self._pty_controller_fd:
            try:
                os.close(self._pty_controller_fd)
            except:
                pass
            self._pty_controller_fd = None