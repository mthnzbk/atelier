"""Watch files and parent directories; snapshots also cover atomic replacement."""
import hashlib
from pathlib import Path
from PySide6.QtCore import QObject, QFileSystemWatcher, QTimer, Signal


def fingerprint(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).digest()
    except FileNotFoundError:
        return None


class FileMonitor(QObject):
    changed = Signal(object, object)  # Document, fingerprint (None when deleted)

    def __init__(self, parent):
        super().__init__(parent)
        self.entries = {}
        self.stats = {}
        self.dirty = set()
        self.watcher = QFileSystemWatcher(self)
        self.debounce = QTimer(self, interval=180, singleShot=True)
        self.debounce.timeout.connect(self.check)
        self.watcher.fileChanged.connect(self.file_event)
        self.watcher.directoryChanged.connect(self.directory_event)
        self.poll = QTimer(self, interval=1600)
        self.poll.timeout.connect(self.check)
        self.poll.start()

    def track(self, doc):
        if doc.path:
            try:
                digest = fingerprint(doc.path)
            except OSError:
                return
            self.entries[doc] = (doc.path, digest)
            self.stats[doc] = self.stat(doc.path)
            self.rewatch()

    def untrack(self, doc):
        self.entries.pop(doc, None)
        self.stats.pop(doc, None)
        self.rewatch()

    def rewatch(self):
        wanted = {str(path) for path, _ in self.entries.values() if path.exists()}
        wanted.update(str(path.parent) for path, _ in self.entries.values() if path.parent.exists())
        current = set(self.watcher.files() + self.watcher.directories())
        if current - wanted:
            self.watcher.removePaths(list(current - wanted))
        if wanted - current:
            self.watcher.addPaths(list(wanted - current))

    @staticmethod
    def stat(path):
        try:
            value = path.stat()
            return value.st_mtime_ns, value.st_size, value.st_ino
        except OSError:
            return None

    def file_event(self, path):
        self.dirty.add(Path(path))
        self.debounce.start()

    def directory_event(self, path):
        self.dirty.update(p for p, _ in self.entries.values() if p.parent == Path(path))
        self.debounce.start()

    def check(self):
        for doc, (path, known) in list(self.entries.items()):
            stat = self.stat(path)
            if stat == self.stats.get(doc) and path not in self.dirty:
                continue
            self.stats[doc] = stat
            try:
                actual = fingerprint(path)
            except OSError:
                continue
            if actual != known:
                self.entries[doc] = (path, actual)
                self.changed.emit(doc, actual)
        self.dirty.clear()
        self.rewatch()

    def has_conflict(self, doc, target):
        entry = self.entries.get(doc)
        if entry is None or Path(target) != entry[0]:
            return False
        return fingerprint(target) != entry[1] or getattr(doc, 'external_pending', False)

    def shutdown(self):
        self.poll.stop()
        self.debounce.stop()
        self.entries.clear()
