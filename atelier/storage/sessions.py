"""Atomic recovery snapshots, separate from user files and QSettings layout."""
import json
import hashlib
import os
from pathlib import Path
from PySide6.QtCore import QStandardPaths


class SessionStore:
    def __init__(self, settings):
        # Ini-backed test/custom profiles get isolated recovery files.
        if settings.format() == settings.Format.IniFormat:
            directory = Path(settings.fileName()).parent / '.atelier-session'
        else:
            directory = Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'recovery'
        directory.mkdir(parents=True, exist_ok=True)
        self.legacy_path = directory / 'session.json'
        self.path = self.legacy_path
        self.root = None

    def select(self, root):
        self.root = os.path.normcase(str(root.resolve()))
        key = hashlib.sha256(self.root.encode('utf-8')).hexdigest()[:24]
        self.path = self.legacy_path.with_name(f'session-{key}.json')

    def load(self):
        try:
            path = self.path if self.path.exists() else self.legacy_path
            result = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(result, dict) and result.get(
                    'version') == 1 and os.path.normcase(result.get('root', '')) == self.root:
                return result
        except (OSError, ValueError, TypeError):
            return {}
        return {}

    def save(self, value):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'version': 1, **value},
                             ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, self.path)
