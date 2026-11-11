import os
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt, QEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
from atelier.projects.scan import IGNORED
from atelier.search.patterns import fuzzy_score


class FileIndex(QThread):
    ready = Signal(list)

    def __init__(self, root, parent):
        super().__init__(parent)
        self.root = Path(root)

    def run(self):
        found = []
        for folder, dirs, files in os.walk(self.root):
            if self.isInterruptionRequested():
                return
            dirs[:] = [d for d in dirs if d not in IGNORED and not Path(folder, d).is_symlink()]
            for name in files:
                path = Path(folder, name)
                if not path.is_symlink():
                    found.append(str(path.relative_to(self.root)))
            if len(found) >= 30000:
                break
        self.ready.emit(found)


class QuickOpen(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.paths = []
        self.setWindowTitle('Hızlı dosya aç · Ctrl+P')
        self.resize(740, 500)
        layout = QVBoxLayout(self)
        self.query = QLineEdit(placeholderText='Dosya adı veya yolun birkaç harfi…')
        self.listing = QListWidget()
        layout.addWidget(self.query)
        layout.addWidget(self.listing)
        self.query.textChanged.connect(self.filter)
        self.query.returnPressed.connect(self.open_selected)
        self.query.installEventFilter(self)
        self.listing.itemActivated.connect(lambda _: self.open_selected())
        self.worker = FileIndex(window.root, self)
        self.worker.ready.connect(self.loaded)
        self.worker.start()

    def loaded(self, paths):
        self.paths = paths
        self.filter()

    def filter(self, *_):
        self.listing.clear()
        ranked = [
            (score,
             path) for path in self.paths if (
                score := fuzzy_score(
                    self.query.text(),
                    path)) is not None]
        for _, path in sorted(ranked, key=lambda pair: (-pair[0], pair[1]))[:100]:
            item = QListWidgetItem(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.listing.addItem(item)
        if self.listing.count():
            self.listing.setCurrentRow(0)

    def open_selected(self):
        item = self.listing.currentItem()
        if item:
            self.window.open_path(self.window.root / item.data(Qt.ItemDataRole.UserRole))
            self.accept()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            if self.listing.count():
                self.listing.setCurrentRow(
                    (self.listing.currentRow() + (1 if event.key() == Qt.Key.Key_Down else -1)) % self.listing.count())
            return True
        return super().eventFilter(watched, event)

    def done(self, result):
        self.worker.requestInterruption()
        self.worker.wait()
        super().done(result)
