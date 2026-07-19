import os
import atexit
from pathlib import Path
from typing import List
import shutil
import asyncio

# Import modules
from server import PROJECT_ROOT
from server.web.websocket.iwebsetup import OSConfig, IWebSetup

class WebSetup(IWebSetup):
    """Proxy class for web setup with WebSocket communication.
    Loads OS-specific implementation in __init__ using factory pattern.
    """
    
    # Class-level cached OS configuration
    _os_config: OSConfig = None
    _os_config_loaded: bool = False
    _impl_instance = None
    
    def __new__(cls):
        """Create new instance and ensure OS config is loaded"""
        cls._load_os_config()
        return super().__new__(cls)
    
    def __init__(self):
        """Initialize the proxy instance - factory creates the appropriate implementation"""
        # Factory logic to create the proper implementation
        if self._os_config.is_windows:
            from server.web.websocket.windows import WebSetupWindows
            self._impl = WebSetupWindows(self._os_config)
        else:
            # For Unix/Linux systems
            from server.web.websocket.unix import WebSetupUnix
            self._impl = WebSetupUnix(self._os_config)
        
        # Store instance for cleanup
        WebSetup._impl_instance = self._impl
    
    def __getattr__(self, name):
        """
        Delegate attribute access to the implementation.
        This allows the proxy to act as a drop-in replacement.
        """
        if hasattr(self._impl, name):
            return getattr(self._impl, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    @classmethod
    def _load_os_config(cls) -> None:
        """Load and configure all OS-dependent setup (runs once at class level)"""
        if cls._os_config_loaded:
            return
        
        is_windows = os.name == 'nt'
        directory = PROJECT_ROOT

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        env['PYTHONPATH'] = directory
        
        preload_script_str = None
        terminal_encoding='utf-8'
        
        if is_windows:
            file = './scripts/console.ps1'
            powershell_cmd = shutil.which('pwsh.exe')
            if powershell_cmd is None:
                powershell_cmd = shutil.which('powershell.exe')
                terminal_encoding='windows-1252'
            exec_path = powershell_cmd
            prompt = 'PS>'
            newline = '\r\n'
            args = ['-NoProfile', '-ExecutionPolicy', 'Bypass']
            if file:
                args.extend(['-File', file])
            shell_name='PowerShell'
        else:
            file = './scripts/console.sh'
            exec_path = shutil.which('bash') or shutil.which('sh')
            prompt = '$'
            newline = '\n'
            args = [file] if file else []
            filepath = Path(os.path.join(directory, file))
            preload_script_str = f"chmod +x {file}"
            shell_name='Bash'

        cls._os_config = OSConfig(
            is_windows=is_windows,
            directory=directory,
            file=file,
            exec_path=exec_path,
            shell_name=shell_name,
            prompt=prompt,
            newline=newline,
            terminal_encoding=terminal_encoding,
            env=env,
            args=args,
            preload_script=preload_script_str,
        )
        cls._os_config_loaded = True
    
    @classmethod
    def is_windows(cls) -> bool:
        """Check if running on Windows"""
        cls._load_os_config()
        return cls._os_config.is_windows
    
    @classmethod
    def shell_name(cls) -> str:
        """Get the shell name"""
        cls._load_os_config()
        return cls._os_config.shell_name

    @classmethod
    def prompt(cls) -> str:
        """Get the prompt symbol"""
        cls._load_os_config()
        return cls._os_config.prompt
    
    @classmethod
    def commands(cls) -> List[str]:
        """Get the command list"""
        cls._load_os_config()
        commands = []
        commands += [f"cd {cls._os_config.directory}"]
        if cls._os_config.preload_script:
            commands += [cls._os_config.preload_script]
        commands += [f"{cls._os_config.exec_path} {' '.join(cls._os_config.args)}"]
        return commands
    
    async def run(self, websocket):
        """
        Main WebSocket handler - delegates to the implementation.
        """
        await self._impl.run(websocket)