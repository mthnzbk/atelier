from pathlib import Path
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem


class CommandPalette(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Komut paleti')
        self.resize(650, 460)
        self.actions = [action for action in window.actions.values() if not action.isSeparator()]
        try:
            from atelier.projects.config import load_project_config
            self.tasks = load_project_config(window.root)['tasks']
        except ValueError as error:
            self.tasks = {}
            window.statusBar().showMessage(str(error), 8000)
        layout = QVBoxLayout(self)
        self.query = QLineEdit(placeholderText='Bir komut arayın…')
        self.listing = QListWidget()
        layout.addWidget(self.query)
        layout.addWidget(self.listing)
        self.query.textChanged.connect(self.filter)
        self.query.installEventFilter(self)
        self.query.returnPressed.connect(self.execute)
        self.listing.itemActivated.connect(lambda _: self.execute())
        self.filter('')

    def eventFilter(self, watched, event):
        if watched is self.query and event.type() == QEvent.Type.KeyPress and event.key() in (
                Qt.Key.Key_Down, Qt.Key.Key_Up):
            if self.listing.count():
                delta = 1 if event.key() == Qt.Key.Key_Down else -1
                self.listing.setCurrentRow(
                    (self.listing.currentRow() + delta) %
                    self.listing.count())
            return True
        return super().eventFilter(watched, event)

    def filter(self, text):
        self.listing.clear()
        terms = text.casefold().split()
        for action in self.actions:
            label = action.text().replace('&', '')
            if all(term in label.casefold() for term in terms):
                shortcut = action.shortcut().toString()
                item = QListWidgetItem(label + ('     ' + shortcut if shortcut else ''))
                item.setData(Qt.ItemDataRole.UserRole, action)
                self.listing.addItem(item)
        for key, task in self.tasks.items():
            label = 'Proje komutu · ' + task['label']
            if all(term in (label + ' ' + key).casefold() for term in terms):
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.listing.addItem(item)
        for project in self.window.recent_projects.entries():
            path = Path(project['path'])
            if not path.is_dir():
                continue
            star = '★ ' if project['pinned'] else ''
            label = f'Proje aç · {star}{path.name or path}  ·  {path.parent}'
            if all(term in label.casefold() for term in terms):
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, ('project', str(path)))
                self.listing.addItem(item)
        if self.listing.count():
            self.listing.setCurrentRow(0)

    def execute(self):
        item = self.listing.currentItem()
        if item:
            action = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
            if isinstance(action, str):
                self.window.run_project_task(action)
            elif isinstance(action, (tuple, list)) and action[0] == 'project':
                self.window.open_recent_project(action[1])
            else:
                action.trigger()
