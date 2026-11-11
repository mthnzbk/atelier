"""Edit the shared project command definitions without rewriting other settings."""
from pathlib import Path
import re
import shlex
import unicodedata

from PySide6.QtCore import QIODevice, QSaveFile, Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from atelier.projects.config import FILENAME, command_settings, tomllib, validate_project_config


class ProjectTasksDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.root = window.root
        self.path = self.root / FILENAME
        self.snapshot = self.read_config()
        self.tasks = self.parse_tasks(self.snapshot)
        self.selected_task = None
        self.setWindowTitle('Proje komutları')
        self.resize(700, 440)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f'{self.root.name} · {FILENAME}'))
        self.listing = QListWidget()
        self.listing.setAccessibleName('Proje komutları')
        self.listing.itemDoubleClicked.connect(lambda _: self.edit_selected())
        layout.addWidget(self.listing)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.button(row, 'Yeni komut…', lambda: self.edit_task())
        self.edit_button = self.button(row, 'Düzenle…', self.edit_selected)
        self.delete_button = self.button(row, 'Sil', self.delete_selected)
        row.addStretch()
        self.run_button = self.button(row, 'Çalıştır', self.run_selected)
        self.button(row, 'Kapat', self.reject)
        self.listing.currentItemChanged.connect(self.update_buttons)
        self.populate()

    def button(self, layout, label, callback):
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def read_config(self):
        if self.path.is_symlink():
            raise ValueError(f'{FILENAME} bir sembolik bağlantı.')
        try:
            return self.path.read_bytes()
        except FileNotFoundError:
            return None

    @staticmethod
    def parse_tasks(source):
        data = tomllib.loads(source.decode('utf-8')) if source is not None else {}
        return validate_project_config(data)['tasks']

    def populate(self, selected=None):
        self.listing.clear()
        for key, task in self.tasks.items():
            item = QListWidgetItem(task['label'])
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(shlex.join(task['args']) + '\n' + task['cwd'])
            self.listing.addItem(item)
            if key == selected:
                self.listing.setCurrentItem(item)
        if self.listing.currentItem() is None and self.listing.count():
            self.listing.setCurrentRow(0)
        self.update_buttons()

    def current_key(self):
        item = self.listing.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def update_buttons(self, *_):
        selected = self.current_key() is not None
        for button in (self.edit_button, self.delete_button, self.run_button):
            button.setEnabled(selected)

    def edit_selected(self):
        if self.current_key() is not None:
            self.edit_task(self.current_key())

    def edit_task(self, key=None):
        task = self.tasks[key] if key is not None else {'label': '', 'args': [], 'cwd': '.'}
        form = QDialog(self)
        form.setWindowTitle('Proje komutunu düzenle' if key is not None else 'Yeni proje komutu')
        form.resize(610, 280)
        layout = QFormLayout(form)
        label = QLineEdit(task['label'])
        args = QPlainTextEdit(shlex.join(task['args']))
        args.setPlaceholderText('-m pytest tests -x -q')
        args.setToolTip('Boşluk içeren argümanları tırnak içine alın.')
        cwd = QLineEdit(task['cwd'])
        folder = QHBoxLayout()
        folder.addWidget(cwd, 1)

        def choose_folder():
            selected = QFileDialog.getExistingDirectory(form, 'Çalışma klasörü', str(self.root))
            if selected:
                path = Path(selected).resolve()
                if path.is_relative_to(self.root):
                    cwd.setText(path.relative_to(self.root).as_posix())
                else:
                    QMessageBox.warning(form, 'Proje komutu', 'Proje içinde bir klasör seçin.')

        self.button(folder, 'Gözat…', choose_folder)
        layout.addRow('Ad', label)
        layout.addRow('Python argümanları', args)
        layout.addRow('Çalışma klasörü', folder)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons)

        def save():
            try:
                title = label.text().strip()
                if not title:
                    raise ValueError('Komuta bir ad verin.')
                values = dict(
                    label=title,
                    args=shlex.split(
                        args.toPlainText()),
                    cwd=cwd.text().strip() or '.')
                task_key = key if key is not None else self.new_key(title)
                self.save_change(task_key, values)
            except (OSError, ValueError) as error:
                QMessageBox.warning(form, 'Proje komutu', str(error))
                return
            form.accept()

        buttons.accepted.connect(save)
        buttons.rejected.connect(form.reject)
        form.exec()
        form.deleteLater()

    def new_key(self, label):
        normalized = unicodedata.normalize('NFKD', label.casefold())
        ascii_label = normalized.encode('ascii', 'ignore').decode('ascii')
        base = re.sub(r'[^a-z0-9]+', '-', ascii_label).strip('-') or 'komut'
        key, number = base, 2
        while key in self.tasks:
            key = f'{base}-{number}'
            number += 1
        return key

    def delete_selected(self):
        key = self.current_key()
        if key is None:
            return
        answer = QMessageBox.question(
            self, 'Proje komutunu sil', f'“{
                self.tasks[key]["label"]}” silinsin mi?')
        if answer == QMessageBox.StandardButton.Yes:
            try:
                self.save_change(key, None)
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, 'Proje komutu', str(error))

    def save_change(self, key, values):
        try:
            import tomlkit
        except ModuleNotFoundError as error:
            raise ValueError(
                'Komut düzenleyicisi için python -m pip install -r requirements.txt çalıştırın.') from error
        if self.window.root != self.root:
            raise ValueError('Proje değişti. Proje komutlarını yeniden açın.')
        doc = next((doc for doc in self.window.documents if doc.path == self.path), None)
        if doc and doc.editor.document().isModified():
            raise ValueError(
                f'Önce editördeki {FILENAME} değişikliklerini kaydedin veya geri alın.')
        if self.read_config() != self.snapshot:
            raise ValueError(f'{FILENAME} değişti. Proje komutlarını yeniden açın.')
        config = tomlkit.parse((self.snapshot or b'').decode('utf-8'))
        if 'tasks' not in config:
            config['tasks'] = tomlkit.table()
        tasks = config['tasks']
        if values is None:
            del tasks[key]
        else:
            settings = command_settings(values, f'tasks.{key}')
            directory = (self.root / settings['cwd']).resolve()
            if not directory.is_relative_to(self.root) or not directory.is_dir():
                raise ValueError('Çalışma klasörü proje içinde ve mevcut olmalı.')
            if key not in tasks:
                from tomlkit.items import InlineTable
                tasks[key] = tomlkit.inline_table() if isinstance(
                    tasks, InlineTable) else tomlkit.table()
            entry = tasks[key]
            for name in ('label', 'args', 'cwd'):
                if entry.get(name) != settings[name]:
                    entry[name] = settings[name]
        updated = tomlkit.dumps(config).encode('utf-8')
        parsed = self.parse_tasks(updated)
        writer = QSaveFile(str(self.path))
        if not writer.open(QIODevice.OpenModeFlag.WriteOnly):
            raise OSError(writer.errorString())
        if writer.write(updated) != len(updated):
            writer.cancelWriting()
            raise OSError(writer.errorString())
        if self.read_config() != self.snapshot:
            writer.cancelWriting()
            raise ValueError(f'{FILENAME} değişti. Proje komutlarını yeniden açın.')
        if not writer.commit():
            raise OSError(writer.errorString())
        self.snapshot, self.tasks = updated, parsed
        self.populate(key)
        if doc:
            self.window.reload_document(doc, confirm=False)
        self.window.git_refresh_timer.start()

    def run_selected(self):
        if self.current_key() is not None:
            self.selected_task = self.current_key()
            self.accept()
