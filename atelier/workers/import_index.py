"""Collect Python exports from source files in the selected environment."""
import ast
import json
import os
from pathlib import Path
import sys
import sysconfig


def modules(root, excluded, limit):
    count = 0
    for folder, directories, names in os.walk(root):
        directories[:] = sorted(name for name in directories if not name.startswith(('.', '_'))
                                and name not in excluded and not (Path(folder, name) / 'pyvenv.cfg').is_file())
        for name in sorted(names):
            path = Path(folder, name)
            if path.suffix not in ('.py', '.pyi') or path.is_symlink():
                continue
            count += 1
            if count > limit:
                return
            parts = list(path.relative_to(root).with_suffix('').parts)
            if parts[-1] == '__init__':
                parts.pop()
            if parts and all(part.isidentifier() and not part.startswith('_') for part in parts):
                yield path, '.'.join(parts)


def exports(path):
    try:
        if path.stat().st_size > 400_000:
            return
        body = ast.parse(path.read_bytes()).body
    except (OSError, SyntaxError, UnicodeError, ValueError, RecursionError):
        return
    for node in body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_'):
            yield node.name, 7 if isinstance(node, ast.ClassDef) else 3
        elif path.stem == '__init__' and isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if name.isidentifier() and not name.startswith('_'):
                    yield name, 0


def index(root):
    excluded = {'build', 'dist', 'venv', 'node_modules', 'site-packages', 'test', 'tests'}
    source_root = root / 'src'
    source_layout = source_root.is_dir() and not (source_root / '__init__.py').is_file()
    locations = [(source_root, 1500)] if source_layout else []
    locations.append((root, 1500))
    for key in ('stdlib', 'purelib', 'platlib'):
        if not (folder := sysconfig.get_path(key)):
            continue
        path = Path(folder)
        if all(path != previous for previous, _ in locations):
            locations.append((path, 2000))
    rows = []
    for location, limit in locations:
        skip = excluded | {'src'} if source_layout and location == root else excluded
        for path, module in modules(location, skip, limit):
            for name, kind in exports(path):
                rows.append((name, module, kind))
                if len(rows) >= 60000:
                    return rows
    return rows


if __name__ == '__main__':
    print(json.dumps(index(Path(sys.argv[1])), ensure_ascii=True))
