"""
Cross-platform file locking implementation.

This module provides a FileLock class that can be used to prevent multiple
instances of a script from running simultaneously. It tries to use the
filelock library if available, otherwise falls back to a custom implementation
using OS-level locking primitives.
"""

import contextlib
import os
import sys
import time
from typing import Optional


 


# Try to import the filelock library first
try:
    from filelock import FileLock as ExternalFileLock
    
    # Use the external library directly - it already blocks by default
    FileLock = ExternalFileLock
    
except ImportError:
    # Fallback to custom implementation using fcntl/msvcrt
    class FileLock:
        """
        Custom file lock implementation using OS-level locking primitives.
        
        Uses fcntl on Unix/Linux and msvcrt on Windows for cross-platform support.
        Blocks until lock is available by default.
        """
        
        def __init__(self, lock_file: str):
            """
            Initialize the file lock.
            
            Args:
                lock_file: Path to the lock file
            """
            self.lock_file = lock_file
            self._fd: Optional[int] = None
            self._locked = False

        def acquire(self, timeout: float = -1) -> None:
            """
            Acquire an exclusive lock on the file.
            
            Args:
                timeout: Maximum time to wait for lock acquisition in seconds.
                        -1 means wait indefinitely (default behavior).
            
            Raises:
                TimeoutError: If timeout is reached and lock cannot be acquired.
            """
            wait_seconds = 0
            
            while True:
                try:
                    # Open the file for writing
                    self._fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR)
                    
                    # Try to acquire an exclusive lock
                    if sys.platform.startswith('win'):
                        # Windows: use msvcrt for file locking
                        import msvcrt
                        msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                    else:
                        # Unix/Linux: use fcntl for file locking
                        import fcntl
                        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    
                    # Write PID to lock file for debugging
                    os.write(self._fd, str(os.getpid()).encode())
                    os.fsync(self._fd)
                    self._locked = True
                    return
                    
                except (OSError, IOError) as e:
                    if self._fd is not None:
                        os.close(self._fd)
                        self._fd = None
                    
                    # Only check timeout if it's explicitly set (not -1)
                    if timeout != -1 and wait_seconds >= timeout:
                        raise TimeoutError(f"Could not acquire lock within {timeout} seconds")
                    
                    wait_seconds += 1
                    print(f"Another instance has been running for {wait_seconds} seconds. Waiting...", file=sys.stderr)
                    time.sleep(1)

        def release(self) -> None:
            """Release the file lock."""
            if self._fd is not None and self._locked:
                try:
                    if sys.platform.startswith('win'):
                        import msvcrt
                        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self._fd, fcntl.LOCK_UN)
                except (OSError, IOError):
                    pass
                finally:
                    os.close(self._fd)
                    self._fd = None
                    self._locked = False
                    
            # Clean up the lock file
            with contextlib.suppress(FileNotFoundError, OSError):
                os.remove(self.lock_file)

        def __enter__(self):
            """Context manager entry."""
            self.acquire()
            return self

        def __exit__(self, exc_type, exc, tb):
            """Context manager exit."""
            self.release()