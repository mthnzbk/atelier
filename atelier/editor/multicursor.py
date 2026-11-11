import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QColor
from PySide6.QtWidgets import QTextEdit


class MultiCursorMixin:
    def undo(self):
        self.secondary_cursors.clear()
        super().undo()
        self.refresh_multi()

    def redo(self):
        self.secondary_cursors.clear()
        super().redo()
        self.refresh_multi()

    def select_next_occurrence(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            self.setTextCursor(cursor)
            return
        value = cursor.selectedText()
        match = self.document().find(value, cursor.selectionEnd())
        if match.isNull():
            match = self.document().find(value, 0)
        ranges = {(c.selectionStart(), c.selectionEnd()) for c in [cursor] + self.secondary_cursors}
        if not match.isNull() and (match.selectionStart(), match.selectionEnd()) not in ranges:
            self.secondary_cursors.append(QTextCursor(cursor))
            self.setTextCursor(match)
            self.refresh_multi()

    def refresh_multi(self):
        self.setExtraSelections(getattr(self, 'base_selections', []))
        self.viewport().update()

    def setExtraSelections(self, selections):
        self.base_selections = list(selections)
        combined = list(selections)
        for cursor in getattr(self, 'secondary_cursors', []):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(QColor(124, 156, 255, 75))
            combined.append(selection)
        for line, executed in getattr(self, 'coverage_lines', {}).items():
            block = self.document().findBlockByNumber(line - 1)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(block)
            selection.format.setBackground(
                QColor(
                    52,
                    211,
                    153,
                    22) if executed else QColor(
                    251,
                    113,
                    133,
                    30))
            from PySide6.QtGui import QTextFormat
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            combined.insert(0, selection)
        super().setExtraSelections(combined)

    def multi_edit(self, text=None, delete=0):
        cursors = [QTextCursor(self.textCursor())] + [QTextCursor(c)
                                                      for c in self.secondary_cursors]
        occupied = set()
        unique = []
        for index, cursor in enumerate(cursors):
            key = (cursor.selectionStart(), cursor.selectionEnd())
            if key not in occupied:
                unique.append((index, cursor))
                occupied.add(key)
        transaction = QTextCursor(self.document())
        transaction.beginEditBlock()
        for _, cursor in sorted(unique, key=lambda pair: pair[1].selectionStart(), reverse=True):
            if text is not None:
                value = text
                if text == '\n':
                    before = cursor.block().text().encode(
                        'utf-16-le')[:cursor.positionInBlock() * 2].decode('utf-16-le', 'ignore')
                    value += re.match(r'[ \t]*', before).group() + \
                        ('    ' if before.rstrip().endswith(':') else '')
                cursor.insertText(value)
            elif cursor.hasSelection():
                cursor.removeSelectedText()
            elif delete < 0:
                cursor.deletePreviousChar()
            else:
                cursor.deleteChar()
        transaction.endEditBlock()
        self.secondary_cursors = [cursor for index, cursor in unique if index != 0]
        self.setTextCursor(next(cursor for index, cursor in unique if index == 0))
        self.refresh_multi()

    def multi_key(self, event):
        if not self.secondary_cursors:
            return False
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.secondary_cursors.clear()
            self.refresh_multi()
            return True
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            if key in (Qt.Key.Key_Z, Qt.Key.Key_Y):
                self.secondary_cursors.clear()
            return False
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.multi_edit(delete=-1 if key == Qt.Key.Key_Backspace else 1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.multi_edit('\n')
        elif key == Qt.Key.Key_Tab:
            self.multi_edit(' ' * getattr(self, 'indent_width', 4))
        elif event.text() and event.text().isprintable():
            self.multi_edit(event.text())
        else:
            self.secondary_cursors.clear()
            self.refresh_multi()
            return False
        return True

    def insertFromMimeData(self, source):
        if self.secondary_cursors:
            self.multi_edit(source.text())
        else:
            super().insertFromMimeData(source)
