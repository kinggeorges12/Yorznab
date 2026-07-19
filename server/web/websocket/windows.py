import asyncio
import errno
import re

# Windows-specific imports
try:
    from winpty import PtyProcess
except ImportError:
    raise ImportError("Please install pywinpty: pip install pywinpty")

# Import modules
from server.web.common import LOGGER
from server.web.websocket.iwebsetup import IWebSetup, OSConfig

def ansi_to_html(text: str) -> str:
    """Convert all ANSI codes to HTML."""
    # Strip leading \x1b[0m reset codes
    text = re.sub(r'^\x1b\[0m+', '', text)
    
    # Map ANSI codes to CSS
    ansi_map = {
        '0': 'reset',
        '1': 'font-weight: bold;',
        '2': 'font-weight: lighter;',
        '3': 'font-style: italic;',
        '4': 'text-decoration: underline;',
        '30': 'color: black;',
        '31': 'color: red;',
        '32': 'color: green;',
        '33': 'color: #ffcc00;',
        '34': 'color: blue;',
        '35': 'color: magenta;',
        '36': 'color: cyan;',
        '37': 'color: white;',
        '90': 'color: gray;',
        '91': 'color: #ff6b6b;',
        '92': 'color: #51cf66;',
        '93': 'color: #fcc419;',
        '94': 'color: #4dabf7;',
        '95': 'color: #da77f2;',
        '96': 'color: #22b8cf;',
        '97': 'color: #f8f9fa;',
    }
    
    def replace_ansi(match):
        codes = match.group(1).split(';')
        
        # Check if this is a reset (contains '0')
        if '0' in codes:
            # Remove '0' from the list and process remaining codes for the new span
            remaining_codes = [c for c in codes if c != '0']
            if remaining_codes:
                # Start a new span with the remaining styles
                styles = []
                for code in remaining_codes:
                    if code in ansi_map:
                        styles.append(ansi_map[code])
                if styles:
                    return f'</span><span style="{"" .join(styles)}">'
            # If no remaining codes, just close the span
            return '</span>'
        
        # No reset code - build styles
        styles = []
        for code in codes:
            if code in ansi_map:
                styles.append(ansi_map[code])
        
        if styles:
            return f'<span style="{"" .join(styles)}">'
        return ''
    
    # Match \x1b[<codes>m
    pattern = re.compile(r'\x1b\[([0-9;]*)m')
    result = pattern.sub(replace_ansi, text)
    
    # Close any unclosed spans
    open_spans = result.count('<span')
    close_spans = result.count('</span>')
    if open_spans > close_spans:
        result += '</span>' * (open_spans - close_spans)
    
    return result

class WebSetupWindows(IWebSetup):
    """Class to handle PowerShell web setup with WebSocket communication"""
    
    def __init__(self, os_config: OSConfig):
        super().__init__(os_config)
        self._process = None
        self._process_pid = None

        # Compile regex patterns once
        self._vt_escape = re.compile(
            r"""
            \x1B
            (?:
                \[[0-?]*[ -/]*[@-~]      # CSI sequences: ESC[...letter
                |
                \][^\x07]*(?:\x07|\x1B\\) # OSC sequences
                |
                [@-_]                     # Single ESC commands
            )
            """, re.VERBOSE )
        self._line_escape = re.compile(r"""
            (?: \x1b\[0m )+        # Group 1: One or more reset codes
            |
            (?: \x1b\[ (\d+) ; (\d+) H )  # Group 2: Cursor position (row, col)
            """, re.VERBOSE)

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

    # -------------------------------------------------------------------------
    # I/O Methods (Required by IWebSetup)
    # -------------------------------------------------------------------------
    async def _read_output(self):
        """Read from winpty output and send to WebSocket."""
        try:
            while not self._shutdown_event.is_set() and self._is_process_alive():
                try:
                    data = await asyncio.wait_for(asyncio.to_thread(self._process.read), timeout=None)
                    
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

    def _clean_output(self, data: str) -> str:
        """Clean terminal escape sequences from output."""
        if not self._seen_initial_vt:
            data = self._vt_escape.sub('', data)
            if data.strip():
                self._seen_initial_vt = True
                
        html_data = ansi_to_html(data)
        clean_line = self._line_escape.sub('', html_data)
        reencoded_line = clean_line.encode(
            self.os_config.terminal_encoding,
            errors="replace"
        ).decode("utf-8", errors="replace")
        return reencoded_line

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