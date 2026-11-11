import json
import os
import re
from pathlib import Path
from atelier.runtime.paths import python_tool_command
from PySide6.QtCore import QProcess, QTimer, Signal


class Lsp(QProcess):
    ready = Signal()
    diagnostics = Signal(dict)
    status = Signal(str)

    def __init__(self, parent, root=None, interpreter=None):
        super().__init__(parent)
        self.buffer = bytearray()
        self.sequence = 0
        self.pending = {}
        self.initialized = False
        self.last_error = ''
        self.stderr = ''
        self.startup_timer = QTimer(self, singleShot=True, interval=20000)
        self.startup_timer.timeout.connect(self.startup_timeout)
        self.root = Path(root or Path.cwd()).resolve()
        self.interpreter = interpreter
        self.readyReadStandardOutput.connect(self.read_messages)
        self.readyReadStandardError.connect(self.read_errors)
        self.errorOccurred.connect(self.process_error)
        self.finished.connect(self.ended)
        self.started.connect(self.initialize)

    def start_server(self):
        from atelier.projects.environments import clean_environment
        program, arguments = python_tool_command('lsp', self.interpreter)
        self.setProcessEnvironment(clean_environment())
        self.setProgram(program)
        self.setArguments(arguments)
        self.startup_timer.start()
        self.start()

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.startup_timer.stop()
            self.last_error = 'LSP başlatılamadı: ' + self.errorString()
            self.status.emit(self.last_error)

    def startup_timeout(self):
        self.last_error = 'LSP başlatılamadı: Dil sunucusu 20 saniyede yanıt vermedi.'
        self.status.emit(self.last_error)
        self.kill()

    def read_errors(self):
        message = bytes(self.readAllStandardError()).decode('utf-8', 'replace').strip()
        if message:
            self.stderr = (self.stderr + '\n' + message).strip()[-6000:]
            self.status.emit(message[-300:])

    def ended(self, code, _):
        self.startup_timer.stop()
        self.initialized = False
        self.pending.clear()
        if not self.last_error:
            self.last_error = f'LSP durdu (çıkış kodu {code}).'
        self.status.emit(self.last_error)

    def send(self, message):
        payload = json.dumps({'jsonrpc': '2.0', **message}, ensure_ascii=False).encode('utf-8')
        self.write(f'Content-Length: {len(payload)}\r\n\r\n'.encode('ascii') + payload)

    def notify(self, method, params):
        self.send({'method': method, 'params': params})

    def request(self, method, params, callback):
        self.sequence += 1
        self.pending[self.sequence] = callback
        self.send({'id': self.sequence, 'method': method, 'params': params})

    def initialize(self):
        self.request('initialize', {
            'processId': os.getpid(), 'rootUri': self.root.as_uri(),
            'capabilities': {'general': {'positionEncodings': ['utf-16']},
                             'textDocument': {'completion': {'completionItem': {'snippetSupport': False}}}}
        }, self.on_initialized)

    def on_initialized(self, result):
        self.startup_timer.stop()
        self.notify('initialized', {})
        self.notify('workspace/didChangeConfiguration', {'settings': {'pylsp': {'plugins': {
            'jedi': {'environment': self.interpreter},
            'jedi_completion': {'enabled': True, 'include_params': False},
            'autopep8': {'enabled': True}, 'yapf': {'enabled': False},
            'black': {'enabled': False},
            'pyflakes': {'enabled': True}, 'pycodestyle': {'enabled': True}}}}})
        self.initialized = True
        self.status.emit('LSP hazır')
        self.ready.emit()

    def read_messages(self):
        self.buffer.extend(bytes(self.readAllStandardOutput()))
        while b'\r\n\r\n' in self.buffer:
            header, body = bytes(self.buffer).split(b'\r\n\r\n', 1)
            match = re.search(rb'Content-Length:\s*(\d+)', header, re.I)
            if not match:
                self.buffer.clear()
                return
            length = int(match[1])
            if len(body) < length:
                return
            del self.buffer[:len(header) + 4 + length]
            try:
                message = json.loads(body[:length])
            except (ValueError, UnicodeError):
                continue
            if 'method' in message and 'id' in message:
                self.send({'id': message['id'], 'error': {
                          'code': -32601, 'message': 'Unsupported request'}})
            elif message.get('method') == 'textDocument/publishDiagnostics':
                self.diagnostics.emit(message['params'])
            elif 'id' in message:
                callback = self.pending.pop(message['id'], None)
                if 'error' in message:
                    self.status.emit(str(message['error'].get('message', 'LSP hatası')))
                elif callback:
                    callback(message.get('result'))

    def stop(self):
        self.startup_timer.stop()
        if self.state() == QProcess.ProcessState.NotRunning:
            return
        if self.initialized:
            self.request('shutdown', None, lambda _: self.notify('exit', None))
            self.waitForFinished(1200)
        if self.state() != QProcess.ProcessState.NotRunning:
            self.kill()
            self.waitForFinished(1000)
