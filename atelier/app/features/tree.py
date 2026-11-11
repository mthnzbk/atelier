"""Main-window tree actions."""
from pathlib import Path
from PySide6.QtWidgets import QApplication, QVBoxLayout, QPlainTextEdit, QLineEdit, QMessageBox, QInputDialog, QDialog, QDialogButtonBox, QFormLayout, QMenu
from atelier.ui.icons import icon


class TreeFeatures:
    def selected_tree_paths(self):
        paths = sorted({Path(self.fs.filePath(index)).absolute(
        ) for index in self.tree.selectionModel().selectedRows(0)}, key=lambda path: len(path.parts))
        selected = []
        for path in paths:
            if not any(parent in path.parents for parent in selected):
                selected.append(path)
        return selected

    def tree_menu(self, position):
        index = self.tree.indexAt(position)
        if index.isValid() and not self.tree.selectionModel().isSelected(index):
            self.tree.setCurrentIndex(index)
        paths = self.selected_tree_paths() if index.isValid() else [self.root]
        if not paths:
            paths = [self.root]
        menu = QMenu(self)

        def add(label, key, callback):
            action = menu.addAction(icon(key), label)
            action.triggered.connect(lambda checked=False: callback())
        menu.addSection(f'{len(paths)} öğe seçili')
        if len(paths) == 1:
            add('Yeni dosya…', 'new', lambda: self.tree_create(paths[0], False))
            add('Yeni klasör…', 'folder_new', lambda: self.tree_create(paths[0], True))
        add('Seçili dosyaları aç', 'open', lambda: [
            self.open_path(path) for path in paths if path.is_file()])
        if self.root not in paths:
            menu.addSeparator()
            if len(paths) == 1 and self.fs.git_states.get(str(paths[0].resolve()), '') in {
                    'DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU'}:
                add('Git çakışmasını çöz…', 'merge_conflicts',
                    lambda: self.resolve_conflicts(paths[0]))
            add('Yeniden adlandır…' if len(paths) == 1 else 'Toplu yeniden adlandır…', 'rename',
                lambda: self.tree_rename(paths[0]) if len(paths) == 1 else self.tree_batch_rename(paths))
            if all(not path.is_symlink() and (path.suffix == '.py' or path.is_dir())
                   for path in paths):
                add('Refactor ile tek tek yeniden adlandır…',
                    'rename', lambda: self.refactor_tree_paths(paths))
            add('Geri dönüşüm kutusuna gönder…', 'trash', lambda: self.tree_delete(
                paths[0]) if len(paths) == 1 else self.tree_delete_many(paths))
        menu.addSeparator()
        add('Git: seçilenleri hazırla', 'git', lambda: self.stage_tree_paths(paths))
        add('Yolları kopyala', 'open', lambda: QApplication.clipboard().setText(
            '\n'.join(str(path) for path in paths)))
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def refactor_tree_paths(self, paths):
        for path in paths:
            if not self.tree_rename(path, refactor=True):
                break

    def stage_tree_paths(self, paths):
        try:
            paths = [self.checked_tree_path(path) for path in paths]
        except ValueError as error:
            self.message(str(error))
            return
        for doc in self.documents:
            if doc.path and any(
                    doc.path == path or path in doc.path.parents for path in paths) and doc.editor.document().isModified():
                if not self.save(doc=doc, allow_format=False):
                    return
        self.git_operation(['add', '--', *[str(path) for path in paths]],
                           'Seçilen yollar Git için hazırlandı.')

    def tree_delete_many(self, paths):
        try:
            paths = [self.checked_tree_path(path) for path in paths]
            if self.root in paths:
                raise ValueError('Proje kökü silinemez.')
            docs = [doc for doc in self.documents if doc.path and any(
                doc.path == path or path in doc.path.parents for path in paths)]
            for doc in docs:
                if not self.confirm_saved(doc):
                    return
            if QMessageBox.question(self, 'Seçilenleri geri dönüşüm kutusuna gönder', str(len(paths)) + ' yol ve içerikleri gönderilsin mi?\n' + '\n'.join(str(path)
                                    for path in paths[:20]), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
                return
            from send2trash import send2trash
            send2trash([str(path) for path in paths])
            for doc in docs:
                if not doc.path.exists():
                    doc.editor.document().setModified(False)
                    self.close_tab(self.tabs.indexOf(doc))
            self.refresh_git()
            return True
        except (OSError, ValueError) as error:
            self.message(str(error))

    def tree_batch_rename(self, paths):
        dialog = QDialog(self)
        dialog.setWindowTitle('Toplu yeniden adlandır (importları değiştirmez)')
        form = QFormLayout(dialog)
        find = QLineEdit()
        replace = QLineEdit()
        prefix = QLineEdit()
        suffix = QLineEdit()
        for label, widget in [('Bul', find), ('Değiştir', replace),
                              ('Önek', prefix), ('Sonek (uzantıdan önce)', suffix)]:
            form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if not dialog.exec():
            return
        moved = []
        try:
            plan = []
            for path in paths:
                path = self.checked_tree_path(path)
                if path == self.root:
                    raise ValueError('Proje kökü yeniden adlandırılamaz.')
                stem = path.stem if path.is_file() else path.name
                name = prefix.text() + (stem.replace(find.text(), replace.text()) if find.text() else stem) + \
                    suffix.text() + (path.suffix if path.is_file() else '')
                if not name or any(char in name for char in '/\\'):
                    raise ValueError('Geçersiz yeni ad.')
                target = self.checked_tree_path(path.with_name(name))
                if target == path:
                    continue
                if target.exists() or any(new == target for _, new in plan):
                    raise ValueError('Hedef isim çakışması: ' + name)
                plan.append((path, target))
            if not plan or not self.review_change('Toplu yeniden adlandırma', '\n'.join(
                    str(old) + ' → ' + new.name for old, new in plan)):
                return
            for old, new in plan:
                old.rename(new)
                moved.append((old, new))
            for old, new in plan:
                self.relocate_documents(old, new)
            self.refresh_git()
        except (OSError, ValueError) as error:
            for old, new in reversed(moved):
                try:
                    new.rename(old)
                except OSError:
                    pass
            self.message(str(error))

    def checked_tree_path(self, path):
        path = Path(path).absolute()
        parent = path.parent.resolve()
        if path != self.root and parent != self.root and self.root not in parent.parents:
            raise ValueError('İşlem proje klasörü içinde olmalıdır.')
        if '.git' in path.relative_to(self.root).parts or (parent.is_relative_to(
                self.root) and '.git' in parent.relative_to(self.root).parts):
            raise ValueError('.git içeriği bu menüden değiştirilemez.')
        return path

    def tree_create(self, selected, folder=False, name=None):
        parent = selected if selected.is_dir() else selected.parent
        if name is None:
            name, ok = QInputDialog.getText(self, 'Yeni klasör' if folder else 'Yeni dosya', 'Ad:')
            if not ok:
                return
        try:
            if not name or name in ('.', '..') or any(c in name for c in '/\\'):
                raise ValueError('Tek bir dosya/klasör adı girin.')
            target = self.checked_tree_path(parent / name)
            if folder:
                target.mkdir()
            else:
                with target.open('x', encoding='utf-8'):
                    pass
                self.open_path(target)
            self.refresh_git()
            return target
        except (OSError, ValueError) as error:
            self.message(str(error))

    def stage_tree_path(self, path):
        try:
            path = self.checked_tree_path(path)
        except ValueError as error:
            self.message(str(error))
            return
        for doc in self.documents:
            if doc.path and (
                    doc.path == path or path in doc.path.parents) and doc.editor.document().isModified():
                if not self.save(doc=doc, allow_format=False):
                    return
        self.git_operation(['add', '--', str(path)], 'Seçili yol Git için hazırlandı.')

    def relocate_documents(self, old, new):
        for doc in self.documents:
            if not doc.path:
                continue
            if doc.path == old or old in doc.path.parents:
                relative = doc.path.relative_to(old) if doc.path != old else Path('.')
                target = (new / relative).resolve() if relative != Path('.') else new
                if self.lsp.initialized and doc.synced is not None:
                    self.lsp.notify('textDocument/didClose', {'textDocument': {'uri': doc.uri}})
                self.file_monitor.untrack(doc)
                doc.path, doc.uri, doc.synced = target, target.as_uri(), None
                doc.update_breadcrumb()
                doc.update_language()
                self.open_document(doc)
                self.file_monitor.track(doc)
        self.refresh_tabs()

    def tree_rename(self, path, refactor=False, name=None):
        if refactor and not self.require_project_trust():
            return False
        try:
            path = self.checked_tree_path(path)
            if path == self.root:
                raise ValueError('Proje kökü yeniden adlandırılamaz.')
            if name is None:
                name, ok = QInputDialog.getText(
                    self, 'Refactor ile yeniden adlandır' if refactor else 'Yeniden adlandır', 'Yeni ad:', text=path.name)
                if not ok:
                    return
            if not name or name in ('.', '..') or any(c in name for c in '/\\'):
                raise ValueError('Tek bir dosya/klasör adı girin.')
            target = self.checked_tree_path(path.with_name(name))
            if target.exists():
                raise ValueError('Bu isimde bir dosya/klasör zaten var.')
            if refactor:
                if path.is_symlink():
                    raise ValueError('Sembolik bağlantı yerine gerçek Python modülünü seçin.')
                for doc in self.documents:
                    if doc.editor.document().isModified() and not self.save(doc=doc, allow_format=False):
                        return
                import keyword
                if path.suffix == '.py' and (
                        target.suffix != '.py' or not target.stem.isidentifier() or keyword.iskeyword(target.stem)):
                    raise ValueError(
                        'Python modülü geçerli bir adla ve .py uzantısıyla yeniden adlandırılmalıdır.')
                if path.is_dir() and (not name.isidentifier() or keyword.iskeyword(name)):
                    raise ValueError(
                        'Python paketi geçerli bir Python adıyla yeniden adlandırılmalıdır.')
                from atelier.languages.refactoring import rename_changes
                project, changes = rename_changes(self.root, path, name)
                try:
                    if not self.review_change('Refactor değişiklikleri', changes.get_description()):
                        return
                    project.do(changes)
                finally:
                    project.close()
                self.relocate_documents(path, target)
                for doc in self.documents:
                    if doc.path and doc.path.exists():
                        self.reload_document(doc, confirm=False)
            else:
                path.rename(target)
                self.relocate_documents(path, target)
            self.refresh_git()
            return target
        except Exception as error:
            self.message(str(error))

    def tree_delete(self, path):
        try:
            path = self.checked_tree_path(path)
            if path == self.root:
                raise ValueError('Proje kökü silinemez.')
            docs = [d for d in self.documents if d.path and (
                d.path == path or path in d.path.parents)]
            for doc in docs:
                if not self.confirm_saved(doc):
                    return
            choice = QMessageBox.question(self, 'Geri dönüşüm kutusuna gönder',
                                          f'{path}\n\nBu yol ve klasörse içeriği geri dönüşüm kutusuna gönderilsin mi?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if choice != QMessageBox.StandardButton.Yes:
                return
            from send2trash import send2trash
            send2trash(str(path))
            for doc in docs:
                doc.editor.document().setModified(False)
                self.close_tab(self.tabs.indexOf(doc))
            self.refresh_git()
            return True
        except (OSError, ValueError) as error:
            self.message(str(error))

    def review_change(self, title, text):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(950, 650)
        layout = QVBoxLayout(dialog)
        preview = QPlainTextEdit(readOnly=True)
        preview.setPlainText(text)
        layout.addWidget(preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Değişiklikleri uygula')
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return bool(dialog.exec())
