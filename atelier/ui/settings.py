import json
import shutil
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QCheckBox, QSpinBox, QLineEdit,
                               QComboBox, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, QKeySequenceEdit, QFontComboBox, QLabel, QPushButton)
from PySide6.QtGui import QFont
from PySide6.QtCore import QSize
from atelier.ui.theme import PALETTES


class SettingsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Ayarlar')
        self.resize(830, 580)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        def page(title):
            widget = QWidget()
            form = QFormLayout(widget)
            tabs.addTab(widget, title)
            return form

        def check(form, label, value):
            widget = QCheckBox()
            widget.setChecked(value)
            form.addRow(label, widget)
            return widget

        def spin(form, label, value, low, high):
            widget = QSpinBox()
            widget.setRange(low, high)
            widget.setValue(value)
            form.addRow(label, widget)
            return widget
        editor = page('Editör')
        self.indent = spin(editor, 'Girinti genişliği', window.tab_width, 2, 8)
        self.delay = spin(editor, 'Tamamlama gecikmesi (ms)', window.completion_delay, 50, 1500)
        self.auto = check(editor, 'Yazarken tamamlama', window.auto_complete)
        self.restore = check(
            editor,
            'Açılışta son proje oturumunu geri yükle',
            window.restore_enabled)
        self.recovery = check(editor, 'Otomatik kurtarma', window.autorecovery_enabled)
        look = page('Görünüm')
        self.theme = QComboBox()
        self.theme.addItems(PALETTES)
        self.theme.setCurrentText(window.theme)
        look.addRow('Tema', self.theme)
        self.family = QFontComboBox()
        self.family.setCurrentFont(QFont(window.font_family))
        look.addRow('Yazı tipi', self.family)
        self.size = spin(look, 'Yazı boyutu', window.font_size, 9, 28)
        self.guide = check(look, 'Yalnızca etkin bloğun kılavuzu', window.active_guide)
        self.minimap = check(look, 'Minimap', window.minimap_visible)
        python = page('Python')
        python.addRow(QLabel('Bu proje: ' + str(window.root)))
        self.interpreter = QLineEdit(window.interpreter)
        python.addRow('Python yolu', self.interpreter)
        manage = QPushButton('Python ortamları ve paketleri yönet…')

        def open_environments():
            window.manage_python()
            self.interpreter.setText(window.interpreter)
        manage.clicked.connect(open_environments)
        python.addRow(manage)
        self.args = QLineEdit(window.run_args)
        python.addRow('Çalıştırma argümanları', self.args)
        self.refresh_terminal = check(python, 'Python değişince boşta olan terminali yenile',
                                      window.refresh_idle_terminal)
        self.format_save = check(python, 'Kaydederken Python biçimlendir', window.format_on_save)
        self.format_web_save = check(
            python,
            'Kaydederken HTML, CSS, JavaScript ve JSON biçimlendir',
            window.format_web_on_save)
        self.import_save = check(python, 'Kaydederken importları düzenle', window.save_imports)
        self.trim_save = check(python, 'Satır sonundaki boşlukları temizle', window.save_trim)
        self.newline_save = check(python, 'Dosya sonuna satır sonu ekle', window.save_final_newline)
        python.addRow(QLabel('Kayıt işlemleri bu proje için saklanır.'))
        git = page('Git')
        self.git_enabled = check(git, 'Git etkin', window.git_enabled)
        self.git_path = QLineEdit(window.git_executable or shutil.which('git') or '')
        git.addRow('Git yolu (boş: PATH)', self.git_path)
        self.git_interval = spin(git, 'Yenileme aralığı (saniye)', window.git_interval, 2, 120)
        tests = page('Testler')
        self.test_args = QLineEdit(window.test_args)
        tests.addRow('Proje pytest argümanları', self.test_args)
        self.coverage = check(tests, 'Çalıştırırken test kapsamını ölç', window.coverage_enabled)
        tests.addRow(QLabel('Seçili Python ortamında coverage paketi gerekir.'))
        shortcuts = QTreeWidget()
        shortcuts.setHeaderLabels(['İşlem', 'Kısayol'])
        tabs.addTab(shortcuts, 'Kısayollar')
        self.keys = {}
        for key, action in window.actions.items():
            item = QTreeWidgetItem(shortcuts, [action.text(), ''])
            edit = QKeySequenceEdit(action.shortcut())
            shortcuts.setItemWidget(item, 1, edit)
            self.keys[key] = edit
            edit.setMinimumHeight(38)
            edit.setStyleSheet(
                'QKeySequenceEdit {background:palette(base);border:1px solid palette(mid);border-radius:5px;padding:2px;} QKeySequenceEdit QLineEdit {background:transparent;color:palette(text);border:0;min-height:26px;padding:3px 8px;}')
            item.setSizeHint(1, QSize(240, 46))
        shortcuts.setColumnWidth(0, 390)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        w = self.window
        from atelier.projects.environments import valid_python_path
        entered = self.interpreter.text().strip()
        if entered and not valid_python_path(entered):
            w.message('Python yolu bulunamadı.')
            return
        seen = {}
        for key, edit in self.keys.items():
            value = edit.keySequence().toString()
            if value and value in seen:
                w.message('Çakışan kısayol: ' + value)
                return
            if value:
                seen[value] = key
        w.tab_width, w.completion_delay = self.indent.value(), self.delay.value()
        w.auto_complete, w.restore_enabled, w.autorecovery_enabled = self.auto.isChecked(
        ), self.restore.isChecked(), self.recovery.isChecked()
        w.theme, w.font_family, w.font_size = self.theme.currentText(
        ), self.family.currentFont().family(), self.size.value()
        w.active_guide, w.minimap_visible = self.guide.isChecked(), self.minimap.isChecked()
        previous = w.interpreter
        if entered != previous:
            w.python_preference = valid_python_path(entered)
        w.resolve_python_environment()
        changed = previous != w.interpreter
        w.run_args, w.test_args = self.args.text(), self.test_args.text()
        w.git_enabled, w.git_executable, w.git_interval = self.git_enabled.isChecked(
        ), self.git_path.text(), self.git_interval.value()
        w.coverage_enabled, w.format_on_save = self.coverage.isChecked(), self.format_save.isChecked()
        w.refresh_idle_terminal = self.refresh_terminal.isChecked()
        w.format_web_on_save = self.format_web_save.isChecked()
        w.save_imports, w.save_trim, w.save_final_newline = self.import_save.isChecked(
        ), self.trim_save.isChecked(), self.newline_save.isChecked()
        w.store_save_actions()
        for key in ['tab_width', 'completion_delay', 'auto_complete', 'restore_enabled', 'autorecovery_enabled', 'theme', 'font_family', 'font_size', 'active_guide',
                    'git_enabled', 'git_executable', 'git_interval', 'coverage_enabled']:
            w.settings.setValue(key, getattr(w, key))
        w.settings.setValue('restore_session', w.restore_enabled)
        w.settings.setValue('autorecovery', w.autorecovery_enabled)
        w.settings.setValue('minimap', w.minimap_visible)
        w.settings.setValue('refresh_idle_terminal', w.refresh_idle_terminal)
        mapping = {key: edit.keySequence().toString() for key, edit in self.keys.items()}
        w.settings.setValue('shortcuts', json.dumps(mapping))
        for key, value in mapping.items():
            w.actions[key].setShortcut(value)
        w.actions['format_save'].setChecked(w.format_on_save)
        w.project_profiles.save(w.root, w.python_preference, w.run_args, w.test_args)
        w.git_timer.setInterval(w.git_interval * 1000)
        for doc in w.documents:
            doc.completion_timer.setInterval(w.completion_delay)
        w.apply_theme()
        if changed:
            w.start_lsp()
        w.refresh_git()
        self.accept()
