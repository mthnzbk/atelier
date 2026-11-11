"""Python selection and language-server diagnostics."""
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout

from atelier.projects.environments import clean_environment, python_selection_details


class PythonStatusDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Python durumu')
        self.resize(700, 350)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.fields = {}
        for name in ('Yorumlayıcı', 'Python sürümü', 'Seçim nedeni', 'Dil sunucusu'):
            field = QLineEdit(readOnly=True)
            form.addRow(name, field)
            self.fields[name] = field
        self.details = QPlainTextEdit(readOnly=True)
        self.details.setPlaceholderText('Ortam ve dil sunucusu ayrıntıları')
        layout.addWidget(self.details)
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        window.button(buttons, 'Proje ortamını hazırla…', self.prepare_project)
        window.button(buttons, 'Python seç…', self.choose_python)
        window.button(buttons, 'Yeniden tara', self.rescan)
        window.button(buttons, 'LSP’yi yeniden başlat', window.start_lsp)
        buttons.addStretch()
        window.button(buttons, 'Kapat', self.accept)
        self.probe = QProcess(self)
        self.probe.setProcessEnvironment(clean_environment())
        self.probe.finished.connect(self.probe_finished)
        self.probe.errorOccurred.connect(self.probe_failed)
        self.timeout = QTimer(self, interval=5000, singleShot=True)
        self.timeout.timeout.connect(self.probe_timeout)
        self.probe_error = ''
        self.issues = []
        window.python_status_changed.connect(self.refresh_details)
        self.refresh_environment()

    def choose_python(self):
        self.window.manage_python()
        self.refresh_environment()

    def prepare_project(self):
        self.window.manage_python(prepare=True)
        self.refresh_environment()

    def rescan(self):
        self.window.rescan_python()
        self.refresh_environment()

    def refresh_environment(self):
        self.stop_probe()
        window = self.window
        if window.project_trusted:
            reason, self.issues = python_selection_details(
                window.root, window.interpreter, window.python_preference,
                window.settings.value('interpreter', ''))
        else:
            reason, self.issues = 'Proje güveni gerekli', []
        self.probe_error = ''
        self.fields['Yorumlayıcı'].setText(window.interpreter)
        self.fields['Seçim nedeni'].setText(reason)
        self.fields['Python sürümü'].setText('Sorgulanıyor…' if window.interpreter else '—')
        self.refresh_details()
        if window.interpreter:
            self.timeout.start()
            self.probe.start(window.interpreter, ['-I', '--version'])

    def refresh_details(self):
        lsp = self.window.lsp
        self.fields['Dil sunucusu'].setText(self.window.lsp_label.text().lstrip('● '))
        self.details.setPlainText('\n\n'.join(filter(None, [
            *self.issues, self.probe_error, lsp.last_error, lsp.stderr,
        ])))

    def probe_finished(self, code, _):
        self.timeout.stop()
        output = bytes(self.probe.readAllStandardOutput()).decode('utf-8', 'replace').strip()
        error = bytes(self.probe.readAllStandardError()).decode('utf-8', 'replace').strip()
        if code == 0 and (output or error):
            self.fields['Python sürümü'].setText(output or error)
        elif not self.probe_error:
            self.show_probe_error(error or f'Python sorgusu başarısız oldu (çıkış kodu {code}).')

    def probe_failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timeout.stop()
            self.show_probe_error(self.probe.errorString())

    def probe_timeout(self):
        self.show_probe_error('Python sürüm sorgusu 5 saniyede yanıt vermedi.')
        self.probe.kill()

    def show_probe_error(self, error):
        self.probe_error = error
        self.fields['Python sürümü'].setText('Okunamadı')
        self.refresh_details()

    def stop_probe(self):
        self.timeout.stop()
        if self.probe.state() != QProcess.ProcessState.NotRunning:
            self.probe.kill()
            self.probe.waitForFinished(1000)

    def done(self, result):
        self.stop_probe()
        super().done(result)
