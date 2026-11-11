"""PySide6 Python editor. Run with the interpreter containing requirements.txt."""
import re
from atelier.editor.multicursor import MultiCursorMixin

from PySide6.QtCore import QTimer, Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QTextCursor
from PySide6.QtWidgets import QListWidget, QPlainTextEdit, QWidget


def units(text):
    return len(text.encode('utf-16-le')) // 2


from atelier.editor.highlighting import Highlighter




class LineNumbers(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            block = self.editor.cursorForPosition(event.position().toPoint()).blockNumber()
            if event.position().x() > self.width() - 17:
                self.editor.structure.toggle(block)
            else:
                self.editor.breakpoint_toggled.emit(block + 1)


class Editor(MultiCursorMixin, QPlainTextEdit):
    complete = Signal()
    signature_requested = Signal()
    hover_requested = Signal(object)
    breakpoint_toggled = Signal(int)

    def __init__(self):
        super().__init__()
        self.secondary_cursors = []
        self.coverage_lines = {}
        self.show_active_guide = True
        self.setFont(QFont('Consolas', 12))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.highlighter = Highlighter(self.document())
        self.gutter = LineNumbers(self)
        self.diagnostic_lines = {}
        self.breakpoints = set()
        self.git_lines = {}
        self.execution_line = None
        self.setMouseTracking(True)
        self.hover_timer = QTimer(self, singleShot=True, interval=550)
        self.hover_timer.timeout.connect(lambda: self.hover_requested.emit(self.hover_position))
        self.hover_position = None
        self.blockCountChanged.connect(self.update_gutter_margin)
        self.updateRequest.connect(self.update_gutter)
        self.cursorPositionChanged.connect(self.gutter.update)
        self.update_gutter_margin()
        self.popup = QListWidget(self)
        self.popup.setWindowFlags(Qt.WindowType.ToolTip)
        self.popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popup.itemClicked.connect(self.accept_completion)
        self.popup.hide()
        from atelier.editor.signature import SignaturePopup
        self.signature_popup=SignaturePopup(self)
        self.language = 'python'
        from atelier.editor.snippets import SnippetSession
        self.snippet_session = SnippetSession(self)
        self.minimap_enabled = True
        from atelier.editor.folding import MiniMap
        self.minimap = MiniMap(self)
        self.configure_navigation()
        self.update_gutter_margin()

    def configure_navigation(self):
        from atelier.editor.folding import CodeStructure
        document = self.document()
        if not hasattr(document, '_structure'):
            document._structure = CodeStructure(document)
        self.structure = document._structure
        self.structure.updated.connect(self.navigation_updated)
        self.navigation_updated()

    def setPlainText(self,text):
        self.secondary_cursors=[]
        super().setPlainText(text)

    def navigation_updated(self):
        self.gutter.update()
        self.minimap.update()
        self.viewport().update()

    def reveal_line(self, line):
        self.structure.reveal(line)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.hover_position = event.position().toPoint()
        self.hover_timer.start()

    def mousePressEvent(self,event):
        if event.modifiers() & Qt.KeyboardModifier.AltModifier and event.button()==Qt.MouseButton.LeftButton:
            self.secondary_cursors.append(QTextCursor(self.textCursor()))
            self.setTextCursor(self.cursorForPosition(event.position().toPoint()))
            self.refresh_multi()
            return
        self.secondary_cursors.clear()
        super().mousePressEvent(event)
        self.refresh_multi()

    def leaveEvent(self, event):
        self.hover_timer.stop()
        self.hover_position = None
        super().leaveEvent(event)

    def focusOutEvent(self, event):
        self.popup.hide()
        if hasattr(self,'signature_popup'):self.signature_popup.hide()
        super().focusOutEvent(event)

    def gutter_width(self):
        return 43 + self.fontMetrics().horizontalAdvance('9') * len(str(max(1, self.blockCount())))

    def update_gutter_margin(self, *_):
        left = self.gutter_width()
        right = 106 if getattr(self, 'minimap_enabled', False) else 0
        margins = self.viewportMargins()
        if margins.left() != left or margins.right() != right:
            self.setViewportMargins(left, 0, right, 0)

    def update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_margin()
        if hasattr(self, 'minimap'):
            self.minimap.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.gutter.setGeometry(rect.left(), rect.top(), self.gutter_width(), rect.height())
        if hasattr(self, 'minimap'):
            self.minimap.setGeometry(rect.right() - 105, rect.top(), 106, rect.height())

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), self.palette().window())
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            line = block.blockNumber()
            if block.isVisible() and top + height >= event.rect().top():
                light = self.palette().window().color().lightness() >= 128
                painter.setPen(QColor(('#243047' if light else '#e5e7eb') if line == self.textCursor().blockNumber() else '#778196'))
                painter.drawText(0, top, self.gutter.width() - 22, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(line + 1))
                if hasattr(self, 'structure') and line in self.structure.regions:
                    x,y = self.gutter.width()-11, top+height//2
                    if line in self.structure.folded:
                        painter.drawLine(x-2,y-4,x+2,y)
                        painter.drawLine(x+2,y,x-2,y+4)
                    else:
                        painter.drawLine(x-4,y-2,x,y+2)
                        painter.drawLine(x,y+2,x+4,y-2)
                if line+1 in self.coverage_lines:
                    painter.fillRect(0,top,3,height,QColor('#34d399' if self.coverage_lines[line+1] else '#fb7185'))
                if line in self.diagnostic_lines:
                    painter.setBrush(QColor('#f87171' if self.diagnostic_lines[line] == 1 else '#fbbf24'))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(3, top + 5, 6, 6)
                if line + 1 in self.breakpoints:
                    painter.setBrush(QColor('#fb7185'))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(11, top + 4, 9, 9)
                if line in self.git_lines:
                    painter.fillRect(self.gutter.width() - 3, top, 3, max(height, 3), QColor(self.git_lines[line]))
                if self.execution_line == line + 1:
                    painter.setPen(QColor('#fbbf24'))
                    painter.drawText(1, top, 12, height, Qt.AlignmentFlag.AlignCenter, '▶')
            top += height
            if hasattr(self, 'structure') and line in self.structure.folded:
                block = self.document().findBlockByNumber(self.structure.regions[line] + 1)
            else:
                block = block.next()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not hasattr(self, 'structure'):
            return
        painter = QPainter(self.viewport())
        painter.setPen(QColor('#526888' if self.palette().base().color().lightness() < 128 else '#a6b6ca'))
        current = self.textCursor().blockNumber()
        scopes = [start for start,end in self.structure.regions.items() if start <= current <= end]
        active = max(scopes) if scopes and self.show_active_guide and self.language=='python' else None
        column = 0
        end = -1
        if active is not None:
            header = self.document().findBlockByNumber(active).text().expandtabs(4)
            column = len(header)-len(header.lstrip())
            end = self.structure.regions[active]
            while end>active and not self.document().findBlockByNumber(end).text().strip():
                end-=1
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        space = self.fontMetrics().horizontalAdvance(' ')
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible():
                origin = self.cursorRect(QTextCursor(block)).left()
                if active is not None and active < block.blockNumber() <= end:
                    x = round(origin + column*space + 1)
                    painter.drawLine(x, top, x, top+height)
                if block.blockNumber() in self.structure.folded:
                    cursor = QTextCursor(block)
                    cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
                    painter.drawText(self.cursorRect(cursor).right()+12,top+self.fontMetrics().ascent(),
                                     f'⋯ {self.structure.regions[block.blockNumber()]-block.blockNumber()} satır')
            top += height
            line = block.blockNumber()
            if line in self.structure.folded:
                block = self.document().findBlockByNumber(self.structure.regions[line] + 1)
            else:
                block = block.next()
        for cursor in self.secondary_cursors:
            rect = self.cursorRect(cursor)
            painter.drawLine(rect.left(),rect.top(),rect.left(),rect.bottom())

    def keyPressEvent(self, event):
        if self.multi_key(event):
            return
        key = event.key()
        if key == Qt.Key.Key_Escape and self.snippet_session.stops:
            self.snippet_session.cancel()
            self.popup.hide()
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            if self.snippet_session.stops:
                self.snippet_session.advance(key == Qt.Key.Key_Backtab)
                self.popup.hide()
                return
            if key == Qt.Key.Key_Tab and not self.popup.isVisible() and not self.textCursor().hasSelection() and self.snippet_session.expand():
                self.popup.hide()
                return
        if key == Qt.Key.Key_Escape:
            self.popup.hide()
            return
        if self.popup.isVisible():
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                self.accept_completion(self.popup.currentItem())
                return
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                delta = 1 if key == Qt.Key.Key_Down else -1
                self.popup.setCurrentRow((self.popup.currentRow() + delta) % self.popup.count())
                return
            self.popup.hide()
        if key == Qt.Key.Key_Space and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.complete.emit()
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            if self.textCursor().hasSelection() or key == Qt.Key.Key_Backtab:
                self.indent_selection(key == Qt.Key.Key_Backtab)
            else:
                self.insertPlainText(' '*getattr(self,'indent_width',4))
            return
        if self.language != 'python':
            typed = event.text()
            super().keyPressEvent(event)
            if self.language == 'html' and not getattr(self, 'large_file', False) and getattr(self, 'auto_completion', True):
                if typed and (typed.isalnum() or typed in ('<', '/', '-', ' ')):
                    from atelier.languages.html import completion_context
                    before, _ = completion_context(self.textCursor())
                    if before.rfind('<') > before.rfind('>'):
                        self.complete.emit()
            return
        if event.text() in ('(', '[', '{', '"', "'") and not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            opening = event.text()
            closing = {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}[opening]
            cursor = self.textCursor()
            if cursor.hasSelection():
                text = cursor.selectedText().replace('\u2029', '\n')
                cursor.insertText(opening + text + closing)
            else:
                ahead = self.document().characterAt(cursor.position())
                behind = self.document().characterAt(max(0, cursor.position()-1))
                if opening in ('"', "'") and (behind.isalnum() or behind == '\\'):
                    super().keyPressEvent(event)
                    return
                if ahead == closing and opening == closing:
                    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
                else:
                    cursor.insertText(opening + closing)
                    cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
            self.setTextCursor(cursor)
            if opening == '(':
                self.signature_requested.emit()
            return
        if event.text() in (')', ']', '}') and self.document().characterAt(self.textCursor().position()) == event.text():
            self.moveCursor(QTextCursor.MoveOperation.NextCharacter)
            return
        if key == Qt.Key.Key_Backspace and not self.textCursor().hasSelection():
            cursor = self.textCursor()
            before = self.document().characterAt(max(0, cursor.position()-1))
            after = self.document().characterAt(cursor.position())
            if cursor.position() and (before, after) in [('(', ')'), ('[', ']'), ('{', '}'), ('"', '"'), ("'", "'")]:
                cursor.beginEditBlock()
                cursor.deleteChar()
                cursor.deletePreviousChar()
                cursor.endEditBlock()
                return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            before = cursor.block().text().encode('utf-16-le')[:cursor.positionInBlock()*2].decode('utf-16-le', 'ignore')
            indent = re.match(r'\s*', before).group()
            self.insertPlainText('\n' + indent + (' '*getattr(self,'indent_width',4) if before.rstrip().endswith(':') else ''))
            return
        super().keyPressEvent(event)
        if event.text() == ',':
            self.signature_requested.emit()
        if getattr(self,'auto_completion',True) and event.text() and (event.text().isalnum() or event.text() in '._'):
            self.complete.emit()

    def selected_blocks(self):
        cursor = self.textCursor()
        first = self.document().findBlock(cursor.selectionStart())
        end = cursor.selectionEnd()
        last = self.document().findBlock(max(cursor.selectionStart(), end - 1))
        return first.blockNumber(), last.blockNumber()

    def indent_selection(self, remove=False):
        first, last = self.selected_blocks()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for line in range(last, first - 1, -1):
            block = self.document().findBlockByNumber(line)
            cursor.setPosition(block.position())
            if remove:
                count = min(getattr(self,'indent_width',4), len(block.text()) - len(block.text().lstrip(' ')))
                if block.text().startswith('\t'):
                    count = 1
                cursor.setPosition(block.position() + count, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
            else:
                cursor.insertText(' '*getattr(self,'indent_width',4))
        cursor.endEditBlock()

    def toggle_comment(self):
        first, last = self.selected_blocks()
        blocks = [self.document().findBlockByNumber(i) for i in range(first, last + 1)]
        uncomment = all(not b.text().strip() or b.text().lstrip().startswith('#') for b in blocks)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for block in reversed(blocks):
            text = block.text()
            if not text.strip():
                continue
            indent = len(text) - len(text.lstrip())
            cursor.setPosition(block.position() + indent)
            if uncomment:
                count = 2 if text[indent:].startswith('# ') else 1
                cursor.setPosition(cursor.position() + count, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
            else:
                cursor.insertText('# ')
        cursor.endEditBlock()

    def accept_completion(self, item):
        self.popup.hide()
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if '_html' in data:
            self.snippet_session.insert(*data['_html'])
            return
        if data.get('_snippet'):
            self.snippet_session.expand(data['_snippet'])
            return
        cursor = self.textCursor()
        edit = data.get('textEdit')
        if edit:
            region = edit.get('range', edit.get('replace'))
            cursor.setPosition(self.offset(region['start']))
            cursor.setPosition(self.offset(region['end']), QTextCursor.MoveMode.KeepAnchor)
            value = edit['newText']
        else:
            prefix = re.search(r'\w*$', cursor.block().text().encode('utf-16-le')[:cursor.positionInBlock()*2].decode('utf-16-le', 'ignore')).group()
            cursor.setPosition(cursor.position() - units(prefix), QTextCursor.MoveMode.KeepAnchor)
            value = data.get('insertText') or data['label']
        # LSP kinds: Method=2, Function=3, Constructor=4, Class=7.
        callable_item = data.get('kind') in (2, 3, 4, 7)
        suffix = self.toPlainText().encode('utf-16-le')[cursor.selectionEnd()*2:].decode('utf-16-le', 'ignore')
        line_prefix = cursor.block().text().encode('utf-16-le')[:(cursor.selectionStart()-cursor.block().position())*2].decode('utf-16-le', 'ignore')
        import_context = re.match(r'^\s*(?:from\s+\S*|import\s+|from\s+\S+\s+import\s+)', line_prefix)
        if callable_item and value.endswith('()') and (suffix.lstrip().startswith('(') or import_context):
            value = value[:-2]
        add_call = callable_item and '(' not in value and not suffix.lstrip().startswith('(') and not import_context
        if add_call:
            value += '()'
        cursor.insertText(value)
        if add_call or (callable_item and value.endswith('()')):
            cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
        elif callable_item and not import_context and suffix.startswith('('):
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter)
        self.setTextCursor(cursor)
        if callable_item and not import_context:
            self.signature_requested.emit()

    def offset(self, position):
        block = self.document().findBlockByNumber(position['line'])
        if not block.isValid():
            return self.document().characterCount() - 1
        return block.position() + min(position['character'], units(block.text()))
