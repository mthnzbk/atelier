"""Document-wide folding and clickable miniature code overview."""
import re
from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtGui import QColor, QPainter, QTextCursor, QPixmap
from PySide6.QtWidgets import QWidget


class CodeStructure(QObject):
    updated = Signal()

    def __init__(self, document):
        super().__init__(document)
        self.document = document
        self.language = 'python'
        self.enabled = True
        self.source = None
        self.regions = {}
        self.folded = {}
        self.guide_columns = {}
        self.had_hidden = False
        self.timer = QTimer(self, interval=160, singleShot=True)
        self.timer.timeout.connect(self.rebuild)
        document.contentsChange.connect(self.schedule)

    def schedule(self, position=0, removed=0, added=0):
        if self.enabled and (removed or added):
            self.timer.start()

    def rebuild(self):
        self.timer.stop()
        if not self.enabled:
            self.source = None
            self.regions.clear()
            self.folded.clear()
            self.guide_columns.clear()
            self.apply()
            return
        self.source = self.document.toPlainText()
        lines = self.source.split('\n')
        regions = {}
        if self.language == 'markdown':
            headers = []
            fence = None
            for i, text in enumerate(lines):
                if re.match(r'^\s*(`{3,}|~{3,})', text):
                    if fence is None:
                        fence = i
                    else:
                        if i > fence + 1:
                            regions[fence] = i
                        fence = None
                if fence is not None:
                    continue
                match = re.match(r'^(#{1,6})\s+', text)
                if match:
                    level = len(match[1])
                    while headers and headers[-1][1] >= level:
                        start, _ = headers.pop()
                        if i > start + 1:
                            regions[start] = i - 1
                    headers.append((i, level))
            for start, _ in headers:
                if len(lines) > start + 1:
                    regions[start] = len(lines) - 1
        elif self.language == 'python':
            # Indentation keeps folding available while the source is incomplete.
            stack = []
            for i, text in enumerate(lines):
                if not text.strip() or text.lstrip().startswith('#'):
                    continue
                indent = len(text.expandtabs(4)) - len(text.expandtabs(4).lstrip())
                while stack and indent <= stack[-1][1]:
                    start, _ = stack.pop()
                    if i > start + 1:
                        regions[start] = i - 1
                if text.rstrip().endswith(':'):
                    stack.append((i, indent))
            for start, _ in stack:
                if len(lines) > start + 1:
                    regions[start] = len(lines) - 1
        self.regions = regions
        self.guide_columns = {}
        active = []
        for line, text in enumerate(lines):
            active = [(start, end) for start, end in active if line <= end]
            if active:
                self.guide_columns[line] = [len(lines[start].expandtabs(
                    4)) - len(lines[start].expandtabs(4).lstrip()) for start, _ in active]
            if line in regions:
                active.append((line, regions[line]))
        anchors = {cursor.blockNumber(): cursor for cursor in self.folded.values()}
        self.folded = {line: cursor for line, cursor in anchors.items() if line in regions}
        self.apply()

    def toggle(self, line):
        if line not in self.regions:
            return
        if line in self.folded:
            del self.folded[line]
        else:
            self.folded[line] = QTextCursor(self.document.findBlockByNumber(line))
        self.apply()

    def reveal(self, line):
        self.folded = {start: cursor for start, cursor in self.folded.items()
                       if not start < line <= self.regions.get(start, start)}
        self.apply()

    def apply(self):
        if not self.folded and not self.had_hidden:
            self.updated.emit()
            return
        hidden = set()
        for start in self.folded:
            hidden.update(range(start + 1, self.regions.get(start, start) + 1))
        block = self.document.firstBlock()
        while block.isValid():
            visible = block.blockNumber() not in hidden
            block.setVisible(visible)
            block.setLineCount(1 if visible else 0)
            block = block.next()
        self.document.markContentsDirty(0, self.document.characterCount())
        self.had_hidden = bool(hidden)
        self.updated.emit()


class MiniMap(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip('Dosyada gezinmek için tıklayın veya sürükleyin')
        self.cache = None
        self.cache_key = None

    def build_image(self):
        document = self.editor.document()
        self.scale = min(3.0, max(0.00001, self.height() / max(1, document.blockCount())))
        self.cache = QPixmap(self.size())
        self.cache.fill(self.editor.palette().window().color())
        painter = QPainter(self.cache)
        step = max(1, document.blockCount() // max(1, self.height()))
        for number in range(0, document.blockCount(), step):
            block = document.findBlockByNumber(number)
            text = block.text()[:160].expandtabs(4)
            if not text.strip():
                continue
            indent = len(text) - len(text.lstrip())
            color = '#8297bc' if block.isVisible() else '#475569'
            if text.lstrip().startswith(('#', '"""', "'''")):
                color = '#779077'
            elif text.lstrip().startswith(('def ', 'class ')):
                color = '#a78bfa'
            painter.fillRect(4 + min(65, indent * 0.9), int(number * self.scale),
                             max(1, min(96 - indent, max(2, len(text.strip()) * 0.9))), max(1, int(self.scale - 1)), QColor(color))
        painter.end()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.editor.palette().window())
        document = self.editor.document()
        key = (
            document.revision(),
            self.width(),
            self.height(),
            tuple(
                self.editor.structure.folded),
            self.editor.palette().window().color().name())
        if key != self.cache_key:
            self.cache_key = key
            self.build_image()
        painter.drawPixmap(0, 0, self.cache)
        first = self.editor.firstVisibleBlock().blockNumber()
        last = self.editor.cursorForPosition(
            self.editor.viewport().rect().bottomLeft()).blockNumber()
        painter.fillRect(0, int(first * self.scale), self.width(),
                         max(5, int((last - first + 1) * self.scale)), QColor(124, 156, 255, 45))

    def mousePressEvent(self, event):
        self.navigate(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.navigate(event)

    def navigate(self, event):
        scale = getattr(self, 'scale', 1)
        line = min(self.editor.blockCount() - 1, max(0, int(event.position().y() / scale)))
        self.editor.reveal_line(line)
        cursor = QTextCursor(self.editor.document().findBlockByNumber(line))
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
