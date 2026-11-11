"""Seed Python ignore rules while preserving the user's existing rules."""
import os
import tempfile


PYTHON_IGNORES = (
    '__pycache__/', '*.py[cod]', '*$py.class', '.venv/', 'venv/', 'env/',
    '.pytest_cache/', '.mypy_cache/', '.ruff_cache/', '.tox/', '.nox/',
    '.coverage', '.coverage.*', 'htmlcov/', 'build/', 'dist/', '*.egg-info/',
    '.env', '.atelier-session/',
)


def with_python_ignores(original):
    bom = b'\xef\xbb\xbf' if original and original.startswith(b'\xef\xbb\xbf') else b''
    existing = (original or b'')[len(bom):]
    rules = set(existing.splitlines())
    missing = [rule.encode('ascii') for rule in PYTHON_IGNORES if rule.encode('ascii') not in rules]
    if not missing:
        return original
    newline = b'\r\n' if b'\r\n' in existing else b'\n'
    block = newline.join([b'# Python / Atelier', *missing]) + newline
    return bom + block + (newline + existing if existing else b'')


def seed_python_gitignore(path):
    if path.is_symlink():
        raise OSError('.gitignore bir sembolik bağlantı.')
    try:
        original = path.read_bytes()
    except FileNotFoundError:
        original = None
    updated = with_python_ignores(original or b'')
    if updated == original:
        return updated
    if original is None:
        with path.open('xb') as handle:
            handle.write(updated)
        return updated
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(updated)
        if path.is_symlink() or path.read_bytes() != original:
            raise OSError('.gitignore işlem sırasında değişti.')
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return updated
