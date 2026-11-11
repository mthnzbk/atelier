"""Start packaged Python tools without installing them into the project."""
from pathlib import Path
import os
import runpy
import sys


if __name__ == '__main__':
    tool = sys.argv.pop(1)
    sys.path.insert(0, str(Path(__file__).resolve().with_name('vendor')))
    if tool == 'debug':
        os.environ['PYDEVD_USE_CYTHON'] = 'NO'
    runpy.run_module({'lsp': 'pylsp', 'debug': 'debugpy.adapter'}[tool], run_name='__main__')
