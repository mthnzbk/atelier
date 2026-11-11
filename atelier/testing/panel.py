import json
import shlex
from atelier.ui.icons import for_text
from atelier.runtime.paths import worker_script
from PySide6.QtCore import Qt, QProcess, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QSplitter, QHeaderView


class TestPanel(QWidget):
    navigate = Signal(str, int)

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(lambda _: self.label.setText(self.process.errorString()))
        self.buffer = bytearray()
        self.items = {}
        self.results = {}
        self.mode = 'collect'
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.label = QLabel('pytest · testleri keşfedin')
        row.addWidget(self.label, 1)
        for text, callback in [('Keşfet', lambda: self.start('collect')), ('Tümünü çalıştır', lambda: self.start('run')),
                               ('Seçileni çalıştır', self.run_selected), ('Durdur', self.process.kill)]:
            button = QPushButton(text)
            button.setIcon(for_text(text))
            button.setProperty('materialButton', True)
            button.clicked.connect(lambda checked=False, fn=callback: fn())
            row.addWidget(button)
        layout.addLayout(row)
        splitter = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Test', 'Sonuç'])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemClicked.connect(self.show_detail)
        self.tree.itemDoubleClicked.connect(self.open_result)
        self.detail = QPlainTextEdit(readOnly=True)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.detail)
        self.coverage_tree = QTreeWidget()
        self.coverage_tree.setHeaderLabels(['Kapsam', 'Oran', 'Eksik satır'])
        self.coverage_tree.hide()
        self.coverage_tree.itemDoubleClicked.connect(
            lambda item, *_: self.navigate.emit(*item.data(0, Qt.ItemDataRole.UserRole)))
        splitter.addWidget(self.coverage_tree)
        layout.addWidget(splitter)

    def start(self, mode, node=None):
        if not self.window.require_project_trust():
            return
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        from atelier.projects.environments import PYTHON_MISSING, valid_python_path
        if not valid_python_path(self.window.interpreter):
            self.label.setText(PYTHON_MISSING)
            return
        for doc in self.window.documents:
            self.window.cancel_save(doc)
            if doc.editor.document().isModified() and not self.window.save(doc=doc, allow_format=False):
                return
        self.mode = mode
        self.buffer.clear()
        self.results.clear()
        self.detail.clear()
        self.label.setText('Testler keşfediliyor…' if mode == 'collect' else 'Testler çalışıyor…')
        if node is None:
            self.tree.clear()
            self.items.clear()
        self.process.setWorkingDirectory(str(self.window.root))
        from atelier.projects.environments import clean_environment
        environment = clean_environment()
        environment.insert('ATELIER_COVERAGE', '1' if self.window.coverage_enabled else '0')
        self.process.setProcessEnvironment(environment)
        args = ['-u', str(worker_script('pytest_host.py')), mode]
        if node:
            args.append(node)
        else:
            args.append('.')
        try:
            args.extend(shlex.split(self.window.test_args))
        except ValueError as error:
            self.label.setText(str(error))
            return
        self.process.start(self.window.interpreter, args)

    def run_selected(self):
        item = self.tree.currentItem()
        if item:
            self.start('run', item.data(0, Qt.ItemDataRole.UserRole)['id'])

    def read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b'\n' in self.buffer:
            line, _, remaining = self.buffer.partition(b'\n')
            self.buffer = bytearray(remaining)
            text = line.decode('utf-8', 'replace')
            marker = text.find('@@ATELIER@@')
            if marker >= 0:
                try:
                    self.handle(json.loads(text[marker + len('@@ATELIER@@'):]))
                except ValueError:
                    pass
            else:
                self.detail.appendPlainText(text)

    def handle(self, event):
        if 'coverage' in event:
            self.window.apply_coverage(event['coverage'])
        if 'error' in event:
            self.detail.appendPlainText(event['error'])
        for test in event.get('collected', []):
            item = self.items.get(test['id'])
            if item is None:
                item = QTreeWidgetItem(self.tree, [test['id'], 'Hazır'])
                self.items[test['id']] = item
            item.setData(0, Qt.ItemDataRole.UserRole, test)
        if 'result' in event:
            result = event['result']
            self.results[result['id']] = result
            item = self.items.get(result['id'])
            if item:
                item.setText(1, {'passed': 'Geçti', 'failed': 'Başarısız',
                             'skipped': 'Atlandı'}[result['outcome']])
                item.setForeground(1,
                                   QColor({'passed': '#34d399',
                                           'failed': '#fb7185',
                                           'skipped': '#fbbf24'}[result['outcome']]))
                stored = item.data(0, Qt.ItemDataRole.UserRole)
                if result.get('path'):
                    stored.update(
                        path=str(
                            (self.window.root / result['path']).resolve()),
                        line=result['line'])
                    item.setData(0, Qt.ItemDataRole.UserRole, stored)

    def show_detail(self, item, *_):
        test = item.data(0, Qt.ItemDataRole.UserRole)
        result = self.results.get(test['id'])
        if result:
            self.detail.setPlainText(result['detail'] or result['outcome'])

    def open_result(self, item, *_):
        test = item.data(0, Qt.ItemDataRole.UserRole)
        self.navigate.emit(test['path'], test['line'])

    def finished(self, code, *_):
        self.read()
        if self.mode == 'collect' and code == 0:
            self.label.setText(f'{len(self.items)} test bulundu')
        else:
            failed = sum(result['outcome'] == 'failed' for result in self.results.values())
            self.label.setText(f'{len(self.results)} sonuç · {failed} başarısız · çıkış {code}')

    def shutdown(self):
        self.process.kill()
        self.process.waitForFinished(1000)
