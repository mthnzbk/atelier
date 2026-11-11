"""Start a source worker with a known application import path."""
from pathlib import Path
import sys

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('task', 'terminal'):
        raise SystemExit('Expected a task or terminal worker.')
    kind = sys.argv.pop(1)
    if __name__ == '__main__':
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    if sys.platform == 'win32' and (sys.stdin is None or sys.stdout is None):
        import ctypes
        import msvcrt
        import os
        from ctypes import wintypes

        handle = ctypes.WinDLL('kernel32').GetStdHandle
        handle.argtypes = [wintypes.DWORD]
        handle.restype = wintypes.HANDLE
        for name, number, mode, flags in (
            ('stdin', -10, 'r', os.O_RDONLY), ('stdout', -11, 'w', os.O_WRONLY)
        ):
            if getattr(sys, name) is None:
                fd = msvcrt.open_osfhandle(handle(number), flags | os.O_BINARY)
                setattr(sys, name, os.fdopen(fd, mode, encoding='utf-8'))
    if kind == 'task':
        from atelier.workers.tasks import main as run
    else:
        from atelier.workers.terminal import run
    run()


if __name__ == '__main__':
    main()
