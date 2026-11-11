"""Main-window language actions."""
import html
import re
import difflib
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QListWidgetItem, QInputDialog, QToolTip
from atelier.languages.lsp import Lsp
from atelier.languages.validation import LANGUAGES as VALIDATED_LANGUAGES
from atelier.languages.formatting import LANGUAGES as WEB_FORMAT_LANGUAGES
from atelier.runtime.tasks import TaskWorker
from atelier.languages.locations import definition_target, uri_path


class LanguageFeatures:
    def start_lsp(self):
        self.dismiss_definition_preview()
        self.profile_selector.refresh()
        if self.lsp:
            self.lsp.pending.clear()
            self.lsp.stop()
            self.lsp.deleteLater()
        for doc in self.documents:
            doc.synced = None
            if doc.language == 'python':
                doc.diagnostics = []
            for editor in doc.editors:
                editor.popup.hide()
                editor.signature_popup.hide()
            doc.paint_diagnostics()
        self.refresh_problems()
        self.lsp = Lsp(self, self.root, self.interpreter)
        self.lsp.ready.connect(self.lsp_ready)
        self.lsp.status.connect(self.lsp_status)
        self.lsp.diagnostics.connect(self.diagnostics)
        if not self.project_trusted:
            self.python_label.setText('Python')
            self.python_label.setToolTip('Proje güveni gerekli')
            self.lsp_label.setText('● LSP kısıtlı')
            self.python_status_changed.emit()
            return
        if not self.interpreter:
            from atelier.projects.environments import PYTHON_MISSING
            self.python_label.setText('Python bulunamadı')
            self.python_label.setToolTip(PYTHON_MISSING)
            self.lsp_label.setText('● LSP kapalı')
            self.statusBar().showMessage(PYTHON_MISSING, 8000)
            self.python_status_changed.emit()
            return
        self.lsp_label.setText('● LSP başlatılıyor')
        self.lsp.start_server()
        self.python_label.setText('Python · ' + Path(self.interpreter).parent.name)
        self.python_label.setToolTip(self.interpreter)
        self.python_status_changed.emit()

    def lsp_status(self, text):
        if text == 'LSP hazır':
            self.lsp_label.setText('● LSP hazır')
        elif 'durdu' in text or 'başlatılamadı' in text:
            self.lsp_label.setText('● LSP bağlantısı yok')
        self.statusBar().showMessage(text, 8000)
        self.python_status_changed.emit()

    def lsp_ready(self):
        for doc in self.documents:
            self.open_document(doc)

    def open_document(self, doc):
        if doc.large_file or doc.synced is not None or not self.lsp or not self.lsp.initialized:
            return
        if doc.path and doc.path.suffix.lower() not in ('.py', '.pyw'):
            return
        doc.version += 1
        doc.synced = doc.editor.toPlainText()
        self.lsp.notify('textDocument/didOpen', {'textDocument': {'uri': doc.uri,
                                                                  'languageId': 'python', 'version': doc.version, 'text': doc.synced}})

    def sync_document(self, doc):
        doc.timer.stop()
        if doc.large_file or doc.synced is None:
            return
        text = doc.editor.toPlainText()
        if self.lsp.initialized and doc.synced is not None and text != doc.synced:
            doc.version += 1
            doc.synced = text
            self.lsp.notify('textDocument/didChange', {'textDocument': {'uri': doc.uri, 'version': doc.version},
                                                       'contentChanges': [{'text': text}]})

    def diagnostics(self, params):
        for doc in self.documents:
            if not doc.large_file and doc.synced is not None and params.get('uri') == doc.uri:
                if params.get('version') is not None and params['version'] != doc.version:
                    return
                if doc.editor.toPlainText() != doc.synced:
                    return
                doc.diagnostics = params.get('diagnostics', [])
                doc.paint_diagnostics()
                self.refresh_problems()
                break

    def refresh_problems(self):
        self.problems.clear()
        for doc in self.documents:
            for diagnostic in doc.diagnostics:
                pos = diagnostic['range']['start']
                icon = '●' if diagnostic.get('severity', 1) == 1 else '▲'
                item = QListWidgetItem(
                    f"{icon}  {
                        self.doc_name(doc)}:{
                        pos['line'] +
                        1}:{
                        pos['character'] +
                        1}   {
                        diagnostic['message']}")
                item.setData(Qt.ItemDataRole.UserRole, (doc.uri, pos))
                self.problems.addItem(item)
        self.bottom.setTabText(0, f'Sorunlar · {self.problems.count()}')

    def queue_validation(self, doc):
        if doc in self.documents and doc.language in VALIDATED_LANGUAGES and not doc.large_file:
            self.validation_pending.add(doc)
            self.pump_validation()

    def pump_validation(self):
        if self.closing:
            return
        while len(self.validation_workers) < 2:
            doc = next(
                (item for item in self.validation_pending if item.validation_worker is None),
                None)
            if doc is None:
                return
            self.validation_pending.remove(doc)
            if doc in self.documents and doc.language in VALIDATED_LANGUAGES and not doc.large_file:
                self.validate_document(doc)

    def validate_document(self, doc):
        generation = doc.edit_generation
        path, language = doc.path, doc.language
        worker = TaskWorker('validate', dict(source=doc.editor.toPlainText(), language=language,
                                             filename=path.name if path else ''), self, 5000)
        doc.validation_worker = worker

        def receive(problems):
            if (not self.closing and doc in self.documents and not doc.large_file and
                    doc.path == path and doc.language == language and doc.edit_generation == generation):
                doc.diagnostics = problems
                doc.paint_diagnostics()
                self.refresh_problems()

        def finished():
            if doc.validation_worker is worker:
                doc.validation_worker = None

        worker.results.connect(receive)
        worker.error.connect(
            lambda error: self.statusBar().showMessage(
                'Doğrulama: ' + error, 6000))
        worker.finished.connect(finished)
        self.track_worker(worker, self.validation_workers)
        worker.finished.connect(self.pump_validation)
        worker.start()

    def goto_problem(self, item):
        uri, pos = item.data(Qt.ItemDataRole.UserRole)
        doc = next((d for d in self.documents if d.uri == uri), None)
        if doc:
            self.goto(doc, pos)

    def request_at(self, method, callback, doc=None, editor=None, position=None):
        doc = doc or self.current
        if not doc or doc.large_file or not self.lsp.initialized:
            return
        client = self.lsp
        editor = editor or doc.editor
        self.sync_document(doc)
        if doc.synced is None:
            return
        cursor = editor.textCursor() if position is None else editor.cursorForPosition(position)
        snapshot = (doc.uri, doc.version, cursor.position(), editor.toPlainText())

        def receive(result):
            if self.closing or self.lsp is not client or doc not in self.documents or editor not in doc.editors or doc.uri != snapshot[
                    0] or doc.version != snapshot[1] or editor.toPlainText() != snapshot[3]:
                return
            if position is None and editor.textCursor().position() != snapshot[2]:
                return
            callback(result)
        self.lsp.request(method, {'textDocument': {'uri': doc.uri},
                                  'position': {'line': cursor.blockNumber(), 'character': cursor.positionInBlock()}}, receive)

    def complete(self, doc=None):
        doc = doc or self.current
        if not doc or doc.large_file or doc is not self.current:
            return
        editor = doc.editor
        if doc.language == 'html':
            from atelier.languages.html import completion_context, suggestions
            before, after = completion_context(editor.textCursor())
            editor.popup.clear()
            for label, template, prefix, consume in suggestions(before, after):
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, {'_html': (template, prefix, consume)})
                editor.popup.addItem(item)
            self.show_completion_popup(editor)
            return

        def receive(result):
            items = result.get('items', []) if isinstance(result, dict) else result or []
            popup = editor.popup
            popup.clear()
            from atelier.editor.snippets import templates_for
            cursor = editor.textCursor()
            before = cursor.block().text().encode(
                'utf-16-le')[:cursor.positionInBlock() * 2].decode('utf-16-le', 'ignore')
            prefix = re.search(r'\w*$', before).group()
            if prefix:
                for key in templates_for(doc.language):
                    if key.startswith(prefix):
                        row = QListWidgetItem(key + '  · şablon')
                        row.setData(Qt.ItemDataRole.UserRole, {'label': key, '_snippet': key})
                        popup.addItem(row)
            for data in items[:150]:
                if data.get('insertTextFormat', 1) == 2:
                    continue
                row = QListWidgetItem(data['label'])
                row.setData(Qt.ItemDataRole.UserRole, data)
                row.setToolTip(data.get('detail', ''))
                popup.addItem(row)
            if self.current is doc and doc.editor is editor:
                self.show_completion_popup(editor)
        if doc.language == 'python':
            self.request_at('textDocument/completion', receive, doc)
        else:
            receive([])

    def show_completion_popup(self, editor):
        popup = editor.popup
        if not popup.count():
            popup.hide()
            return
        popup.setCurrentRow(0)
        popup.resize(440, min(280, popup.count() * 27 + 12))
        popup.move(editor.viewport().mapToGlobal(editor.cursorRect().bottomLeft()))
        popup.show()

    def signature(self, doc, editor):
        def receive(result):
            editor.signature_popup.update_help(result)
        self.request_at('textDocument/signatureHelp', receive, doc, editor)

    def hover(self, doc, editor, pos):
        if pos is None or self.current is not doc or editor not in doc.editors:
            return
        cursor = editor.cursorForPosition(pos)
        if self.debugger.thread is not None and editor.execution_line:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            expression = cursor.selectedText()
            if expression.isidentifier():
                generation = self.debugger.frame_generation

                def show_value(result):
                    if self.closing or self.current is not doc or editor not in doc.editors or editor.hover_position != pos or generation != self.debugger.frame_generation:
                        return
                    if 'result' in result:
                        type_name = result.get('type', '')
                        value = expression + \
                            (f' ({type_name})' if type_name else '') + \
                            ' = ' + str(result['result'])[:2000]
                        QToolTip.showText(
                            editor.viewport().mapToGlobal(pos),
                            '<pre>' + html.escape(value) + '</pre>',
                            editor)
                self.debugger.evaluate(expression, show_value, context='hover')
                return
        for diagnostic in doc.diagnostics:
            region = diagnostic['range']
            if editor.offset(region['start']) <= cursor.position() <= editor.offset(region['end']):
                QToolTip.showText(
                    editor.viewport().mapToGlobal(pos), html.escape(
                        diagnostic['message']), editor)
                return

        def receive(result):
            if editor.hover_position != pos or self.current is not doc:
                return
            content = result.get('contents') if result else None
            if not content:
                return
            if not isinstance(content, list):
                content = [content]
            text = '\n\n'.join(c.get('value', '') if isinstance(c, dict) else c for c in content)
            QToolTip.showText(editor.viewport().mapToGlobal(pos), '<pre>' +
                              html.escape(text[:4000]) + '</pre>', editor)
        self.request_at('textDocument/hover', receive, doc, editor, pos)

    def definition(self):
        def receive(result):
            if target := definition_target(result):
                self.open_definition(*target)
        self.request_at('textDocument/definition', receive)

    def definition_document(self, path):
        uri = path.as_uri()
        return next((doc for doc in self.documents if doc.path == path or doc.uri == uri), None)

    def open_definition(self, path, position):
        self.remember_location()
        target = self.definition_document(path) or self.open_path(path)
        if target:
            self.goto(target, position, record=False)
            self.remember_location()

    def dismiss_definition_preview(self, restore_focus=False):
        self.definition_preview_generation += 1
        preview = self.definition_preview
        self.definition_preview = None
        if preview:
            editor = preview.editor
            preview.close()
            if restore_focus and self.editor is editor:
                editor.setFocus()

    def peek_definition(self):
        doc, editor = self.current, self.editor
        if not doc or doc.language != 'python' or doc.large_file or not self.lsp.initialized:
            self.statusBar().showMessage('Tanım önizlemesi için Python dil sunucusu hazır olmalı.', 4500)
            return
        self.dismiss_definition_preview()
        generation = self.definition_preview_generation

        def receive(result):
            if self.definition_preview_generation != generation or self.current is not doc or self.editor is not editor:
                return
            target = definition_target(result)
            if not target:
                self.statusBar().showMessage('Tanım bulunamadı.', 3500)
                return
            from atelier.ui.definition_preview import DefinitionPreview, definition_excerpt
            path, position = target
            target_doc = self.definition_document(path)
            try:
                text, highlight_line = definition_excerpt(
                    path, position['line'], target_doc.editor.toPlainText() if target_doc else None)
            except (OSError, ValueError, SyntaxError) as error:
                self.statusBar().showMessage(str(error), 4500)
                return

            def open_target():
                self.dismiss_definition_preview()
                self.open_definition(path, position)

            preview = DefinitionPreview(
                editor, path, position['line'], text, highlight_line, open_target,
                lambda checked=False: self.dismiss_definition_preview(restore_focus=True))
            self.definition_preview = preview
            preview.reposition()
            preview.show()
            preview.raise_()
            preview.code.setFocus()

        self.request_at('textDocument/definition', receive, doc, editor)

    def rename_symbol(self):
        if not self.current or not self.lsp.initialized:
            return
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        value, ok = QInputDialog.getText(
            self, 'Sembolü yeniden adlandır', 'Yeni Python adı:', text=cursor.selectedText())
        if not ok or not value:
            return
        if not value.isidentifier() or __import__('keyword').iskeyword(value):
            self.message('Geçerli bir Python adı girin.')
            return
        doc = self.current
        self.sync_document(doc)
        version, source = doc.version, doc.editor.toPlainText()

        def receive(result):
            if doc not in self.documents or doc.version != version or doc.editor.toPlainText() != source:
                self.message('Belge değişti. Yeniden adlandırmayı tekrar deneyin.')
                return
            self.apply_workspace_edit(result)
        self.lsp.request('textDocument/rename', {'textDocument': {'uri': doc.uri},
                                                 'position': {'line': cursor.blockNumber(), 'character': cursor.positionInBlock()}, 'newName': value}, receive)

    def apply_workspace_edit(self, result):
        if not result:
            self.message('Bu sembol için değişiklik bulunamadı.')
            return False
        changes = dict(result.get('changes', {}))
        for change in result.get('documentChanges', []):
            if 'textDocument' not in change:
                self.message('Dosya oluşturma/taşıma içeren değişiklik desteklenmiyor.')
                return False
            descriptor = change['textDocument']
            opened = next((d for d in self.documents if d.uri == descriptor['uri']), None)
            if opened and descriptor.get(
                    'version') is not None and descriptor['version'] != opened.version:
                self.message('Belge değişti. Yeniden adlandırmayı tekrar deneyin.')
                return False
            changes[change['textDocument']['uri']] = change.get('edits', [])
        prepared = []
        for uri, edits in changes.items():
            doc = next((d for d in self.documents if d.uri == uri), None)
            if not doc:
                doc = self.open_path(uri_path(uri))
            if not doc:
                return False
            prepared.append((doc, edits))
        for doc, edits in prepared:
            self.apply_edits(doc, edits)
        self.statusBar().showMessage(
            f'{len(prepared)} dosyada değişiklik uygulandı. Kaydetmek için Ctrl+Alt+S.', 7000)
        return True

    def apply_edits(self, doc, edits):
        editor = doc.editor
        for view in doc.editors:
            view.secondary_cursors = []
        operations = [
            (editor.offset(
                edit['range']['start']), editor.offset(
                edit['range']['end']), edit['newText']) for edit in edits]
        cursor = QTextCursor(editor.document())
        cursor.beginEditBlock()
        for start, end, text in sorted(operations, key=lambda x: x[0], reverse=True):
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(text)
        cursor.endEditBlock()

    def format_document(self, doc=None, after=None):
        doc = doc or self.current
        if not doc:
            return
        if doc.large_file or doc.language not in (WEB_FORMAT_LANGUAGES | {'python'}):
            if after:
                after()
            return
        if doc.language in WEB_FORMAT_LANGUAGES:
            self.cancel_save(doc)
            if len(self.save_workers) >= 2:
                self.statusBar().showMessage('Biçimlendirme işlemleri sürüyor. Biraz sonra tekrar deneyin.', 5000)
                return
            self.launch_save_actions(doc, doc.path, self.root, doc.editor.toPlainText(),
                                     doc.edit_generation, {'format_web_on_save': True},
                                     manual=True, after=after)
            return
        if not self.lsp.initialized:
            self.message('Biçimlendirme için LSP bağlantısını bekleyin.')
            return
        self.sync_document(doc)
        source = doc.editor.toPlainText()
        client = self.lsp

        def receive(result):
            if not self.closing and self.lsp is client and doc in self.documents and doc.editor.toPlainText() == source:
                if result:
                    self.apply_edits(doc, result)
                if after:
                    after()
        self.lsp.request('textDocument/formatting', {'textDocument': {'uri': doc.uri},
                                                     'options': {'tabSize': 4, 'insertSpaces': True}}, receive)

    def replace_document_text(self, doc, text):
        self.apply_edits(doc, [{'range': {'start': {'line': 0, 'character': 0}, 'end': {
                         'line': doc.editor.blockCount(), 'character': 0}}, 'newText': text}])

    def python_refactor(self, kind):
        if not self.require_project_trust():
            return
        doc = self.current
        if not doc or doc.language != 'python':
            return
        cursor = doc.editor.textCursor()
        source = doc.editor.toPlainText()
        if kind != 'imports' and not cursor.hasSelection():
            self.message('Önce çıkarılacak ifadeyi veya kod bloğunu seçin.')
            return
        name = None
        if kind != 'imports':
            name, ok = QInputDialog.getText(
                self, 'Fonksiyona çıkar' if kind == 'method' else 'Değişkene çıkar', 'Yeni ad:')
            import keyword
            if not ok:
                return
            if not name.isidentifier() or keyword.iskeyword(name):
                self.message('Geçerli bir Python adı girin.')
                return
        if not self.save(doc=doc, allow_format=False):
            return
        start = len(source.encode('utf-16-le')[:cursor.selectionStart() * 2].decode('utf-16-le'))
        end = len(source.encode('utf-16-le')[:cursor.selectionEnd() * 2].decode('utf-16-le'))
        project = None
        try:
            from atelier.languages.python_tools import code_changes
            project, changes = code_changes(self.root, doc.path, kind, name, start, end)
            if not changes:
                self.message('Uygulanacak değişiklik yok.')
                return
            if not self.review_change('Python refactor önizlemesi', changes.get_description()):
                return
            project.do(changes)
            self.reload_document(doc, confirm=False)
            self.file_history.snapshot(doc.path, doc.editor.toPlainText())
        except Exception as error:
            self.message(str(error))
        finally:
            if project:
                project.close()

    def add_missing_import(self):
        if not self.require_project_trust():
            return
        doc = self.current
        if not doc or doc.language != 'python':
            return
        try:
            from atelier.languages.python_tools import missing_imports, insert_import
            candidates = missing_imports(self.root, doc.editor.toPlainText())
            if not candidates:
                self.message('Önerilebilecek eksik import bulunamadı.')
                return
            labels = [statement + '    (' + name + ')' for name, statement in candidates]
            label, ok = QInputDialog.getItem(
                self, 'Eksik import ekle', 'Eklenecek import:', labels, 0, False)
            if ok:
                text = insert_import(doc.editor.toPlainText(), candidates[labels.index(label)][1])
                if self.review_change('Import ekle', ''.join(difflib.unified_diff(
                        doc.editor.toPlainText().splitlines(True), text.splitlines(True)))):
                    self.replace_document_text(doc, text)
        except (OSError, SyntaxError, ValueError) as error:
            self.message(str(error))

    def code_actions(self):
        doc = self.current
        if not doc or not self.lsp.initialized or doc.language != 'python':
            return
        self.sync_document(doc)
        cursor = doc.editor.textCursor()
        start = QTextCursor(doc.editor.document())
        start.setPosition(cursor.selectionStart())
        end = QTextCursor(doc.editor.document())
        end.setPosition(cursor.selectionEnd())
        version = doc.version

        def received(actions):
            if doc not in self.documents or doc.version != version:
                self.message('Belge değişti; düzeltmeleri yeniden isteyin.')
                return
            actions = [action for action in actions or [] if not action.get('disabled')]
            if not actions:
                self.message('Dil sunucusu bu konum için hızlı düzeltme sunmadı.')
                return
            labels = [action.get('title', 'Düzeltme') for action in actions]
            title, ok = QInputDialog.getItem(
                self, 'Hızlı düzeltmeler', 'Uygulanacak düzeltme:', labels, 0, False)
            if not ok:
                return
            action = actions[labels.index(title)]
            if action.get('edit') and not self.apply_workspace_edit(action['edit']):
                return
            command = action.get('command')
            if isinstance(command, str):
                command = action
            if command:
                self.lsp.request(
                    'workspace/executeCommand', {
                        'command': command['command'], 'arguments': command.get(
                            'arguments', [])}, lambda result: self.apply_workspace_edit(result) if result and (
                        'changes' in result or 'documentChanges' in result) else None)
        self.lsp.request('textDocument/codeAction', {'textDocument': {'uri': doc.uri},
                                                     'range': {'start': {'line': start.blockNumber(), 'character': start.positionInBlock()}, 'end': {'line': end.blockNumber(), 'character': end.positionInBlock()}},
                                                     'context': {'diagnostics': [diagnostic for diagnostic in doc.diagnostics if start.blockNumber() <= diagnostic['range']['start']['line'] <= end.blockNumber()]}}, received)
