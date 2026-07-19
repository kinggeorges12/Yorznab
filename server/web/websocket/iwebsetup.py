from abc import abstractmethod
from dataclasses import dataclass, field
import os
from typing import Dict, List, Optional
import json
import re
import asyncio
import signal
from contextlib import suppress
from fastapi import WebSocket, WebSocketDisconnect

# Import modules
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
    terminal_encoding: str
    env: Dict[str, str] = field(default_factory=dict)
    args: List[str] = field(default_factory=list)
    preload_script: Optional[str] = None


class IWebSetup:
    """Interface for WebSetup implementations"""
    
    def __init__(self, os_config: OSConfig):
        self.os_config = os_config
        
        # Common instance attributes
        self._process = None
        self._tasks = []
        self._read_buffer = ''
        self._process_running = False
        self._websocket: Optional[WebSocket] = None
        self._input_queue = asyncio.Queue()
        self._shutdown_event = asyncio.Event()
        self._seen_initial_vt = False
        self._cleanup_done = False
        
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
            """,
            re.VERBOSE
        )
        self._line_escape = re.compile(
            r'(?:\x1b\[0m)+|(?:\x1b\[(\d+);(\d+)H)'
        )

    @property
    def nl(self):
        return self.os_config.newline

    # -------------------------------------------------------------------------
    # Abstract Methods (OS-specific)
    # -------------------------------------------------------------------------
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
    async def _write_to_process(self, text: str):
        """Write text to stdin"""
        pass

    async def _stdin_writer(self):
        """Write text to stdin using abstract write method."""
        await asyncio.sleep(2)
        
        while not self._shutdown_event.is_set() and self._is_process_alive():
            try:
                text = await asyncio.wait_for(self._input_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                LOGGER.debug("Stdin writer task cancelled")
                break 
            
            await self._send_echo(text)
            await self._write_to_process(text)
            self._input_queue.task_done()
        
        LOGGER.debug("Stdin writer finished")
        self._shutdown_event.set()

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

    # -------------------------------------------------------------------------
    # Helper Methods (Shared)
    # -------------------------------------------------------------------------
    async def _safe_send_json(self, data: dict) -> bool:
        """Safely send JSON to WebSocket. Returns True if successful."""
        if not self._websocket:
            return False
        try:
            await self._websocket.send_json(data)
            return True
        except Exception:
            return False

    def _clean_output(self, data: str) -> str:
        """Clean terminal escape sequences from output."""
        if not self.os_config.is_windows: 
            return data
        if not self._seen_initial_vt:
            data = self._vt_escape.sub('', data)
            if data.strip():
                self._seen_initial_vt = True
        
        clean_line = self._line_escape.sub('', data)
        return clean_line.encode(
            self.os_config.terminal_encoding, 
            errors="replace"
        ).decode("utf-8", errors="replace")

    async def _process_output_data(self, data: str):
        """Process output data and send to WebSocket."""
        clean_data = self._clean_output(data)
        self._read_buffer += clean_data
        
        while '\n' in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split('\n', 1)
            LOGGER.debug(f"📤 Sending output: {line}")
            
            if not await self._safe_send_json({
                "type": "output",
                "message": line
            }):
                self._shutdown_event.set()

    async def _handle_input(self):
        """Handle user input from WebSocket."""
        while not self._shutdown_event.is_set():
            if not self._process or not self._is_process_alive():
                break
            
            try:
                data = await asyncio.wait_for(
                    self._websocket.receive_text(), 
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                LOGGER.debug("WebSocket disconnected")
                break
            
            await self._process_input(data)
        
        self._shutdown_event.set()

    async def _process_input(self, data: str):
        """Process a single input message."""
        try:
            json_data = json.loads(data)
            msg_type = json_data.get('type')
            
            if msg_type == 'input':
                text = json_data.get('message', '')
                LOGGER.debug(f"📥 Input received: {text}")
                
                if text in ('\x03', 'Ctrl+C'):
                    LOGGER.debug("🔴 Ctrl+C detected, sending interrupt")
                    self._send_interrupt_to_process()
                    return
                
                await self._input_queue.put(text)
                
            elif msg_type == 'ready':
                LOGGER.debug("🟢 Client ready message received")
                
        except json.JSONDecodeError:
            LOGGER.debug(f"📥 Input received (plain text): {data}")
            await self._input_queue.put(data)
        except Exception as e:
            LOGGER.error(f"Error processing input: {e}")

    async def _send_initial_messages(self):
        """Send initial connection messages to WebSocket."""
        messages = [
            f"✅ Connected to {self.os_config.shell_name} session",
        ]
        
        if self.os_config.directory:
            messages.append(f"📁 Working directory: {self.os_config.directory}")
        
        messages.extend([
            "💡 Interactive terminal loading...",
            "━"*80,
            ""
        ])
        
        for msg in messages:
            await self._safe_send_json({
                "type": "system",
                "message": msg
            })

    async def _handle_process_completion(self, return_code: int):
        """Handle process completion."""
        LOGGER.debug(f"✅ Process completed with exit code: {return_code}")
        await self._safe_send_json({
            "type": "exit",
            "code": return_code
        })
        
        if return_code == 0:
            LOGGER.info("🔄 Reloading configuration after setup")
            AppSettings(filename='settings.yaml').load()

    async def _cancel_tasks(self):
        """Cancel all running tasks."""
        for task in self._tasks:
            with suppress(asyncio.CancelledError):
                task.cancel()

    # -------------------------------------------------------------------------
    # Main Methods
    # -------------------------------------------------------------------------
    async def cleanup(self):
        """Clean up resources."""
        if self._cleanup_done:
            return
        
        LOGGER.debug("Running cleanup...")
        
        self._shutdown_event.set()
        self._process_running = False
        
        await self._cancel_tasks()
        self._read_buffer = ''

        self._kill_process()
        
        self._cleanup_done = True
        LOGGER.debug("Cleanup complete.")

    async def run(self, websocket):
        """Main WebSocket handler."""
        self._websocket = websocket
        await self._websocket.accept()
        
        original_sigint_handler = signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            await self._send_initial_messages()
            
            LOGGER.info(f"📄 Running script: {self.os_config.file}")
            LOGGER.info(f"🔧 Starting {self.os_config.shell_name} in: {self.os_config.directory}")
            
            if not await self.start_process():
                await self._safe_send_json({
                    "type": "error",
                    "message": f"{self.os_config.shell_name} executable not found"
                })
                return
            
            self._tasks = [
                asyncio.create_task(self._read_output()),
                asyncio.create_task(self._handle_input()),
                asyncio.create_task(self._stdin_writer()),
            ]
            
            while not self._shutdown_event.is_set():
                await asyncio.sleep(0.1)
            
            if self._process:
                return_code = self._get_process_exit_code()
                await self._handle_process_completion(return_code)
            
            LOGGER.debug("Main loop exited")
                
        except WebSocketDisconnect:
            LOGGER.debug("WebSocket disconnected")
        except Exception as e:
            LOGGER.error(f"❌ Error in WebSocket setup: {e}")
            await self._safe_send_json({
                "type": "error",
                "message": f"Error: {str(e)}"
            })
        finally:
            signal.signal(signal.SIGINT, original_sigint_handler)
            signal.signal(signal.SIGTERM, original_sigint_handler)
            
            await self.cleanup()
            
            LOGGER.debug("WebSetup closing...")

            # asyncio.get_running_loop().stop()
            # asyncio.get_event_loop().stop()
        return