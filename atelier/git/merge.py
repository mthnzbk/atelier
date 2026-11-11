"""Resolve ordinary, diff3 and zdiff3 text conflict markers without losing context."""
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                               QPlainTextEdit, QPushButton, QSplitter, QWidget, QMessageBox)

MARKER = re.compile(r'^(<{7,}|\|{7,}|={7,}|>{7,})(?:\s.*)?$')


def parse_conflicts(source):
    lines = source.splitlines(keepends=True)
    parts, common, index = [], [], 0
    while index < len(lines):
        match = MARKER.match(lines[index].rstrip('\r\n'))
        if not match or not match[1].startswith('<'):
            common.append(lines[index])
            index += 1
            continue
        if common:
            parts.append(''.join(common))
            common = []
        width, start = len(match[1]), index
        index += 1
        ours, theirs = [], []
        phase = 'ours'
        while index < len(lines):
            marker = MARKER.match(lines[index].rstrip('\r\n'))
            token = marker[1] if marker and len(marker[1]) == width else ''
            if token.startswith('<'):
                raise ValueError('İç içe çakışma işaretleri var; dosyayı elle düzenleyin.')
            if token.startswith('|') and phase == 'ours':
                phase = 'base'
            elif token.startswith('=') and phase in ('ours', 'base'):
                phase = 'theirs'
            elif token.startswith('>') and phase == 'theirs':
                index += 1
                parts.append(
                    dict(
                        ours=''.join(ours),
                        theirs=''.join(theirs),
                        line=start + 1,
                        choice=None))
                break
            elif phase == 'ours':
                ours.append(lines[index])
            elif phase == 'theirs':
                theirs.append(lines[index])
            index += 1
        else:
            raise ValueError('Eksik veya bozuk çakışma işaretleri var.')
    if common:
        parts.append(''.join(common))
    return parts


class MergeDialog(QDialog):
    def __init__(self, window, doc):
        super().__init__(window)
        self.window, self.doc = window, doc
        self.path, self.root = doc.path, window.root
        self.original = doc.editor.toPlainText()
        self.disk = doc.path.read_bytes()
        self.parts = parse_conflicts(self.original)
        self.chunks = [part for part in self.parts if isinstance(part, dict)]
        if not self.chunks:
            raise ValueError(
                'Dosyada desteklenen metin çakışma işaretleri yok. Silme/ikili dosya çakışmalarını Git üzerinden çözün.')
        self.setWindowTitle('Git çakışmalarını çöz — ' + doc.path.name)
        self.resize(1120, 760)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            'Her çakışma için seçim yapın. Sonuç alanını ayrıca düzenleyebilirsiniz. Yerel/Gelen etiketleri dosyadaki işaret sırasını gösterir.'))
        self.listing = QListWidget()
        self.listing.setMaximumHeight(100)
        for i, chunk in enumerate(self.chunks):
            self.listing.addItem(f'{i + 1}. çakışma · satır {chunk["line"]} · seçim bekliyor')
        self.listing.currentRowChanged.connect(self.show_chunk)
        layout.addWidget(self.listing)
        sides = QSplitter(Qt.Orientation.Horizontal)
        self.ours, self.theirs = QPlainTextEdit(), QPlainTextEdit()
        for title, view in [('Yerel (ilk taraf)', self.ours),
                            ('Gelen (ikinci taraf)', self.theirs)]:
            page = QWidget()
            box = QVBoxLayout(page)
            box.addWidget(QLabel(title))
            box.addWidget(view)
            view.setReadOnly(True)
            sides.addWidget(page)
        layout.addWidget(sides, 1)
        row = QHBoxLayout()
        for title, choice in [('Yereli kullan', 'ours'), ('Geleni kullan',
                                                          'theirs'), ('İkisini birleştir', 'both')]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, value=choice: self.choose(value))
            row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(
            QLabel('Sonuç · doğrudan düzenlenebilir (bir seçim değişirse sonuç yeniden oluşturulur)'))
        self.result = QPlainTextEdit()
        self.generated = self.original
        self.result.setPlainText(self.original)
        layout.addWidget(self.result, 2)
        footer = QHBoxLayout()
        for title, callback in [('Sonucu editöre aktar', lambda: self.apply(
                False)), ('Kaydet ve Git için hazırla', lambda: self.apply(True)), ('İptal', self.reject)]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            footer.addWidget(button)
        layout.addLayout(footer)
        self.listing.setCurrentRow(0)

    def show_chunk(self, index):
        if 0 <= index < len(self.chunks):
            self.ours.setPlainText(self.chunks[index]['ours'])
            self.theirs.setPlainText(self.chunks[index]['theirs'])

    def choose(self, choice):
        index = self.listing.currentRow()
        if index < 0:
            return
        if self.result.toPlainText() != self.generated and QMessageBox.question(
                self, 'Sonucu yeniden oluştur', 'Sonuç alanındaki elle yapılan değişiklikler sıfırlansın mı?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        chunk = self.chunks[index]
        chunk['choice'] = choice
        self.listing.item(index).setText(
            f'{
                index +
                1}. çakışma · satır {
                chunk["line"]} · {
                dict(
                    ours="Yerel",
                    theirs="Gelen",
                    both="İkisi")[choice]}')
        source = []
        for part in self.parts:
            if isinstance(part, str):
                source.append(part)
            elif part['choice'] == 'both':
                source.append(part['ours'] + part['theirs'])
            elif part['choice']:
                source.append(part[part['choice']])
            else:
                source.append(
                    '<<<<<<< seçim bekliyor\n' +
                    part['ours'] +
                    '=======\n' +
                    part['theirs'] +
                    '>>>>>>> seçim bekliyor\n')
        self.generated = ''.join(source)
        self.result.setPlainText(self.generated)
        if index + 1 < len(self.chunks):
            self.listing.setCurrentRow(index + 1)

    def apply(self, stage=False):
        text = self.result.toPlainText()
        if any((match := MARKER.match(line)) and match[1]
               [0] in '<>|' for line in text.splitlines()):
            self.window.message('Sonuçta çakışma işaretleri var. Önce tüm çakışmaları çözün.')
            return
        doc, window = self.doc, self.window
        if doc not in window.documents or doc.path != self.path or window.root != self.root or doc.editor.toPlainText() != self.original:
            window.message('Editör içeriği değişti. Çakışma ekranını yeniden açın.')
            return
        try:
            if doc.path.read_bytes() != self.disk:
                raise ValueError('Dosya dışarıda değişti. Çakışma ekranını yeniden açın.')
        except (OSError, ValueError) as error:
            window.message(str(error))
            return
        was_modified = doc.editor.document().isModified()
        cursor = doc.editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(cursor.SelectionType.Document)
        cursor.insertText(text)
        cursor.endEditBlock()
        if stage:
            if not window.save(doc=doc, allow_format=False):
                doc.editor.undo()
                doc.editor.document().setModified(was_modified)
                return
            window.git_operation(['--literal-pathspecs', 'add', '--',
                                 str(doc.path)], 'Çakışma çözümü Git için hazırlandı.')
        self.accept()
