import difflib
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextFormat, QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QSplitter, QPlainTextEdit, QListWidget, QPushButton, QTextEdit, QWidget
from atelier.git.partial import selected_patch
from atelier.ui.icons import icon


class GitCompare(QDialog):
    def __init__(self, window, path):
        super().__init__(window)
        self.window, self.path = window, Path(path)
        self.setWindowTitle('Git · yan yana karşılaştırma')
        self.resize(1150, 780)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(['Hazırlanmamış değişiklikler', 'Hazırlanmış değişiklikler'])
        self.mode.setItemData(0, 'Git dizini ↔ çalışma dosyası', Qt.ItemDataRole.ToolTipRole)
        self.mode.setItemData(1, 'HEAD ↔ Git dizini', Qt.ItemDataRole.ToolTipRole)
        row.addWidget(self.mode)
        self.status = QLabel(str(path))
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        row.addWidget(self.status, 1)
        layout.addLayout(row)
        split = QSplitter()
        self.left = QPlainTextEdit(readOnly=True)
        self.right = QPlainTextEdit(readOnly=True)
        self.side_labels = []
        for view in (self.left, self.right):
            pane = QWidget()
            pane_layout = QVBoxLayout(pane)
            pane_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel()
            self.side_labels.append(label)
            pane_layout.addWidget(label)
            view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            view.setStyleSheet('font-family:Consolas;font-size:11pt;')
            pane_layout.addWidget(view)
            split.addWidget(pane)
        layout.addWidget(split, 1)
        self.groups = QListWidget()
        self.groups.setMaximumHeight(140)
        layout.addWidget(self.groups)
        self.apply = QPushButton('Seçili değişiklik grubunu hazırla')
        self.apply.setIcon(icon('git'))
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self.apply)
        close = QPushButton('Kapat')
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        layout.addLayout(footer)
        self.mode.currentIndexChanged.connect(self.load)
        self.groups.currentRowChanged.connect(self.highlight)
        self.apply.clicked.connect(self.apply_group)
        self.left.verticalScrollBar().valueChanged.connect(self.right.verticalScrollBar().setValue)
        self.right.verticalScrollBar().valueChanged.connect(self.left.verticalScrollBar().setValue)
        self.generation = 0
        self.load()

    def load(self, *_):
        staged = self.mode.currentIndex() == 1
        self.side_labels[0].setText('Son commit (HEAD)' if staged else 'Git dizini')
        self.side_labels[1].setText('Git dizini' if staged else 'Çalışma dosyası')
        self.generation += 1
        generation = self.generation
        self.apply.setEnabled(False)
        self.groups.clear()

        def root(code, text):
            if code:
                self.status.setText(text)
                return
            self.relative = self.path.relative_to(Path(text.strip())).as_posix()
            staged = self.mode.currentIndex() == 1

            def left(code, text):
                if generation != self.generation:
                    return
                self.missing_base = bool(code)
                self.base = '' if code else text
                if staged:
                    self.window.git_command(['show', ':' + self.relative], right)
                else:
                    try:
                        with self.path.open(encoding='utf-8', newline='') as source:
                            working = source.read()
                        if '\r\n' not in self.base:
                            working = working.replace('\r\n', '\n')
                        right(0, working)
                    except (OSError, UnicodeError) as error:
                        right(1, str(error))

            def right(code, text):
                if generation != self.generation:
                    return
                if code or '\x00' in text or '\x00' in self.base:
                    self.status.setText('Bu görünüm UTF-8 metin dosyaları içindir.')
                    return
                self.working = text
                self.left.setPlainText(self.base)
                self.right.setPlainText(text)
                self.changes = list(
                    difflib.SequenceMatcher(
                        a=self.base.splitlines(True),
                        b=text.splitlines(True),
                        autojunk=False).get_grouped_opcodes(3))
                for index, group in enumerate(self.changes):
                    modified = [op for op in group if op[0] != 'equal']
                    self.groups.addItem(
                        f'Grup {index + 1} · eski {modified[0][1] + 1}–{modified[-1][2]} / yeni {modified[0][3] + 1}–{modified[-1][4]}')
                self.apply.setText(
                    'Seçili grubu hazırlamadan çıkar' if staged else 'Seçili grubu hazırla')
                if self.missing_base:
                    self.apply.setText(
                        'Yeni dosyanın tamamını hazırlamadan çıkar' if staged else 'Yeni dosyanın tamamını Git’e ekle')
                self.apply.setEnabled(bool(self.changes))
                self.status.setText(f'{self.path.name} · {len(self.changes)} değişiklik grubu')
                if self.changes:
                    self.groups.setCurrentRow(0)
            self.window.git_command(['show', ('HEAD:' if staged else ':') + self.relative], left)
        self.window.git_command(['rev-parse', '--show-toplevel'], root)

    def highlight(self, index):
        if index < 0 or index >= len(getattr(self, 'changes', [])):
            return
        group = self.changes[index]
        for view, side, color in [(self.left, 1, QColor(251, 113, 133, 45)),
                                  (self.right, 3, QColor(52, 211, 153, 45))]:
            selections = []
            for opcode in group:
                if opcode[0] == 'equal':
                    continue
                for line in range(opcode[side], opcode[side + 1]):
                    block = view.document().findBlockByNumber(line)
                    if not block.isValid():
                        continue
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = QTextCursor(block)
                    selection.format.setBackground(color)
                    selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                    selections.append(selection)
            view.setExtraSelections(selections)
            cursor = QTextCursor(view.document().findBlockByNumber(group[0][side]))
            view.setTextCursor(cursor)
            view.centerCursor()

    def apply_group(self):
        index = self.groups.currentRow()
        if index < 0:
            return
        staged = self.mode.currentIndex() == 1

        def completed(code, text):
            if code:
                self.window.message(text)
            else:
                self.window.refresh_git()
                self.load()
        if self.missing_base:
            self.window.git_command(['rm', '--cached', '--', str(self.path)]
                                    if staged else ['add', '--', str(self.path)], completed)
            return
        changed = [op for op in self.changes[index] if op[0] != 'equal']
        first, last = changed[0][3], max(changed[0][3], changed[-1][4] - 1)
        patch = selected_patch(self.base, self.working, self.relative, first, last)
        flags = ['--cached'] + (['--reverse'] if staged else [])

        def checked(code, text):
            if code:
                self.window.message('Git değişmiş olabilir; görünümü yenileyin.\n' + text)
            else:
                self.window.git_command(['apply', *flags, '-'], completed, input_text=patch)
        self.window.git_command(['apply', *flags, '--check', '-'], checked, input_text=patch)
