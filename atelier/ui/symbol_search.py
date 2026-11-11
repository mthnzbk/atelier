"""Project-wide Python symbols, including unsaved open documents."""
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel, QPushButton
from atelier.runtime.tasks import TaskWorker
from atelier.search.patterns import fuzzy_score


class SymbolSearch(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.root, self.rows = window, window.root, []
        self.setWindowTitle('Projede sembol ara · Ctrl+T')
        self.resize(820, 530)
        layout = QVBoxLayout(self)
        self.query = QLineEdit(placeholderText='Fonksiyon, sınıf veya Class.method…')
        self.listing, self.status = QListWidget(), QLabel('Proje taranıyor…')
        layout.addWidget(self.query)
        layout.addWidget(self.listing)
        layout.addWidget(self.status)
        cancel = QPushButton('Taramayı durdur')
        layout.addWidget(cancel)
        self.timer = QTimer(self, singleShot=True, interval=100)
        self.query.textChanged.connect(lambda _: self.timer.start())
        self.timer.timeout.connect(self.filter)
        self.query.returnPressed.connect(self.open_selected)
        self.listing.itemActivated.connect(self.open_selected)
        overlays = {str(doc.path): doc.editor.toPlainText() for doc in window.documents
                    if doc.path and not doc.large_file and doc.language == 'python' and self.root in doc.path.parents}
        self.worker = TaskWorker('symbols', dict(root=str(self.root), overlays=overlays), self)
        self.worker.results.connect(self.loaded)
        self.worker.error.connect(self.status.setText)
        self.worker.finished.connect(lambda: cancel.setEnabled(False))
        cancel.clicked.connect(
            lambda: (
                self.worker.requestInterruption(),
                self.status.setText('Tarama durduruldu.')))
        self.worker.start()

    def loaded(self, result):
        self.rows = result['rows']
        self.filter()
        self.status.setText(f'{len(self.rows)} sembol · {result["skipped"]} okunamayan/hatalı dosya' + (
            ' · tarama sınırına ulaşıldı' if result['limited'] else ''))

    def filter(self):
        self.listing.clear()
        ranked = [
            (score,
             row) for row in self.rows if (
                score := fuzzy_score(
                    self.query.text(),
                    row['name'])) is not None]
        for _, row in sorted(ranked, key=lambda pair: (-pair[0], pair[1]['name']))[:200]:
            item = QListWidgetItem(
                f'{
                    row["kind"]} {
                    row["name"]}  —  {
                    Path(
                        row["path"]).relative_to(
                        self.root)}:{
                            row["line"] +
                    1}')
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.listing.addItem(item)
        if self.listing.count():
            self.listing.setCurrentRow(0)

    def open_selected(self, *_):
        item = self.listing.currentItem()
        if item and self.window.root == self.root:
            row = item.data(Qt.ItemDataRole.UserRole)
            doc = self.window.open_path(row['path'])
            if doc:
                self.window.goto(doc, dict(line=row['line'], character=row['character']))
                self.accept()

    def done(self, result):
        self.timer.stop()
        self.worker.requestInterruption()
        self.worker.wait(1000)
        super().done(result)
