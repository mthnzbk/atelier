"""Killable jobs: expensive parsing and regex never run on the UI thread."""
import json
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal
from atelier.runtime.paths import application_root, worker_command


class TaskWorker(QObject):
    results = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, operation, payload, parent=None, timeout=60000):
        super().__init__(parent)
        self.operation, self.payload = operation, payload
        self.cancelled = False
        self.completed = False
        self.process = QProcess(self)
        self.process.finished.connect(self.complete)
        self.process.errorOccurred.connect(self.failed)
        self.timer = QTimer(self, singleShot=True, interval=timeout)
        self.timer.timeout.connect(self.timed_out)
        self.output, self.errors = bytearray(), bytearray()
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read)

    def read(self):
        self.output.extend(bytes(self.process.readAllStandardOutput()))
        self.errors.extend(bytes(self.process.readAllStandardError()))

    def start(self):
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(str(application_root()))

        def send():
            self.process.write(
                json.dumps(
                    dict(
                        operation=self.operation,
                        **self.payload)).encode('utf-8'))
            self.process.closeWriteChannel()
        self.process.started.connect(send)
        program, arguments = worker_command('task')
        self.process.start(program, arguments)
        self.timer.start()

    def failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.errors.extend(self.process.errorString().encode('utf-8'))
            self.complete(-1)

    def complete(self, code=0, *_):
        if self.completed:
            return
        self.completed = True
        self.timer.stop()
        self.read()
        if not self.cancelled:
            try:
                if code:
                    raise ValueError(self.errors.decode('utf-8', 'replace')
                                     [-2000:] or 'Arka plan işlemi tamamlanamadı.')
                result = json.loads(self.output)
                if 'error' in result:
                    raise ValueError(result['error'])
                self.results.emit(result['result'])
            except (ValueError, KeyError) as error:
                self.error.emit(str(error))
        self.finished.emit()

    def timed_out(self):
        self.error.emit('İşlem süre sınırını aştı ve durduruldu.')
        self.requestInterruption()

    def requestInterruption(self):
        self.cancelled = True
        self.timer.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def isRunning(self):
        return self.process.state() != QProcess.ProcessState.NotRunning

    def wait(self, milliseconds=3000):
        return not self.isRunning() or self.process.waitForFinished(milliseconds)
