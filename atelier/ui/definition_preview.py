"""Read-only, syntax-highlighted definition overlay."""
from itertools import islice
import tokenize

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QTextFormat
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTextEdit, QVBoxLayout

from atelier.editor.highlighting import FILE_LANGUAGES, Highlighter


def definition_excerpt(path, line, source=None):
    first = max(0, line - 5)
    last = line + 21
    if source is not None:
        lines = source.split('\n')[first:last]
    else:
        if path.stat().st_size > 25_000_000:
            raise ValueError('Tanım önizlemesi için dosya çok büyük.')
        python = path.suffix.lower() in ('.py', '.pyw', '.pyi')
        with (tokenize.open(path) if python else path.open(encoding='utf-8')) as handle:
            lines = [text.rstrip('\r\n') for text in islice(handle, first, last)]
    if not 0 <= line - first < len(lines):
        raise ValueError('Tanım satırı dosyada bulunamadı.')
    return '\n'.join(text if len(text) <= 4000 else text[:4000] + '…' for text in lines), line - first


class DefinitionPreview(QFrame):
    def __init__(self, editor, path, line, text, highlight_line, open_target, dismiss):
        super().__init__(editor.viewport())
        self.editor = editor
        self.setObjectName('definitionPreview')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 8)
        header = QHBoxLayout()
        title = QLabel(f'{path.name} · Satır {line + 1}')
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setToolTip(str(path))
        header.addWidget(title, 1)
        open_button = QPushButton('Sekmede aç')
        open_button.clicked.connect(open_target)
        header.addWidget(open_button)
        close_button = QPushButton('Kapat')
        close_button.clicked.connect(dismiss)
        header.addWidget(close_button)
        layout.addLayout(header)
        self.code = QPlainTextEdit(readOnly=True)
        self.code.setAccessibleName('Tanım önizlemesi')
        self.code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code.setFont(editor.font())
        self.code.setTabStopDistance(editor.tabStopDistance())
        self.code.setPlainText(text)
        self.highlighter = Highlighter(self.code.document())
        self.highlighter.style = editor.highlighter.style
        self.highlighter.set_language('python' if path.suffix.lower() == '.pyi'
                                      else FILE_LANGUAGES.get(path.suffix.lower(), 'text'))
        layout.addWidget(self.code)
        cursor = self.code.textCursor()
        cursor.setPosition(self.code.document().findBlockByNumber(highlight_line).position())
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setBackground(self.palette().alternateBase())
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        self.code.setExtraSelections([selection])
        self.code.setTextCursor(cursor)
        self.escape = QShortcut(QKeySequence('Esc'), self)
        self.escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.escape.activated.connect(dismiss)
        editor.viewport().installEventFilter(self)

    def reposition(self):
        viewport = self.editor.viewport()
        width = min(700, viewport.width())
        height = min(290, viewport.height())
        anchor = self.editor.cursorRect()
        x = max(0, min(anchor.x(), viewport.width() - width))
        y = anchor.bottom() + 6
        if y + height > viewport.height():
            y = max(0, min(anchor.top() - height - 6, viewport.height() - height))
        self.setGeometry(x, y, width, height)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.reposition()
        return super().eventFilter(watched, event)
