"""Import completion suggestions without delaying the language server."""
import json
import re

from PySide6.QtCore import QProcess, QTimer, Signal

from atelier.languages.python_tools import COMMON, import_insertion_line
from atelier.projects.environments import clean_environment
from atelier.runtime.paths import worker_script


class AutoImportIndex(QProcess):
    loaded = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.requested = False
        self.rows = []
        self.finished.connect(self.load)
        self.timeout = QTimer(self, singleShot=True, interval=15000)
        self.timeout.timeout.connect(self.kill)

    def invalidate(self):
        self.requested = False
        self.rows = []

    def reset(self):
        self.invalidate()
        self.timeout.stop()
        if self.state() != QProcess.ProcessState.NotRunning:
            self.kill()
            self.waitForFinished(700)

    def load(self, code, *_):
        self.timeout.stop()
        if self.requested and code == 0:
            try:
                self.rows = json.loads(bytes(self.readAllStandardOutput()))
                self.loaded.emit()
            except ValueError:
                pass

    def suggestions(self, doc, editor, before, prefix, ordinary):
        leading = before[:-len(prefix)] if prefix else before
        if (len(prefix) < 2 or leading.endswith('.') or
                re.match(r'\s*(?:from|import|def|class)\b', leading) or
                editor.textCursor().block().previous().userState() in (1, 2) or
                '#' in leading or any(leading.count(quote) % 2 for quote in ('"', "'"))):
            return []
        if not self.requested and self.state() == QProcess.ProcessState.NotRunning:
            self.requested = True
            self.setProcessEnvironment(clean_environment())
            self.start(self.window.interpreter,
                       ['-I', '-u', str(worker_script('import_index.py')), str(self.window.root)])
            self.timeout.start()
        source = editor.toPlainText()
        lines = source.split('\n')
        try:
            line = import_insertion_line(source)
        except SyntaxError:
            try:
                line = import_insertion_line('\n'.join(lines[:editor.textCursor().blockNumber()]))
            except SyntaxError:
                line = next((index for index, text in enumerate(lines)
                             if text.strip() and not text.lstrip().startswith('#')), 0)
        position = {'line': line, 'character': 0}
        existing = {item['label'].split('(')[0] for item in ordinary if 'label' in item}
        existing.update(match[1] for match in re.finditer(r'^\s*(?:class|def)\s+(\w+)', source, re.MULTILINE))
        choices = {}
        if doc.path and doc.path.is_relative_to(self.window.root):
            parts = doc.path.relative_to(self.window.root).with_suffix('').parts
            own_module = '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)
        else:
            own_module = ''
        for name, module, kind in self.rows:
            if name.startswith(prefix) and name not in existing and module != own_module:
                choices.setdefault((name, f'from {module} import {name}'), kind)
        for name, statement in COMMON.items():
            if name.startswith(prefix) and name not in existing:
                kind = 7 if name[0].isupper() and name not in ('Any', 'Optional', 'Callable') else 0
                choices.setdefault((name, statement), kind)
        result = []
        source_lines = {text.strip() for text in lines}
        for (name, statement), kind in sorted(choices.items(), key=lambda row: (row[0][0] != prefix, row[0])):
            if statement in source_lines:
                continue
            result.append(dict(label=name, kind=kind, detail=statement, additionalTextEdits=[
                {'range': {'start': position, 'end': position}, 'newText': statement + '\n'}]))
            if len(result) == 30:
                break
        return result
