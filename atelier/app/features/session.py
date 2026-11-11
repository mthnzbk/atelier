"""Main-window session actions."""
import os
import uuid
import base64
from atelier.runtime.paths import application_root
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox
from atelier.version import APP_VERSION
from atelier.editor.document import Document


class SessionFeatures:
    def install_update(self):
        source = application_root()
        installation = source.parent
        if os.name != 'nt' or not (
                installation / 'runtime/python.exe').exists() or source.name != 'app':
            self.message(
                'Otomatik paket güncellemesi Python dahil Windows kurulumunda kullanılabilir. Kaynak sürümü yeni kaynak ZIP dosyasıyla güncelleyin.')
            return
        if self.update_worker and self.update_worker.isRunning():
            self.message('Bir güncelleme paketi zaten hazırlanıyor.')
            return
        archive, _ = QFileDialog.getOpenFileName(
            self, 'Atelier Windows güncelleme paketi', '', 'ZIP (*.zip)')
        if not archive:
            return
        from atelier.runtime.updates import UpdateWorker
        stage = self.session_store.path.parent / 'updates' / uuid.uuid4().hex
        worker = UpdateWorker(archive, stage, self)
        self.update_worker = worker
        worker.progress.connect(
            lambda value: self.statusBar().showMessage(
                f'Güncelleme paketi doğrulanıyor · %{value}'))
        worker.failed.connect(self.message)

        def ready(manifest, payload):
            answer = QMessageBox.question(self, 'Güncelleme hazır',
                                          f"Mevcut sürüm: {APP_VERSION}\nPaket sürümü: {
                                              manifest.get(
                                                  'version',
                                                  '?')}\n\n"
                                          'Paket dosyaları doğrulandı. Editör kapatılıp güncellensin mi? Ayarlar ve kurtarma kayıtları korunur; eski uygulama klasörü yedeklenir.',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Yes:
                self.pending_update = (payload, installation)
                if not self.close():
                    self.pending_update = None
        worker.ready.connect(ready)
        worker.start()

    def save_layout(self):
        self.settings.setValue('window/geometry', self.saveGeometry())
        self.settings.setValue('window/state', self.saveState())
        self.settings.setValue('window/maximized', self.isMaximized())
        self.settings.setValue('layout/main', self.main_split.saveState())
        self.settings.setValue('layout/right', self.right_split.saveState())
        self.settings.setValue('layout/sidebar_visible', not self.sidebar.isHidden())
        self.settings.setValue('layout/bottom_visible', not self.bottom.isHidden())
        self.settings.setValue('layout/sidebar_tab', self.sidebar.currentIndex())
        self.settings.setValue('layout/bottom_tab', self.bottom.currentIndex())
        self.settings.setValue('run_args', self.run_args)
        self.project_profiles.save(self.root, self.python_preference, self.run_args, self.test_args)
        self.settings.sync()

    def restore_layout(self):
        geometry = self.settings.value('window/geometry')
        if geometry:
            self.restoreGeometry(geometry)
        if self.settings.value('window/state'):
            self.restoreState(self.settings.value('window/state'))
        for key, splitter in [('layout/main', self.main_split), ('layout/right', self.right_split)]:
            state = self.settings.value(key)
            if state:
                splitter.restoreState(state)
        self.sidebar.setVisible(self.settings.value('layout/sidebar_visible', True, type=bool))
        self.bottom.setVisible(self.settings.value('layout/bottom_visible', True, type=bool))
        self.sidebar.setCurrentIndex(int(self.settings.value('layout/sidebar_tab', 0)))
        self.bottom.setCurrentIndex(int(self.settings.value('layout/bottom_tab', 0)))
        if self.settings.value('window/maximized', False, type=bool):
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def checkpoint(self, clean=False, force=False):
        if self.restoring or (not clean and not force and not self.autorecovery_enabled):
            return
        records = []
        for index in range(self.tabs.count()):
            doc = self.tabs.widget(index)
            dirty = doc.editor.document().isModified()
            if clean and dirty and doc.path is None:
                continue
            record = {'path': str(doc.path) if doc.path else None,
                      'active': doc is self.current,
                      'cursor': doc.editor.textCursor().position(),
                      'scroll': doc.editor.verticalScrollBar().value(),
                      'views': [{'cursor': view.textCursor().position(), 'scroll': view.verticalScrollBar().value(),
                                 'horizontal': view.horizontalScrollBar().value()} for view in doc.editors],
                      'active_view': doc.editors.index(doc.editor),
                      'breakpoints': sorted(doc.breakpoints), 'conditions': doc.breakpoint_conditions,
                      'split': len(doc.editors) == 2, 'folds': sorted(doc.editor.structure.folded),
                      'editor_split': base64.b64encode(bytes(doc.splitter.saveState())).decode('ascii'),
                      'content_split': base64.b64encode(bytes(doc.content_split.saveState())).decode('ascii'),
                      'markdown_mode': doc.markdown_mode.currentIndex()}
            record['encoding'] = doc.text_format.encoding
            if (not clean and dirty) or (doc.path is None and not (clean and dirty)):
                record.update(text=doc.editor.toPlainText(), dirty=dirty)
                if not doc.text_format.mixed:
                    record['newline'] = doc.text_format.newline
                tracked = self.file_monitor.entries.get(doc)
                if tracked and tracked[1] and not doc.external_pending:
                    record['disk_digest'] = tracked[1].hex()
            records.append(record)
        try:
            self.session_store.save({'root': str(self.root), 'documents': records,
                                     'current': self.tabs.currentIndex(), 'watches': self.watch_expressions, 'clean': clean,
                                     'closed_breakpoints': self.closed_breakpoints})
            self.save_layout()
            return True
        except OSError as error:
            self.statusBar().showMessage('Kurtarma kaydı yazılamadı: ' + str(error), 5000)
            return False

    def restore_session(self, startup=True):
        from dataclasses import replace
        from atelier.storage.text_format import NEWLINES, TextFormat

        if startup and not self.restore_enabled:
            return
        snapshot = self.session_store.load()
        if not snapshot:
            return
        active = None
        for record in snapshot.get('documents', []):
            path = Path(record['path']) if record.get('path') else None
            if path and path.exists():
                doc = self.open_path(path, encoding=record.get('encoding'))
            elif 'text' in record:
                doc = self.add_document(Document(self, path, record['text'],
                                                 TextFormat(record.get('encoding') or 'utf-8')))
            else:
                continue
            if doc is None:
                continue
            if 'text' in record:
                if record.get('newline') in NEWLINES.values():
                    doc.text_format = replace(doc.text_format, newline=record['newline'], mixed=())
                doc.editor.setPlainText(record['text'])
                doc.editor.document().setModified(record.get('dirty', True))
                tracked = self.file_monitor.entries.get(doc)
                if path and not (
                        tracked and tracked[1] and tracked[1].hex() == record.get('disk_digest')):
                    doc.external_pending = True
                    doc.external_label.setText(
                        'Kurtarılan yerel içerik. Kaydetmeden önce diskteki sürümle karşılaştırabilirsiniz.')
                    doc.external_bar.show()
            self.restore_breakpoints(doc, {
                line: record.get('conditions', {}).get(str(line), '') for line in record.get('breakpoints', [])
            })
            if record.get('split'):
                self.tabs.setCurrentWidget(doc)
                self.toggle_split()
            cursor = doc.editor.textCursor()
            cursor.setPosition(min(record.get('cursor', 0),
                               doc.editor.document().characterCount() - 1))
            doc.editor.setTextCursor(cursor)
            doc.editor.structure.rebuild()
            for line in record.get('folds', []):
                doc.editor.structure.toggle(line)
            doc.editor.verticalScrollBar().setValue(record.get('scroll', 0))
            doc.markdown_mode.setCurrentIndex(record.get('markdown_mode', 1))
            for key, splitter in [('editor_split', doc.splitter),
                                  ('content_split', doc.content_split)]:
                if record.get(key):
                    from PySide6.QtCore import QByteArray
                    try:
                        splitter.restoreState(QByteArray(base64.b64decode(record[key])))
                    except (ValueError, TypeError):
                        pass
            for view, state in zip(doc.editors, record.get('views', [])):
                cursor = view.textCursor()
                cursor.setPosition(min(state['cursor'], view.document().characterCount() - 1))
                view.setTextCursor(cursor)
                view.verticalScrollBar().setValue(state['scroll'])
                view.horizontalScrollBar().setValue(state['horizontal'])
            doc.active_editor = doc.editors[min(record.get('active_view', 0), len(doc.editors) - 1)]
            if record.get('active'):
                active = doc
        if self.documents:
            if active:
                self.tabs.setCurrentWidget(active)
            else:
                self.tabs.setCurrentIndex(min(snapshot.get('current', 0), self.tabs.count() - 1))
            self.current.editor.setFocus()
        self.watch_expressions = snapshot.get('watches', [])
        self.refresh_watches()
        if startup and not snapshot.get('clean', True):
            self.statusBar().showMessage('Önceki oturum ve kurtarma içeriği geri yüklendi.', 10000)
