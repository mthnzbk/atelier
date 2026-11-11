from PySide6.QtCore import QItemSelectionModel, Qt, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QAbstractItemView


class BreakpointPanel(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Kesme noktaları')
        self.resize(800, 450)
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Dosya', 'Satır', 'Koşul'])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setColumnWidth(0, 400)
        layout.addWidget(self.tree)
        row = QHBoxLayout()
        layout.addLayout(row)
        for title, callback in [('Konuma git', self.navigate), ('Koşulu düzenle', self.condition),
                                ('Seçileni kaldır', self.remove), ('Tümünü kaldır', self.remove_all)]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        self.tree.itemDoubleClicked.connect(self.navigate)
        self.timer = QTimer(self, interval=300)
        self.timer.timeout.connect(self.refresh)
        self.snapshot = None
        self.refresh()
        self.timer.start()

    def refresh(self):
        snapshot = [(str(doc.path) if doc.path else doc, line, doc.breakpoint_conditions.get(line, ''))
                    for doc in self.window.documents for line in sorted(doc.breakpoints)]
        snapshot.extend((path, line, condition) for path, points in sorted(self.window.closed_breakpoints.items())
                        for line, condition in sorted(points.items()))
        if snapshot == self.snapshot:
            return
        selected = {item.data(0, Qt.ItemDataRole.UserRole) for item in self.tree.selectedItems()}
        self.snapshot = snapshot
        self.tree.clear()
        for target, line, condition in snapshot:
            name = target if isinstance(target, str) else 'Adsız.py'
            item = QTreeWidgetItem(self.tree, [name, str(line), condition or 'Koşulsuz'])
            item.setData(0, Qt.ItemDataRole.UserRole, (target, line))
            if (target, line) in selected:
                item.setSelected(True)
                self.tree.setCurrentItem(item, 0, QItemSelectionModel.SelectionFlag.NoUpdate)

    def open_target(self, target):
        if isinstance(target, str):
            doc = self.window.open_path(target)
            if doc is None:
                self.window.message('Kesme noktasının dosyası açılamadı.')
            return doc
        return target if target in self.window.documents else None

    def navigate(self, *_):
        if item := self.tree.currentItem():
            target, line = item.data(0, Qt.ItemDataRole.UserRole)
            if doc := self.open_target(target):
                self.window.goto(doc, dict(line=line - 1, character=0))

    def condition(self):
        if item := self.tree.currentItem():
            target, line = item.data(0, Qt.ItemDataRole.UserRole)
            if (doc := self.open_target(target)) and 1 <= line <= doc.editor.blockCount():
                self.window.edit_breakpoint_condition(doc, line)
                self.refresh()

    def remove(self):
        for item in self.tree.selectedItems():
            target, line = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(target, str) and target in self.window.closed_breakpoints:
                self.window.remove_closed_breakpoint(target, line)
                continue
            doc = next(
                (doc for doc in self.window.documents if str(
                    doc.path) == target),
                None) if isinstance(
                target,
                str) else target
            if doc in self.window.documents and line in doc.breakpoints:
                self.window.toggle_breakpoint(doc, line)
        self.refresh()

    def remove_all(self):
        for doc in self.window.documents:
            for line in list(doc.breakpoints):
                self.window.toggle_breakpoint(doc, line)
        for path, points in list(self.window.closed_breakpoints.items()):
            for line in list(points):
                self.window.remove_closed_breakpoint(path, line)
        self.refresh()

    def done(self, result):
        self.timer.stop()
        super().done(result)
