"""Bounded project traversal shared by background jobs and navigation."""
import os
import tokenize
from pathlib import Path

IGNORED = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', '.idea', '.mypy_cache',
           '.pytest_cache', '.ruff_cache', '.tox', '.nox', 'site-packages', 'dist', 'build'}
SUFFIXES = {
    '.py',
    '.pyw',
    '.txt',
    '.md',
    '.toml',
    '.json',
    '.yaml',
    '.yml',
    '.ini',
    '.cfg',
    '.html',
    '.css',
    '.js',
    '.ts',
    '.sql'}


def files(root, suffixes=SUFFIXES, max_files=30000):
    visited = 0
    for folder, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in IGNORED and not Path(folder, name).is_symlink()
                   and not (Path(folder, name) / 'pyvenv.cfg').is_file()]
        for name in names:
            visited += 1
            if visited > max_files:
                return
            path = Path(folder, name)
            if path.suffix.lower() in suffixes and not path.is_symlink():
                try:
                    if path.stat().st_size <= 2_000_000:
                        yield path
                except OSError:
                    pass


def read_source(path):
    if path.suffix.lower() in ('.py', '.pyw'):
        with tokenize.open(path) as handle:
            return handle.read()
    return path.read_text(encoding='utf-8')
