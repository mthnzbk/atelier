"""Asynchronous Debug Adapter Protocol client for debugpy (stdio)."""
import json
from atelier.runtime.paths import python_tool_command
from PySide6.QtCore import QObject, QProcess, QTimer, Signal


class Debugger(QObject):
    output = Signal(str)
    paused = Signal(list)
    variables = Signal(list)
    state = Signal(str)
    trace = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.finished)
        self.buffer = bytearray()
        self.seq = 0
        self.pending = {}
        self.quiet = set()
        self.thread = None
        self.breakpoints = {}
        self.active = False
        self.conditions = {}
        self.frame_id = None
        self.frame_generation = 0
        self.scope_reference = None
        self.process.started.connect(self.initialize)

    def send(self, command, arguments=None, callback=None, quiet=False):
        self.trace.emit('→ ' + command)
        self.seq += 1
        if callback:
            self.pending[self.seq] = callback
        if quiet:
            self.quiet.add(self.seq)
        data = json.dumps({'seq': self.seq, 'type': 'request', 'command': command,
                           'arguments': arguments or {}}).encode('utf-8')
        self.process.write(f'Content-Length: {len(data)}\r\n\r\n'.encode() + data)

    def start(self, path, interpreter, root, breakpoints, args=None, environment=None):
        if self.active:
            return
        self.path, self.interpreter, self.root = str(path), interpreter, str(root)
        self.args = args or []
        self.environment = environment or {}
        self.breakpoints = breakpoints
        self.buffer.clear()
        self.pending.clear()
        self.quiet.clear()
        self.thread = None
        self.clear_frame()
        self.active = True
        self.state.emit('Başlatılıyor')
        self.process.setWorkingDirectory(self.root)
        from atelier.projects.environments import clean_environment
        self.process.setProcessEnvironment(clean_environment())
        self.process.start(*python_tool_command('debug', interpreter))

    def initialize(self):
        self.send('initialize', {
            'clientID': 'atelier', 'adapterID': 'debugpy', 'pathFormat': 'path',
            'linesStartAt1': True, 'columnsStartAt1': True,
            'supportsRunInTerminalRequest': False, 'supportsVariableType': True,
        }, self.launch)

    def launch(self, _):
        self.send('launch', {'name': 'Python', 'type': 'python', 'request': 'launch',
                             'program': self.path, 'python': [self.interpreter], 'cwd': self.root,
                             'args': self.args, 'console': 'internalConsole', 'justMyCode': True,
                             'stopOnEntry': False, 'redirectOutput': True, 'env': self.environment})

    def set_breakpoints(self, path, lines, callback=None):
        conditions = self.conditions.get(str(path), {})
        self.send('setBreakpoints', {'source': {'path': str(path)},
                                     'breakpoints': [dict(line=line, **({'condition': conditions[line]} if conditions.get(line) else {})) for line in sorted(lines)]}, callback)

    def read_error(self):
        text = bytes(self.process.readAllStandardError()).decode('utf-8', 'replace')
        if text:
            self.output.emit(text)

    def read(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b'\r\n\r\n' in self.buffer:
            header, body = bytes(self.buffer).split(b'\r\n\r\n', 1)
            length = int(header.split(b'Content-Length:')[1].split(b'\r\n')[0])
            if len(body) < length:
                return
            del self.buffer[:len(header) + 4 + length]
            message = json.loads(body[:length])
            self.trace.emit('← ' + json.dumps(message))
            if message['type'] == 'response':
                callback = self.pending.pop(message['request_seq'], None)
                quiet = message['request_seq'] in self.quiet
                self.quiet.discard(message['request_seq'])
                if not message.get('success', True):
                    if not quiet:
                        self.output.emit(
                            'Debugger: ' +
                            message.get(
                                'message',
                                'İstek başarısız') +
                            '\n')
                    if message.get('command') == 'launch':
                        self.stop()
                elif callback:
                    callback(message.get('body', {}))
            elif message['type'] == 'event':
                self.handle_event(message['event'], message.get('body', {}))

    def handle_event(self, event, body):
        if event == 'initialized':
            entries = list(self.breakpoints.items())

            def configure(index=0):
                if index == len(entries):
                    self.send('setExceptionBreakpoints', {'filters': ['uncaught']},
                              lambda _: self.send('configurationDone'))
                    self.state.emit('Çalışıyor')
                else:
                    path, lines = entries[index]
                    self.set_breakpoints(path, lines, lambda _: configure(index + 1))
            configure()
        elif event == 'output' and body.get('category') != 'telemetry':
            self.output.emit(body.get('output', ''))
        elif event == 'stopped':
            self.clear_frame()
            self.thread = body.get('threadId')
            self.state.emit('Duraklatıldı')
            generation = self.frame_generation
            self.send('stackTrace', {'threadId': self.thread}, lambda result: self.stack(
                result) if generation == self.frame_generation else None)
        elif event == 'continued':
            self.thread = None
            self.clear_frame()
            self.state.emit('Çalışıyor')
        elif event == 'terminated':
            self.thread = None
            self.clear_frame()
            self.state.emit('Bitti')
            # An adapter may remain alive after its debuggee exits.
            self.send('disconnect', {'terminateDebuggee': False}, lambda _: self.process.kill())
            pid = self.process.processId()
            QTimer.singleShot(1200, lambda: self.process.kill()
                              if self.process.processId() == pid and pid else None)
        elif event == 'exited':
            self.output.emit(f"\n[Çıkış kodu: {body.get('exitCode')}]\n")

    def stack(self, body):
        frames = body.get('stackFrames', [])
        self.paused.emit(frames)
        if frames and self.frame_id is None:
            self.inspect_frame(frames[0]['id'])

    def clear_frame(self):
        self.frame_id = self.scope_reference = None
        self.frame_generation += 1

    def inspect_frame(self, frame_id):
        if self.thread is None:
            return
        self.clear_frame()
        self.frame_id = frame_id
        generation = self.frame_generation
        self.send('scopes', {'frameId': frame_id}, lambda result: self.scopes(result, generation))

    def scopes(self, body, generation):
        if generation != self.frame_generation:
            return
        scopes = body.get('scopes', [])
        if scopes:
            self.scope_reference = scopes[0]['variablesReference']
            self.send('variables', {'variablesReference': scopes[0]['variablesReference']},
                      lambda result: self.variables.emit(result.get('variables', [])) if generation == self.frame_generation else None)

    def evaluate(self, expression, callback, context='watch'):
        if self.thread is not None and self.frame_id is not None:
            generation = self.frame_generation
            self.send('evaluate', {'expression': expression, 'frameId': self.frame_id, 'context': context},
                      lambda result: callback(result) if generation == self.frame_generation else None, quiet=context == 'hover')

    def set_variable(self, name, value, reference=None, callback=None):
        reference = reference or self.scope_reference
        if self.thread is not None and reference:
            self.send('setVariable', {'variablesReference': reference,
                      'name': name, 'value': value}, callback)

    def action(self, command):
        if self.thread is not None:
            self.send(command, {'threadId': self.thread})

    def pause(self):
        self.send('threads', callback=lambda body: self.send('pause', {
            'threadId': body['threads'][0]['id']}) if body.get('threads') else None)

    def stop(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.send('disconnect', {'terminateDebuggee': True})

    def finished(self, *_):
        self.active = False
        self.thread = None
        self.clear_frame()
        self.pending.clear()
        self.quiet.clear()
        self.state.emit('Bitti')

    def process_error(self, error):
        self.output.emit(self.process.errorString())
        if error == QProcess.ProcessError.FailedToStart:
            self.finished()

    def shutdown(self):
        self.stop()
        if not self.process.waitForFinished(1500):
            self.process.kill()
            self.process.waitForFinished(1000)
