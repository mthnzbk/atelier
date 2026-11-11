"""Project switching and pin management."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout


class RecentProjectsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.store = window.recent_projects
        self.selected_path = None
        self.setWindowTitle("Son projeler")
        self.resize(720, 440)
        layout = QVBoxLayout(self)
        self.listing = QListWidget()
        self.listing.setAccessibleName("Son projeler")
        self.listing.itemActivated.connect(self.open_selected)
        layout.addWidget(self.listing)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.pin_button = self.button(row, "Sabitle", self.toggle_pin)
        self.forget_button = self.button(row, "Listeden çıkar", self.forget)
        row.addStretch()
        self.open_button = self.button(row, "Projeyi aç", self.open_selected)
        self.button(row, "Kapat", self.reject)
        self.listing.currentItemChanged.connect(self.update_buttons)
        self.reload(str(window.root))

    @staticmethod
    def button(layout, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def reload(self, selected=None):
        self.listing.clear()
        for record in self.store.entries():
            path = Path(record["path"])
            star = "★ " if record["pinned"] else ""
            missing = " · Klasör bulunamadı" if not path.is_dir() else ""
            item = QListWidgetItem(f"{star}{path.name or path}  ·  {path.parent}{missing}")
            item.setData(Qt.ItemDataRole.UserRole, record)
            item.setToolTip(str(path))
            self.listing.addItem(item)
            if str(path) == selected:
                self.listing.setCurrentItem(item)
        if self.listing.count() and self.listing.currentItem() is None:
            self.listing.setCurrentRow(0)
        self.update_buttons()

    def current_record(self):
        item = self.listing.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def update_buttons(self, *_):
        record = self.current_record()
        self.pin_button.setEnabled(record is not None)
        self.forget_button.setEnabled(record is not None)
        self.open_button.setEnabled(record is not None and Path(record["path"]).is_dir())
        self.pin_button.setText("Sabitlemeyi kaldır" if record and record["pinned"] else "Sabitle")

    def toggle_pin(self):
        if record := self.current_record():
            self.store.toggle_pin(record["path"])
            self.reload(record["path"])

    def forget(self):
        if record := self.current_record():
            self.store.forget(record["path"])
            self.reload()

    def open_selected(self, *_):
        if (record := self.current_record()) and Path(record["path"]).is_dir():
            self.selected_path = record["path"]
            self.accept()
