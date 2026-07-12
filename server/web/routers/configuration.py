import os
import html
import json
from pathlib import Path
import time
from typing import List, Optional
from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import RedirectResponse

# Web sockets
import asyncio
import shutil
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

# Import modules
from server.routers.handler import RouteHandler
from server.rss.ArrClient import ArrClient, ArrType
from server.rss.QBitClient import QBitClient
from server.web.common import LOGGER, TITLE, get_csrf_token, navigation, page_template
from server.web.routers.auth import authenticate

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/setup")
async def setup(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)

    token = get_csrf_token()
    exceptions = []

    try:
        radarr_client = ArrClient(ArrType.Radarr)
        radarr_status = radarr_client.status() if radarr_client else ""
        LOGGER.debug(f"Radarr Status: {radarr_status}")
    except Exception as e:
        exceptions.append(f"Radarr: {e}")
        radarr_client = {}
        radarr_status = ""
    try:
        sonarr_client = ArrClient(ArrType.Sonarr)
        sonarr_status = sonarr_client.status() if sonarr_client else ""
        LOGGER.debug(f"Sonarr Status: {sonarr_status}")
    except Exception as e:
        exceptions.append(f"Sonarr: {e}")
        sonarr_client = {}
        sonarr_status = ""
    try:
        qbittorrent_client = QBitClient()
        qbittorrent_status = qbittorrent_client.status() if qbittorrent_client else ""
        LOGGER.debug(f"qBittorrent Status: {qbittorrent_status}")
    except Exception as e:
        exceptions.append(f"qBittorrent: {e}")
        qbittorrent_client = {}
        qbittorrent_status = ""

    # Format exceptions, if something is wrong with no exceptions, show a generic error message
    html_exceptions = '<p class="error-message">Radarr: Unknown error occurred</p>' if not exceptions and not radarr_status else ""
    html_exceptions = '<p class="error-message">Sonarr: Unknown error occurred</p>' if not exceptions and not sonarr_status else ""
    html_exceptions = '<p class="error-message">qBittorrent: Unknown error occurred</p>' if not exceptions and not qbittorrent_status else ""
    for e in exceptions:
        html_exceptions += f'<p class="error-message">{e}</p>\n'

    # Build app items html
    def build_apps_html(name: str, url: str, status: str, icon_url: str) -> str:
        placeholder_image = f'style="background-image: url(\'{RouteHandler.STATIC}/favicon.ico\')"' if url else ''
        return f'''<!-- {name} -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if status else 'red-border-shadow' }"{placeholder_image}>
                            <a href="{url if url else '#'}" target="_blank" rel="noreferrer">
                                <img class="app-icon" alt="{name}"
                                    src="{icon_url}"
                                    onerror="this.onerror=null; this.parentElement.parentElement.querySelector('.warning-badge').classList.add('visible')"
                                    onload="this.classList.add('loaded'); this.parentElement.parentElement.style.backgroundImage = 'none';">
                            </a>
                            <span class="warning-badge" title="{name} app image did not load">⚠️</span>
                        </div>
                        <div class="app-info">
                            <span class="app-name">{name}</span>
                            <span class="app-version">{status if status else '?'}</span>
                            <span class="status-dot { 'healthy' if status else 'unhealthy' }"></span>
                        </div>
                    </div>'''
    
    html_apps = ''
    html_apps += build_apps_html(name = radarr_client.ServerName if radarr_client and radarr_client.ServerName else 'Radarr',
                                url = radarr_client.Url if radarr_client and hasattr(radarr_client, 'Url') and radarr_client.Url else None,
                                status = radarr_status['version'] if radarr_status and 'version' in radarr_status else None,
                                icon_url = 'https://avatars.githubusercontent.com/u/25025331')
    html_apps += build_apps_html(name = sonarr_client.ServerName if sonarr_client and sonarr_client.ServerName else 'Sonarr',
                                url = sonarr_client.Url if sonarr_client and hasattr(sonarr_client, 'Url') and sonarr_client.Url else None,
                                status = sonarr_status['version'] if sonarr_status and 'version' in sonarr_status else None,
                                icon_url = 'https://avatars.githubusercontent.com/u/1082903')
    html_apps += build_apps_html(name = qbittorrent_client.ServerName if qbittorrent_client and qbittorrent_client.ServerName else 'qBittorrent',
                                url = qbittorrent_client.Url if qbittorrent_client and hasattr(qbittorrent_client, 'Url') and qbittorrent_client.Url else None,
                                status = qbittorrent_status or None,
                                icon_url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/New_qBittorrent_Logo.svg/1280px-New_qBittorrent_Logo.svg.png')

    setup_command = get_setup_command()

    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.LOGIN}/setup')}
            <h1>{TITLE} ⚙️ Configuration</h1>

            <div id="appIconsContainer" class="text-container">
                <h2>Connected Apps</h2>
                
                <div class="app-icons-container">
                    {html_apps}
                </div>
                <div class="error-container" style="display: {'flex' if not radarr_status or not sonarr_status or not qbittorrent_status else 'none'};">
                    {html_exceptions}
                <p class="hint-message">Try the <a href="#" onclick="showTerminal()">🖥️ Interactive Setup</a> to configure your apps.</p>
            </div>

            </div>
            
            <div class="terminal-container" id="terminalConfig" data-ws="{RouteHandler.LOGIN}/setup/ws">
                <div class="terminal-header">
                    <span class="terminal-title">🖥️ Interactive Setup</span>
                    <div class="terminal-controls">
                        <span class="terminal-dot red"></span>
                        <span class="terminal-dot yellow"></span>
                        <span class="terminal-dot green"></span>
                    </div>
                </div>
                <div class="terminal-output" id="terminalOutput">
                    <div class="terminal-line system">⏳ Initializing setup environment...</div>
                    <div class="terminal-line system">📌 Running: {setup_command.get("html", "")}</div>
                    <div class="terminal-line system">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
                </div>
                <div class="terminal-input-container">
                    <span class="prompt-symbol">{"PS>" if is_windows() else '$'}</span>
                    <input type="text" id="terminalInput" class="terminal-input" placeholder="Type your response here..." />
                    <button type="button" id="sendBtn" class="term-btn term-btn-primary">Send</button>
                </div>
                <div class="terminal-footer">
                    <div class="terminal-status" id="terminalStatus">
                        <span class="status-indicator error"></span>
                        <span id="statusText">Loading</span>
                    </div>
                    <div class="terminal-actions">
                        <button type="button" id="runSetupBtn" class="term-btn term-btn-primary" onclick="connectTerminal()">▶️ Run Setup</button>
                        <button type="button" id="clearBtn" class="term-btn term-btn-secondary" onclick="clearTerminal()">🗑️ Clear</button>
                        <button type="button" id="copyBtn" class="term-btn term-btn-secondary" onclick="copyTerminalOutput()">📋 Copy</button>
                    </div>
                </div>
            </div>
            <div class="button-container">
                <button type="button" class="nav-toggle-button active" data-container="appIconsContainer">📱 Connected Apps</button>
                <button type="button" class="nav-toggle-button" data-container="terminalConfig">🖥️ Interactive Setup</button>
            </div>
        </div>'''
    
    return Response(content=page_template(title="Configuration", content=content, token=token, js="terminal.js", css="setup.css"), media_type="text/html")

def is_windows() -> bool:
    return os.name == 'nt'

def get_setup_command():
    server_path = os.getcwd()
    
    full_path = Path(server_path).resolve().parent

    if is_windows():
        # Just the command without cd
        file = './setup.ps1'
        commands = []
        prompt = 'PS>'
        newline = 'rn'
        ws_command = f"powershell.exe -NoProfile -ExecutionPolicy Bypass -File {file}"
    else:
        file = './setup.sh'
        commands = ['chmod +x setup.sh']
        prompt = '$'
        newline = 'n'
        ws_command = f"bash {file}"

    setup_path = full_path / file
    LOGGER.info(f"❓ File {'exists' if setup_path.exists() else 'does not exist'}: {setup_path}")
    
    # For execution - just the commands without cd
    execution_command = ' && '.join(commands)

    # For HTML display - show the full command with cd
    display_command = f'cd "{str(full_path)}" && ' + ' && '.join(commands+[ws_command])
    html_display = display_command.replace(' && ', '<br>')
    
    # For JSON/attribute - properly escape for HTML attribute
    attribute_cmd = html.escape(execution_command, quote=True)
    # For JSON/attribute - properly escape for HTML attribute
    attribute_wd = html.escape(str(full_path), quote=True)
    
    return {
        'html': html_display,
        'file': file,
        'execution': execution_command,  # Just the command without cd
        'directory': attribute_wd,           # The working directory
        'command': attribute_cmd,       # For data-cmd attribute
        'prompt': prompt,           # The prompt symbol
        'newline': newline           # The newline character
    }

@router.websocket("/setup/ws")
async def websocket_setup(websocket: WebSocket):
    """WebSocket endpoint to run a PowerShell script with interactive terminal"""
    # Get setup configuration
    setup_command = get_setup_command()
    directory = setup_command.get('directory', None)
    file = setup_command.get('file', None)
    pre_commands = setup_command.get('pre_commands', [])
    
    # Create WebSetup instance and run handler
    setup = WebSetup(directory, file, pre_commands=pre_commands)
    await setup.run_websocket_handler(websocket)

class WebSetup:
    """Class to handle PowerShell web setup with WebSocket communication"""
    
    def __init__(self, directory: Optional[str] = None, file: Optional[str] = None, pre_commands: Optional[List[str]] = None):
        """
        Initialize WebSetup instance
        
        Args:
            directory: Working directory for the PowerShell process
            file: PowerShell script file to execute
            pre_commands: Commands to execute before the main script
        """
        self.directory = directory
        self.file = file
        self.pre_commands = pre_commands or []
        self._process = None
        self._tasks = []
        self._input_queue = asyncio.Queue()
        self._stdin_ready_set_time = time.monotonic()
        self._stdin_ready = asyncio.Event()
    
    def is_windows(self) -> bool:
        """Check if running on Windows"""
        return os.name == 'nt'
    
    def get_shell_path(self) -> Optional[str]:
        """Get PowerShell executable path"""
        if self.is_windows():
            return shutil.which('powershell.exe') or shutil.which('pwsh.exe')
        return shutil.which('pwsh') or shutil.which('powershell')
    
    def get_command_args(self) -> List[str]:
        """Build command arguments for PowerShell"""
        args = ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass']
        if self.file:
            args.extend(['-File', self.file])
        return args
    
    async def start_process(self) -> bool:
        """
        Start PowerShell subprocess
        
        Returns:
            bool: True if process started successfully, False otherwise
        """
        powershell_path = self.get_shell_path()
        
        if not powershell_path:
            LOGGER.error("PowerShell executable not found")
            return False
        
        # Set up environment
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        
        # Start process
        self._process = await asyncio.create_subprocess_exec(
            powershell_path,
            *self.get_command_args(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.directory if self.directory else None,
            env=env
        )
        
        LOGGER.info(f"✅ Process created with PID: {self._process.pid}")
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
                    LOGGER.info("stdout: End of stream")
                    break
                try:
                    LOGGER.debug(f"Raw stdout line: {line}")
                    decoded_line = line.decode('utf-8', errors='replace').rstrip('\n')
                    if decoded_line:
                        LOGGER.info(f"📤 Sending output: {decoded_line}")
                        await websocket.send_json({
                            "type": "output",
                            "message": decoded_line
                        })
                except Exception as e:
                    LOGGER.error(f"Error decoding stdout: {e}")
        except Exception as e:
            LOGGER.error(f"Error in read_stdout: {e}")
        LOGGER.info("read_stdout task finished")
    
    async def _read_stderr(self, websocket):
        """Read from stderr and send to WebSocket"""
        try:
            while True:
                self._stdin_ready.set()
                self._stdin_ready_set_time = time.monotonic()
                line = await self._process.stderr.readline()
                self._stdin_ready.clear()
                if not line:
                    LOGGER.info("stderr: End of stream")
                    break
                try:
                    LOGGER.debug(f"Raw stderr line: {line}")
                    decoded_line = line.decode('utf-8', errors='replace').rstrip('\n')
                    if decoded_line:
                        LOGGER.info(f"📤 Sending stderr: {decoded_line}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"[STDERR] {decoded_line}"
                        })
                except Exception as e:
                    LOGGER.error(f"Error decoding stderr: {e}")
        except Exception as e:
            LOGGER.error(f"Error in read_stderr: {e}")
        LOGGER.info("read_stderr task finished")
    
    async def _stdin_writer(self, text: Optional[str] = None):
        """Write text to stdin with proper formatting"""
        await asyncio.sleep(3)
        # self._process.stdin.write('\r\n'.encode('utf-8'))
        await self._process.stdin.drain()
        await asyncio.sleep(.5)
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
                    self._process.stdin.write(fn)
                    await self._process.stdin.drain()
                    await asyncio.sleep(.5)
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

                    LOGGER.info(f"📥 Input queued: {text}")
                    await self._input_queue.put(text)
                    
                except WebSocketDisconnect:
                    LOGGER.info("WebSocket disconnected")
                    break
                except Exception as e:
                    LOGGER.error(f"Error in handle_input: {e}")
                    break
        except Exception as e:
            LOGGER.error(f"Error in handle_input: {e}")
        LOGGER.info("handle_input task finished")
    
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
            # Wait for the command from the client
            data = await websocket.receive_text()
            data_json = json.loads(data)
            LOGGER.info(f"Received from client: {data_json}")
        except json.JSONDecodeError:
            LOGGER.error(f"Error decoding JSON from client: {data}")
            await websocket.send_json({
                "type": "error",
                "message": f"Error decoding JSON from client: {data}"
            })
            return
        
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
                "message": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
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
            LOGGER.info(f"✅ Process completed with exit code: {return_code}")
            
            # Send exit code
            await websocket.send_json({
                "type": "exit",
                "code": return_code
            })
            
            LOGGER.info(f"✅ Setup command completed with exit code: {return_code}")
            
        except WebSocketDisconnect:
            LOGGER.info("WebSocket disconnected")
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