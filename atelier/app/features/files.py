"""Main-window files actions."""
import io
import os
import time
import tokenize
import uuid
import difflib
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox
from atelier.projects.settings import SAVE_ACTIONS
from atelier.languages.formatting import LANGUAGES as WEB_FORMAT_LANGUAGES
from atelier.runtime.tasks import TaskWorker
from atelier.storage.history import HistoryDialog
from atelier.editor.document import Document


class FilesFeatures:
    def set_format_on_save(self, enabled):
        self.format_on_save = enabled
        self.store_save_actions()

    def store_save_actions(self):
        self.project_profiles.save_actions(
            self.root, {
                name: getattr(
                    self, name) for name in SAVE_ACTIONS})

    def new(self):
        return self.add_document(Document(self))

    def add_document(self, doc):
        self.documents.append(doc)
        if doc.path:
            self.restore_breakpoints(doc, self.closed_breakpoints.pop(str(doc.path), {}))
        self.tabs.addTab(doc, self.doc_name(doc))
        self.tabs.setCurrentWidget(doc)
        self.open_document(doc)
        self.file_monitor.track(doc)
        if doc.path and str(doc.path) in self.coverage_data:
            for editor in doc.editors:
                editor.coverage_lines = dict(self.coverage_data[str(doc.path)])
            doc.paint_diagnostics()
        doc.editor.setFocus()
        return doc

    def doc_name(self, doc):
        return doc.path.name if doc.path else 'Adsız.py'

    def refresh_tabs(self):
        for i in range(self.tabs.count()):
            doc = self.tabs.widget(i)
            self.tabs.setTabText(
                i,
                ('● ' if doc.editor.document().isModified() else '') +
                self.doc_name(doc))
            self.tabs.setTabToolTip(i, str(doc.path or 'Kaydedilmemiş belge'))

    def tab_changed(self, *_):
        self.dismiss_definition_preview()
        self.profile_selector.refresh()
        for doc in self.documents:
            for editor in doc.editors:
                editor.popup.hide()
        self.update_position()
        if self.current:
            self.current.diagnostics_timer.start()
        if hasattr(self, 'git_timer'):
            self.git_refresh_timer.start()

    def cycle_tabs(self, step=1):
        count = self.tabs.count()
        if count < 2:
            return
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % count)
        self.current.editor.setFocus()

    def reopen_closed_tab(self):
        while self.closed_tabs:
            path, index, position, scroll = self.closed_tabs.pop()
            if not path.is_file() or any(doc.path == path for doc in self.documents):
                continue
            doc = self.open_path(path)
            if doc:
                bar = self.tabs.tabBar()
                bar.moveTab(self.tabs.indexOf(doc), min(index, self.tabs.count() - 1))
                cursor = doc.editor.textCursor()
                cursor.setPosition(min(position, doc.editor.document().characterCount() - 1))
                doc.editor.setTextCursor(cursor)
                doc.editor.verticalScrollBar().setValue(scroll)
            return
        self.statusBar().showMessage('Yeniden açılabilecek kapalı sekme yok.', 3500)

    def open(self):
        from atelier.editor.highlighting import FILE_LANGUAGES
        extensions = ' '.join('*' + suffix for suffix in FILE_LANGUAGES)
        names, _ = QFileDialog.getOpenFileNames(self, 'Dosya aç', str(
            self.root), f'Kod ve ayar dosyaları ({extensions});;Tüm dosyalar (*)')
        for name in names:
            self.open_path(name)

    def open_path(self, path):
        path = Path(path).resolve()
        existing = next((doc for doc in self.documents if doc.path == path), None)
        if existing:
            self.tabs.setCurrentWidget(existing)
            return existing
        if not path.is_file():
            return None
        try:
            if path.stat().st_size > 25_000_000:
                self.message('25 MB üzerindeki dosyalar açılamıyor.')
                return None
            if path.suffix.lower() in ('.py', '.pyw'):
                with tokenize.open(path) as source:
                    text = source.read()
            else:
                text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError, SyntaxError) as error:
            self.message(str(error))
            return None
        return self.add_document(Document(self, path, text))

    def save(self, save_as=False, doc=None, allow_format=True):
        doc = doc or self.current
        if not doc:
            return False
        target = doc.path
        if save_as or target is None:
            name, _ = QFileDialog.getSaveFileName(self, 'Dosyayı kaydet', str(
                target or self.root / 'main.py'), 'Python (*.py);;Tüm dosyalar (*)')
            if not name:
                return False
            target = Path(name).resolve()
        if any(d is not doc and d.path == target for d in self.documents):
            self.message('Bu dosya başka bir sekmede açık.')
            return False
        self.cancel_save(doc)
        if not self.write_document(doc, target):
            return False
        if allow_format and not doc.large_file:
            self.run_save_actions(doc, target)
        return True

    def cancel_save(self, doc):
        self.save_queue.pop(doc, None)
        if doc.save_worker:
            doc.save_worker.requestInterruption()
            doc.save_worker = None

    def run_save_actions(self, doc, target):
        if not self.project_trusted:
            return
        from atelier.projects.config import load_project_config
        options = {name: getattr(self, name) for name in SAVE_ACTIONS}
        try:
            options.update(load_project_config(self.root)['save'])
        except ValueError as error:
            self.statusBar().showMessage(str(error), 8000)
            return
        if doc.language != 'python':
            options['format_on_save'] = options['save_imports'] = False
        if doc.language not in WEB_FORMAT_LANGUAGES:
            options['format_web_on_save'] = False
        if not any(options.values()):
            return
        self.save_queue[doc] = (target, self.root, doc.saved_text, doc.edit_generation, options)
        self.pump_save_actions()

    def pump_save_actions(self):
        while not self.closing and self.save_queue and len(self.save_workers) < 2:
            doc = next(iter(self.save_queue))
            target, root, source, generation, options = self.save_queue.pop(doc)
            if doc in self.documents and doc.path == target and self.root == root and doc.edit_generation == generation:
                self.launch_save_actions(doc, target, root, source, generation, options)

    def launch_save_actions(self, doc, target, root, source, generation,
                            options, manual=False, after=None):
        worker = TaskWorker('save', dict(root=str(root), path=str(target), source=source, options=options,
                                         language=doc.language, python=doc.language == 'python',
                                         markdown=doc.language == 'markdown'), self, 12000)
        doc.save_worker = worker

        def receive(edits):
            if self.closing or doc.save_worker is not worker or doc not in self.documents or doc.path != target or self.root != root:
                return
            if doc.edit_generation != generation or doc.editor.toPlainText() != source:
                self.statusBar().showMessage('Belge yeniden düzenlendiği için biçimlendirme sonucu uygulanmadı.', 4000)
                return
            if manual:
                if edits:
                    self.apply_edits(doc, edits)
                if after:
                    after()
                return
            try:
                if self.file_monitor.has_conflict(doc, target):
                    self.statusBar().showMessage('Kayıt işlemi atlandı: dosya dışarıda değişti.', 4000)
                    return
            except OSError:
                return
            if edits:
                self.apply_edits(doc, edits)
                self.write_document(doc, target)

        def finished():
            if doc.save_worker is worker:
                doc.save_worker = None
        worker.results.connect(receive)
        if manual:
            worker.error.connect(self.message)
        else:
            worker.error.connect(
                lambda error: self.statusBar().showMessage(
                    'Kayıt işlemi atlandı: ' + error, 6000))
        worker.finished.connect(finished)
        self.track_worker(worker, self.save_workers)
        worker.finished.connect(self.pump_save_actions)
        worker.start()

    def write_document(self, doc, target):
        if doc not in self.documents:
            return False
        try:
            if self.file_monitor.has_conflict(doc, target):
                choice = QMessageBox.question(self, 'Dış değişiklik',
                                              f'{
                                                  target.name} dışarıda değişti veya silindi. Diskteki sürümün üzerine yerel içerik yazılsın mı?',
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
                if choice != QMessageBox.StandardButton.Yes:
                    return False
            text = doc.editor.toPlainText()
            if target.exists() and not doc.large_file:
                try:
                    with (tokenize.open(target) if target.suffix.lower() in ('.py', '.pyw') else target.open(encoding='utf-8')) as old:
                        self.file_history.snapshot(target, old.read())
                except (OSError, UnicodeError, SyntaxError) as error:
                    self.statusBar().showMessage('Önceki sürüm geçmişe yazılamadı: ' + str(error), 5000)
            encoding = 'utf-8'
            if target.suffix in ('.py', '.pyw'):
                encoding, _ = tokenize.detect_encoding(io.BytesIO(text.encode('utf-8')).readline)
            payload = text.encode(encoding)
            # Replace atomically so interrupted writes do not truncate existing files.
            temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
            try:
                temporary.write_bytes(payload)
                expected = self.file_monitor.stat(target)
                for delay in (0.015, 0.035, 0.070, 0.120, None):
                    try:
                        os.replace(temporary, target)
                        break
                    except OSError as error:
                        # Windows scanners/readers can briefly deny an atomic replace.
                        if os.name != 'nt' or getattr(error, 'winerror', None) not in (
                                5, 32, 33) or delay is None:
                            raise
                        time.sleep(delay)
                        if self.file_monitor.stat(target) != expected:
                            raise OSError(
                                'Dosya kayıt sırasında dışarıda değişti; yerel içerik korunuyor.') from error
            finally:
                if temporary.exists():
                    temporary.unlink()
        except (OSError, UnicodeError, SyntaxError) as error:
            self.message(str(error))
            return False
        if doc.path != target:
            if self.lsp.initialized and doc.synced is not None:
                self.lsp.notify('textDocument/didClose', {'textDocument': {'uri': doc.uri}})
            doc.path = target
            doc.uri = target.as_uri()
            doc.synced = None
            doc.update_language()
            self.open_document(doc)
            doc.breadcrumb.setText(str(target))
        self.sync_document(doc)
        if self.lsp.initialized and doc.synced is not None:
            self.lsp.notify('textDocument/didSave', {'textDocument': {'uri': doc.uri}})
        doc.editor.document().setModified(False)
        doc.saved_text = text
        if not doc.large_file:
            try:
                self.file_history.snapshot(target, text)
            except OSError as error:
                self.statusBar().showMessage('Geçmiş kaydı yazılamadı: ' + str(error), 5000)
        doc.external_pending = False
        doc.external_bar.hide()
        self.file_monitor.track(doc)
        self.refresh_tabs()
        if doc is self.current or target == self.root / 'atelier.toml':
            self.profile_selector.refresh()
        self.git_refresh_timer.start()
        return True

    def save_all(self, allow_format=True):
        for doc in list(self.documents):
            if (doc.editor.document().isModified() or (doc is self.current and doc.path is None)
                ) and not self.save(doc=doc, allow_format=allow_format):
                return False
        return True

    def confirm_saved(self, doc):
        if not doc.editor.document().isModified():
            return True
        self.tabs.setCurrentWidget(doc)
        choice = QMessageBox.question(self, 'Kaydedilmemiş değişiklikler', f'{self.doc_name(doc)} kaydedilsin mi?',
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        return choice == QMessageBox.StandardButton.Discard or (
            choice == QMessageBox.StandardButton.Save and self.save(doc=doc, allow_format=False))

    def close_tab(self, index):
        doc = self.tabs.widget(index)
        if not isinstance(doc, Document) or not self.confirm_saved(doc):
            return
        if doc.path and doc.path.is_file():
            self.closed_tabs = [entry for entry in self.closed_tabs if entry[0] != doc.path]
            self.closed_tabs.append((doc.path, index, doc.editor.textCursor().position(),
                                     doc.editor.verticalScrollBar().value()))
            del self.closed_tabs[:-25]
        if doc.path and doc.breakpoints:
            self.closed_breakpoints[str(doc.path)] = {
                line: doc.breakpoint_conditions.get(line, '') for line in doc.breakpoints
            }
        self.remove_document(doc)
        if not self.documents and not self.closing:
            self.new()

    def remove_document(self, doc):
        self.dismiss_definition_preview()
        self.cancel_save(doc)
        doc.timer.stop()
        doc.completion_timer.stop()
        doc.markdown_timer.stop()
        doc.diagnostics_timer.stop()
        doc.validation_timer.stop()
        self.validation_pending.discard(doc)
        if doc.validation_worker:
            doc.validation_worker.requestInterruption()
        for editor in doc.editors:
            editor.signature_timer.stop()
            editor.hover_timer.stop()
            editor.popup.hide()
            editor.signature_popup.hide()
        self.file_monitor.untrack(doc)
        if self.lsp.initialized and doc.synced is not None:
            self.lsp.notify('textDocument/didClose', {'textDocument': {'uri': doc.uri}})
        self.documents.remove(doc)
        self.tabs.removeTab(self.tabs.indexOf(doc))
        doc.deleteLater()
        self.refresh_problems()

    def external_changed(self, doc, digest):
        if doc not in self.documents:
            return
        doc.external_pending = True
        doc.external_label.setText('Dosya diskte silindi. Yerel içeriğiniz korunuyor.' if digest is None else
                                   'Dosya başka bir uygulama tarafından değiştirildi. Yerel içeriğiniz korunuyor.')
        doc.external_bar.show()
        self.refresh_tabs()

    def reload_document(self, doc, confirm=True):
        if not doc.path or not doc.path.exists():
            self.message('Dosya diskte bulunamadı. Yerel içeriği kaydedebilirsiniz.')
            return False
        if confirm and doc.editor.document().isModified():
            answer = QMessageBox.question(self, 'Diskten yeniden yükle',
                                          'Kaydedilmemiş yerel değişiklikler silinecek. Diskteki içerik yüklensin mi?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Yes:
                return False
        try:
            if doc.path.suffix.lower() in ('.py', '.pyw'):
                with tokenize.open(doc.path) as source:
                    text = source.read()
            else:
                text = doc.path.read_text(encoding='utf-8')
        except (OSError, UnicodeError, SyntaxError) as error:
            self.message(str(error))
            return False
        position = doc.editor.textCursor().position()
        self.apply_edits(doc, [{'range': {'start': {'line': 0, 'character': 0},
                                          'end': {'line': doc.editor.blockCount(), 'character': 0}}, 'newText': text}])
        cursor = doc.editor.textCursor()
        cursor.setPosition(min(position, doc.editor.document().characterCount() - 1))
        doc.editor.setTextCursor(cursor)
        doc.editor.document().setModified(False)
        doc.saved_text = text
        doc.external_pending = False
        doc.external_bar.hide()
        self.file_monitor.track(doc)
        self.sync_document(doc)
        self.refresh_tabs()
        return True

    def compare_external(self, doc):
        try:
            if doc.path.suffix.lower() in ('.py', '.pyw'):
                with tokenize.open(doc.path) as source:
                    disk = source.read()
            else:
                disk = doc.path.read_text(encoding='utf-8')
        except (OSError, UnicodeError, SyntaxError) as error:
            self.message(str(error))
            return
        difference = ''.join(difflib.unified_diff(doc.editor.toPlainText().splitlines(keepends=True),
                                                  disk.splitlines(keepends=True), fromfile='Editördeki yerel içerik', tofile='Diskteki içerik'))
        self.show_text('Dış değişikliği karşılaştır', difference or 'İçerikler aynı.')

    def export_markdown(self, doc):
        doc.render_markdown()
        name, _ = QFileDialog.getSaveFileName(self, 'HTML dışa aktar', str(
            (doc.path or self.root / 'document.md').with_suffix('.html')), 'HTML (*.html)')
        if name:
            try:
                Path(name).write_text(doc.preview.rendered_html, encoding='utf-8')
                self.statusBar().showMessage('HTML dosyası kaydedildi.', 4000)
            except OSError as error:
                self.message(str(error))

    def show_file_history(self):
        if self.current and self.current.path:
            HistoryDialog(self, self.current).exec()
        else:
            self.message('Geçmiş için önce dosyayı kaydedin.')
