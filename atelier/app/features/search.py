"""Main-window search actions."""
import re
import base64
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QListWidgetItem, QMessageBox
from atelier.editor.widget import units
from atelier.search.worker import SearchWorker
from atelier.runtime.tasks import TaskWorker


class SearchFeatures:
    def show_find(self):
        self.find_bar.show()
        if self.editor and self.editor.textCursor().hasSelection():
            self.find_text.setText(self.editor.textCursor().selectedText())
        self.find_text.setFocus()
        self.find_text.selectAll()

    def search_matcher(self):
        from atelier.search.patterns import pattern
        return pattern(self.find_text.text(), self.find_regex.isChecked(),
                       self.find_whole.isChecked(), self.find_case.isChecked())

    def find_next(self, backwards=False):
        if not self.editor or not self.find_text.text():
            return
        try:
            source = self.editor.toPlainText()
            matches = list(self.search_matcher().finditer(source))
        except re.error as error:
            self.statusBar().showMessage(str(error), 5000)
            return
        if not matches:
            self.statusBar().showMessage('Eşleşme bulunamadı.', 3000)
            return
        cursor = self.editor.textCursor()
        position = cursor.selectionStart() if backwards else cursor.selectionEnd()
        candidates = [m for m in matches if (
            units(source[:m.end()]) <= position if backwards else units(source[:m.start()]) >= position)]
        match = (candidates[-1] if candidates else matches[-1]
                 ) if backwards else (candidates[0] if candidates else matches[0])
        key = (self.find_text.text(), match.start(), match.end())
        if match.start() == match.end() and getattr(self, 'last_find', None) == key and len(matches) > 1:
            match = matches[(matches.index(match) + (-1 if backwards else 1)) % len(matches)]
        self.last_find = (self.find_text.text(), match.start(), match.end())
        cursor.setPosition(units(source[:match.start()]))
        cursor.setPosition(units(source[:match.end()]), QTextCursor.MoveMode.KeepAnchor)
        self.editor.reveal_line(cursor.blockNumber())
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()

    def replace_one(self):
        if not self.editor or not self.find_text.text():
            return
        source = self.editor.toPlainText()
        cursor = self.editor.textCursor()
        start = len(source.encode('utf-16-le')[:cursor.selectionStart() * 2].decode('utf-16-le'))
        end = len(source.encode('utf-16-le')[:cursor.selectionEnd() * 2].decode('utf-16-le'))
        try:
            match = self.search_matcher().match(source, start)
            if match and match.end() == end:
                value = match.expand(
                    self.replace_text.text()) if self.find_regex.isChecked() else self.replace_text.text()
                cursor.insertText(value)
        except re.error as error:
            self.statusBar().showMessage(str(error), 5000)
            return
        self.find_next()

    def replace_all(self):
        if not self.editor or not self.find_text.text():
            return
        source = self.editor.toPlainText()
        try:
            edits = []
            for match in self.search_matcher().finditer(source):
                value = match.expand(
                    self.replace_text.text()) if self.find_regex.isChecked() else self.replace_text.text()
                edits.append((units(source[:match.start()]), units(source[:match.end()]), value))
        except re.error as error:
            self.statusBar().showMessage(str(error), 5000)
            return
        cursor = QTextCursor(self.editor.document())
        cursor.beginEditBlock()
        for start, end, value in reversed(edits):
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(value)
        cursor.endEditBlock()
        self.statusBar().showMessage(f'{len(edits)} eşleşme değiştirildi.', 4000)

    def show_project_search(self):
        self.sidebar.show()
        self.sidebar.setCurrentIndex(1)
        self.project_query.setFocus()

    def cancel_search(self, clear=False):
        self.search_generation += 1
        for worker in list(self.workers):
            worker.requestInterruption()
        if clear:
            self.search_results.clear()
            self.search_label.setText('Proje dosyalarında arar')
        else:
            self.search_label.setText('Arama durduruldu.')

    def search_project(self):
        self.cancel_search(clear=True)
        generation = self.search_generation
        root = self.root
        query = self.project_query.text()
        if not query:
            return
        if len(self.workers) >= 2:
            self.search_label.setText('Önceki arama durduruluyor; tekrar deneyin.')
            return
        self.search_label.setText('Aranıyor…')
        worker = SearchWorker(
            self.root,
            query,
            self.project_case.isChecked(),
            self,
            regex=self.project_regex.isChecked(),
            whole=self.project_whole.isChecked(),
            globs=self.project_globs.text())
        self.track_worker(worker, self.workers)

        def receive(results):
            if self.closing or generation != self.search_generation:
                return
            for path, line, column, preview in results:
                item = QListWidgetItem(
                    f'{Path(path).relative_to(root)}:{line + 1}  {preview.strip()}')
                item.setData(Qt.ItemDataRole.UserRole, (path, line, column))
                item.setToolTip(preview)
                self.search_results.addItem(item)
            self.search_label.setText(f'{len(results)} eşleşme' +
                                      (' · ilk 5000' if len(results) == 5000 else ''))
        worker.results.connect(receive)
        worker.error.connect(lambda text: self.search_label.setText(
            text) if generation == self.search_generation else None)
        worker.start()

    def open_search_result(self, item):
        path, line, column = item.data(Qt.ItemDataRole.UserRole)
        doc = self.open_path(path)
        if doc:
            text = doc.editor.document().findBlockByNumber(line).text()
            self.goto(doc, {'line': line, 'character': units(text[:column])})

    def replace_project(self):
        query, replacement = self.project_query.text(), self.project_replace.text()
        if not query:
            return
        if any(doc.editor.document().isModified() for doc in self.documents):
            self.message('Projede değiştirmeden önce açık belgeleri kaydedin.')
            return
        self.cancel_search(clear=True)
        if len(self.workers) >= 2:
            self.search_label.setText('Önceki arama durduruluyor; tekrar deneyin.')
            return
        generation, root = self.search_generation, self.root
        self.search_label.setText('Değiştirme önizlemesi hazırlanıyor…')
        worker = TaskWorker('replace', dict(root=str(root), query=query, replacement=replacement,
                                            case=self.project_case.isChecked(), regex=self.project_regex.isChecked(),
                                            whole=self.project_whole.isChecked(), globs=self.project_globs.text()), self)

        def preview(rows):
            if self.closing or generation != self.search_generation:
                return
            self.search_label.setText(f'{len(rows)} dosyada değişiklik')
            if not rows:
                return
            count = sum(row['count'] for row in rows)
            dialog = QMessageBox(self)
            dialog.setWindowTitle('Projedeki değişiklikleri uygula')
            dialog.setText(f'{len(rows)} dosyada {count} eşleşme değiştirilecek. Devam edilsin mi?')
            dialog.setInformativeText(f'{query!r} → {replacement!r}')
            dialog.setDetailedText(
                '\n'.join(str(Path(row['path']).relative_to(root)) for row in rows))
            dialog.setStandardButtons(QMessageBox.StandardButton.Ok |
                                      QMessageBox.StandardButton.Cancel)
            dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if dialog.exec() != QMessageBox.StandardButton.Ok or generation != self.search_generation:
                return
            if any(doc.editor.document().isModified() for doc in self.documents):
                self.message('Önizlemeden sonra bir belge düzenlendi. Tekrar arayın.')
                return
            for row in rows:
                path = Path(row['path'])
                try:
                    if path.is_symlink() or path.read_bytes() != base64.b64decode(row['original']):
                        raise OSError('Dosya değişti')
                except OSError:
                    self.message(
                        f'{path.name} değişmiş veya okunamıyor. İşlem uygulanmadı; tekrar arayın.')
                    return
            for row in rows:
                doc = self.open_path(row['path'])
                if not doc:
                    break
                self.replace_document_text(doc, row['updated'])
                if not self.save(doc=doc, allow_format=False):
                    break
            self.search_project()
        worker.results.connect(preview)
        worker.error.connect(lambda text: self.search_label.setText(
            text) if generation == self.search_generation else None)
        self.track_worker(worker, self.workers)
        worker.start()
