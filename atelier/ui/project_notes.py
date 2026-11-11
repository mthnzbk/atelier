"""Project-wide TODO and FIXME list."""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from atelier.projects.notes import LIMIT, SUFFIXES
from atelier.runtime.tasks import TaskWorker


class ProjectNotesPanel(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.root = window.root
        self.worker = None
        self.dirty = True
        self.rows = []
        self.limited = False
        self.refresh_timer = QTimer(self, interval=700, singleShot=True)
        self.refresh_timer.timeout.connect(self.scan)

        layout = QVBoxLayout(self)
        tools = QHBoxLayout()
        self.filter = QLineEdit(placeholderText='Dosya veya not ara…')
        self.filter.textChanged.connect(self.update_list)
        tools.addWidget(self.filter, 1)
        self.kind = QComboBox()
        self.kind.addItems(['Tümü', 'TODO', 'FIXME'])
        self.kind.currentTextChanged.connect(self.update_list)
        tools.addWidget(self.kind)
        window.button(tools, 'Yenile', lambda: self.invalidate(delay=0))
        layout.addLayout(tools)
        self.listing = QTreeWidget()
        self.listing.setRootIsDecorated(False)
        self.listing.setHeaderLabels(['Tür', 'Not', 'Dosya', 'Satır'])
        self.listing.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.listing.itemClicked.connect(self.open_note)
        self.listing.itemActivated.connect(self.open_note)
        layout.addWidget(self.listing)
        self.status = QLabel()
        layout.addWidget(self.status)

    def showEvent(self, event):
        super().showEvent(event)
        self.invalidate(delay=0)

    def invalidate(self, *, delay=700):
        self.dirty = True
        if self.isVisible() and self.worker is None and not self.window.closing:
            self.refresh_timer.start(delay)

    def source_changed(self, doc):
        if doc.path and doc.path.suffix.lower() in SUFFIXES and doc.path.is_relative_to(self.root):
            self.invalidate()

    def set_project(self, root):
        if self.root != root:
            self.refresh_timer.stop()
            if self.worker:
                self.worker.requestInterruption()
            self.root = root
            self.rows = []
            self.limited = False
            self.update_list()
        self.invalidate(delay=0)

    def scan(self):
        if not self.dirty or self.worker or not self.isVisible() or self.window.closing:
            return
        self.dirty = False
        overlays = {}
        for doc in self.window.documents:
            if (doc.path and doc.path.suffix.lower() in SUFFIXES and doc.path.is_relative_to(self.root)
                    and not doc.large_file):
                overlays[str(doc.path)] = doc.editor.toPlainText()
        worker = self.worker = TaskWorker('notes', dict(root=str(self.root), overlays=overlays), self, 25000)
        self.status.setText('Proje notları aranıyor…')
        worker.results.connect(self.scan_result)
        worker.error.connect(self.status.setText)
        worker.finished.connect(self.scan_finished)
        worker.start()

    def scan_result(self, result):
        if not self.dirty and not self.window.closing:
            self.rows = sorted(result['rows'], key=lambda row: (row['path'].casefold(), row['line'], row['character']))
            self.limited = result['limited']
            self.update_list()

    def scan_finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        if self.dirty and not self.window.closing:
            self.invalidate(delay=0)

    def update_list(self, *_):
        self.listing.clear()
        query = self.filter.text().casefold().strip()
        kind = self.kind.currentText()
        for row in self.rows:
            if kind != 'Tümü' and kind != row['kind']:
                continue
            relative = Path(row['path']).relative_to(self.root).as_posix()
            if query and query not in f'{relative} {row["text"]}'.casefold():
                continue
            item = QTreeWidgetItem([row['kind'], row['text'], relative, str(row['line'] + 1)])
            item.setData(0, Qt.ItemDataRole.UserRole, row)
            item.setToolTip(1, row['text'])
            item.setToolTip(2, relative)
            self.listing.addTopLevelItem(item)
        count = self.listing.topLevelItemCount()
        limit = f' · İlk {LIMIT} not tarandı' if self.limited else ''
        self.status.setText(f'{count} not{limit}' if count or self.rows else 'TODO veya FIXME bulunamadı.')

    def open_note(self, item, *_):
        row = item.data(0, Qt.ItemDataRole.UserRole)
        self.window.remember_location()
        doc = self.window.open_path(row['path'])
        if doc:
            self.window.goto(doc, {'line': row['line'], 'character': row['character']}, record=False)
            self.window.remember_location()
        else:
            self.invalidate(delay=0)

    def shutdown(self):
        self.refresh_timer.stop()
        if self.worker:
            self.worker.requestInterruption()
            if self.worker:
                self.worker.wait()
