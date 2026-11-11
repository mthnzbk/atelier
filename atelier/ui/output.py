import re
from pathlib import Path
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QTextCursor, QColor
from PySide6.QtWidgets import QPlainTextEdit


class OutputView(QPlainTextEdit):
    navigate = Signal(str, int)
    traceback = re.compile(r'File "([^"]+)", line (\d+)')
    diagnostic = re.compile(
        r'^\s*(.+?\.(?:pyw?|html?|css|[mc]?js|json|ya?ml|toml)):(\d+)(?=[:\s]|$)', re.I)

    def __init__(self, root_provider):
        super().__init__()
        self.setReadOnly(True)
        self.root_provider = root_provider
        self.document().contentsChanged.connect(self.mark_links)

    def location(self, text):
        match = self.traceback.search(text) or self.diagnostic.match(text)
        if not match:
            return None
        path = Path(match[1])
        if str(path).startswith('<'):
            return None
        return str((Path(self.root_provider()) / path).resolve()
                   if not path.is_absolute() else path), max(0, int(match[2]) - 1)

    def mark_links(self):
        from PySide6.QtWidgets import QTextEdit
        selections = []
        block = self.document().lastBlock()
        count = 0
        while block.isValid() and count < 1000:
            match = self.traceback.search(block.text()) or self.diagnostic.match(block.text())
            if match:
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(block)
                start = len(block.text()[:match.start()].encode('utf-16-le')) // 2
                end = len(block.text()[:match.end()].encode('utf-16-le')) // 2
                selection.cursor.setPosition(block.position() + start)
                selection.cursor.setPosition(
                    block.position() + end, QTextCursor.MoveMode.KeepAnchor)
                selection.format.setForeground(QColor('#7c9cff'))
                selection.format.setFontUnderline(True)
                selections.append(selection)
            block = block.previous()
            count += 1
        self.setExtraSelections(selections)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            location = self.location(
                self.cursorForPosition(
                    event.position().toPoint()).block().text())
            if location:
                self.navigate.emit(*location)
