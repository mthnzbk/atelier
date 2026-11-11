"""Interactive embedded VT terminal with a persistent project shell."""
import json
import pyte
from atelier.runtime.paths import worker_command
from atelier.ui.icons import for_text
from PySide6.QtCore import Qt, QProcess, QTimer, Signal
from PySide6.QtGui import QTextCursor, QKeySequence
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel, QApplication


class TerminalView(QPlainTextEdit):
    input = Signal(str)
    resized = Signal()

    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet('QPlainTextEdit {font-family:Consolas; font-size:11pt;}')

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste) or (event.key() == Qt.Key.Key_V and event.modifiers(
        ) & Qt.KeyboardModifier.ControlModifier and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.input.emit(QApplication.clipboard().text())
            return
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if ctrl and event.key() == Qt.Key.Key_C:
            if self.textCursor().hasSelection() or shift:
                self.copy()
            else:
                self.input.emit('\x03')
            return
        if ctrl and Qt.Key.Key_A <= event.key() <= Qt.Key.Key_Z:
            self.input.emit(chr(event.key() - Qt.Key.Key_A + 1))
            return
        mapping = {Qt.Key.Key_Return: '\r', Qt.Key.Key_Enter: '\r', Qt.Key.Key_Backspace: '\x7f',
                   Qt.Key.Key_Tab: '\t', Qt.Key.Key_Escape: '\x1b', Qt.Key.Key_Up: '\x1b[A', Qt.Key.Key_Down: '\x1b[B',
                   Qt.Key.Key_Right: '\x1b[C', Qt.Key.Key_Left: '\x1b[D', Qt.Key.Key_Home: '\x1b[H', Qt.Key.Key_End: '\x1b[F',
                   Qt.Key.Key_Delete: '\x1b[3~', Qt.Key.Key_PageUp: '\x1b[5~', Qt.Key.Key_PageDown: '\x1b[6~'}
        text = mapping.get(event.key(), event.text())
        if text:
            self.input.emit(
                ('\x1b' if event.modifiers() & Qt.KeyboardModifier.AltModifier else '') + text)

    def insertFromMimeData(self, source):
        self.input.emit(source.text())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()


class TerminalPanel(QWidget):
    received = Signal(str)

    def __init__(self, root_provider, interpreter_provider):
        super().__init__()
        self.root_provider = root_provider
        self.interpreter_provider = interpreter_provider
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.error_output)
        self.process.errorOccurred.connect(lambda _: self.label.setText(self.process.errorString()))
        self.process.finished.connect(
            lambda *_: self.label.setText('Terminal kapandı · Oturumu yeniden başlatabilirsiniz'))
        self.buffer = bytearray()
        self.ready = False
        self.prompt_idle = False
        self.expect_prompt = True
        self.input_id = 0
        self.root = None
        self.interpreter = ''
        self.terminal_size = None
        self.render_count = 0
        self.resize_timer = QTimer(self, interval=100, singleShot=True)
        self.resize_timer.timeout.connect(self.apply_resize)
        self.screen = pyte.HistoryScreen(110, 30, history=3000)
        self.stream = pyte.Stream(self.screen)
        self.render_timer = QTimer(self, interval=25, singleShot=True)
        self.render_timer.timeout.connect(self.render)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.label = QLabel('Kalıcı proje terminali · komutlar ve etkileşimli Python')
        toolbar.addWidget(self.label, 1)
        for text, callback in [('Yeniden başlat', self.restart), ('Ctrl+C', lambda: self.send_input('\x03')),
                               ('Temizle', self.clear), ('Durdur', self.shutdown)]:
            button = QPushButton(text)
            button.setIcon(for_text(text))
            button.setProperty('materialButton', True)
            button.clicked.connect(lambda checked=False, fn=callback: fn())
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.view = TerminalView()
        self.view.input.connect(self.send_input)
        self.view.resized.connect(self.resize_terminal)
        layout.addWidget(self.view)

    def start(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self.clear()
        self.ready = False
        self.prompt_idle = False
        self.expect_prompt = True
        self.input_id = 0
        self.buffer.clear()
        self.terminal_size = None
        self.root = self.root_provider()
        self.interpreter = self.interpreter_provider()
        self.label.setText('Terminal · ' + str(self.root))
        program, arguments = worker_command('terminal', str(self.root), self.interpreter)
        self.process.start(program, arguments)

    def refresh_idle_environment(self):
        if (self.ready and self.prompt_idle and self.root == self.root_provider()
                and self.interpreter != self.interpreter_provider()):
            self.shutdown()
            self.start()

    def restart(self):
        self.shutdown()
        self.start()
        self.view.setFocus()

    def send(self, message):
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.write((json.dumps(message) + '\n').encode('utf-8'))

    def send_input(self, text):
        if self.ready:
            self.prompt_idle = False
            self.expect_prompt = text.endswith(('\r', '\n', '\x03'))
            self.input_id += 1
            self.send({'input': text, 'id': self.input_id})

    def read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b'\n' in self.buffer:
            line, _, rest = self.buffer.partition(b'\n')
            self.buffer = bytearray(rest)
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get('ready'):
                self.ready = True
                self.resize_terminal()
            if self.expect_prompt and message.get('prompt') == self.input_id:
                self.prompt_idle = True
            if message.get('data'):
                text = message['data']
                self.stream.feed(text)
                self.received.emit(text)
                self.render_timer.start()
            if message.get('exited'):
                self.shutdown()
            if message.get('error'):
                self.label.setText('Terminal hatası: ' + message['error'])
                self.view.setPlainText(message['error'] +
                                       '\nBağımlılıkları requirements.txt ile güncelleyin.')

    def error_output(self):
        text = bytes(self.process.readAllStandardError()).decode('utf-8', 'replace')
        if text:
            self.label.setText(text[-250:])

    def resize_terminal(self):
        self.resize_timer.start()

    def apply_resize(self):
        columns = max(20, int(self.view.viewport().width() /
                              max(1, self.view.fontMetrics().horizontalAdvance('M'))))
        rows = max(5, int(self.view.viewport().height() / max(1, self.view.fontMetrics().height())))
        if (rows, columns) == self.terminal_size:
            return
        self.terminal_size = (rows, columns)
        self.screen.resize(lines=rows, columns=columns)
        self.send({'resize': [rows, columns]})
        self.render_timer.start()

    def render(self):
        history = [''.join(line[x].data if x in line else ' ' for x in range(self.screen.columns)).rstrip()
                   for line in self.screen.history.top]
        text = '\n'.join(history + self.screen.display)
        scrollbar = self.view.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 1
        scroll = scrollbar.value()
        selection = self.view.textCursor()
        selected = selection.hasSelection()
        anchor, position = selection.anchor(), selection.position()
        if text != self.view.toPlainText():
            self.render_count += 1
            self.view.setPlainText(text)
        block = self.view.document().findBlockByNumber(len(history) + self.screen.cursor.y)
        cursor = QTextCursor(block)
        cursor.setPosition(min(block.position() + self.screen.cursor.x,
                           block.position() + len(block.text())))
        if selected:
            maximum = self.view.document().characterCount() - 1
            cursor.setPosition(min(anchor, maximum))
            cursor.setPosition(min(position, maximum), QTextCursor.MoveMode.KeepAnchor)
        self.view.setTextCursor(cursor)
        if at_bottom and not selected:
            self.view.ensureCursorVisible()
        else:
            scrollbar.setValue(scroll)

    def clear(self):
        self.screen.reset()
        self.view.clear()

    def shutdown(self):
        self.render_timer.stop()
        self.resize_timer.stop()
        self.ready = False
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.send({'close': True})
            if not self.process.waitForFinished(900):
                self.process.kill()
                self.process.waitForFinished(500)
