"""Main-window git actions."""
import re
import shutil
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QProcess, QProcessEnvironment
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem, QMessageBox, QInputDialog, QDialog, QDialogButtonBox


class GitFeatures:
    def git_command(self, args, callback, input_text=None, passive=False):
        if not self.project_trusted:
            callback(1, 'Git işlemleri için projeye güven verin.')
            return
        if not self.git_enabled:
            callback(1, 'Git ayarlardan kapatıldı.')
            return
        executable = self.git_executable or shutil.which('git')
        if not executable:
            callback(1, 'Git bulunamadı. Git kurup uygulamayı yeniden açın.')
            return
        process = QProcess(self)
        root = self.root
        self.processes.append(process)
        if passive:
            self.git_reads.add(process)
        process.setWorkingDirectory(str(self.root))
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert('GIT_TERMINAL_PROMPT', '0')
        environment.insert('GCM_INTERACTIVE', 'Never')
        if passive:
            environment.insert('GIT_OPTIONAL_LOCKS', '0')
        process.setProcessEnvironment(environment)
        timeout = QTimer(process, interval=120000, singleShot=True)
        timeout.timeout.connect(process.kill)
        timeout.start()
        finalized = False

        def done(code, *_):
            nonlocal finalized
            if finalized:
                return
            finalized = True
            timeout.stop()
            output = bytes(process.readAllStandardOutput()).decode('utf-8', 'replace')
            error = bytes(process.readAllStandardError()).decode('utf-8', 'replace')
            if process in self.processes:
                self.processes.remove(process)
            self.git_reads.discard(process)
            try:
                if not self.closing and self.project_trusted and self.root == root:
                    callback(code, output if code == 0 else (error or process.errorString()))
            finally:
                process.deleteLater()
        process.finished.connect(done)
        process.errorOccurred.connect(lambda error: done(
            1) if error == QProcess.ProcessError.FailedToStart else None)
        if input_text is not None:
            def write_input():
                process.write(input_text.encode('utf-8'))
                process.closeWriteChannel()
            process.started.connect(write_input)
        process.start(executable, ['-c', 'core.quotepath=false', *args])

    def refresh_git(self):
        if self.closing:
            return
        self.git_refresh_timer.stop()
        self.git_generation += 1
        generation = self.git_generation
        for process in list(self.git_reads):
            process.kill()
        if not self.project_trusted:
            self.fs.set_git_states({})
            self.git_list.clear()
            self.git_list.addItem('Git işlemleri için projeye güven verin.')
            self.diff.clear()
            return
        root = self.root

        def status(code, text):
            if generation != self.git_generation:
                return
            previous = self.git_list.currentItem()
            selected = previous.data(Qt.ItemDataRole.UserRole) if previous else None
            self.git_list.clear()
            states = {}
            if code:
                self.fs.set_git_states({})
                self.git_list.addItem('Git deposu yok / Git kullanılamıyor')
                self.git_list.setToolTip(text)
                return
            chunks = text.split('\0')
            i = 0
            while i < len(chunks):
                entry = chunks[i]
                i += 1
                if len(entry) < 4:
                    continue
                state, path = entry[:2], entry[3:]
                states[str(root / path)] = state
                if 'R' in state or 'C' in state:
                    i += 1
                item = QListWidgetItem(f'{state}  {path}')
                item.setData(Qt.ItemDataRole.UserRole, str(root / path))
                self.git_list.addItem(item)
                if str(root / path) == selected:
                    self.git_list.setCurrentItem(item)
            if not self.git_list.count():
                self.git_list.addItem('✓ Çalışma ağacı temiz')
            self.fs.set_git_states(states)

        def repository(code, text):
            nonlocal root
            if generation != self.git_generation:
                return
            if code:
                status(code, text)
                return
            root = Path(text.strip())
            self.git_command(['status', '--porcelain=v1', '-z',
                             '--untracked-files=all', '--', '.'], status, passive=True)
        self.git_command(['rev-parse', '--show-toplevel'], repository, passive=True)
        doc = self.current
        if not doc or not doc.path or doc.large_file:
            return

        def diff(code, text):
            if generation != self.git_generation or doc not in self.documents:
                return
            lines = {}
            if code == 0:
                for match in re.finditer(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', text, re.M):
                    start, count = int(match[1]) - 1, int(match[2] or 1)
                    color = '#fbbf24' if count else '#fb7185'
                    for line in range(max(0, start), max(0, start) + max(1, count)):
                        lines[line] = color
            for editor in doc.editors:
                editor.git_lines = lines
                editor.gutter.update()
            self.diff.setPlainText(
                text if code == 0 else 'Bu dosya için Git farkı alınamadı.\n' + text)
        self.git_command(['diff', '--no-ext-diff', '--no-color', '--unified=0',
                         'HEAD', '--', str(doc.path)], diff, passive=True)

    def open_git_item(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.open_path(path)
            self.bottom.show()
            self.bottom.setCurrentIndex(3)
            self.refresh_git()

    def resolve_conflicts(self, path=None):
        root = self.root
        selected = Path(path or self.selected_git_path()).resolve(
        ) if path or self.selected_git_path() else None

        def receive(code, text):
            if self.root != root or self.closing:
                return
            if code:
                self.message('Çakışmalar listelenemedi: ' + text)
                return
            choices = list(dict.fromkeys(name for name in text.split('\0') if name))
            if not choices:
                self.statusBar().showMessage('Bu projede çözülmemiş Git çakışması yok.', 5000)
                return
            name = next((name for name in choices if (root / name).resolve() == selected), None)
            if name is None:
                if len(choices) == 1:
                    name = choices[0]
                else:
                    name, ok = QInputDialog.getItem(
                        self, 'Git çakışmaları', 'Çözülecek dosya:', choices, editable=False)
                    if not ok:
                        return
            target = root / name
            if target.is_symlink() or not target.is_file() or root not in target.resolve().parents:
                self.message('Bu çakışma bir metin dosyası olarak açılamıyor; Git üzerinden çözün.')
                return
            doc = self.open_path(target)
            if not doc:
                return
            if doc.large_file:
                self.message('Büyük dosya modunda çakışma işaretlerini editörde elle çözebilirsiniz.')
                return
            self.cancel_save(doc)
            from atelier.git.merge import MergeDialog
            try:
                dialog = MergeDialog(self, doc)
            except (OSError, ValueError) as error:
                self.message(str(error))
                return
            dialog.exec()
            dialog.deleteLater()
        self.git_command(['diff', '--name-only', '--diff-filter=U',
                         '-z', '--relative', '--', '.'], receive)

    def selected_git_path(self):
        item = self.git_list.currentItem()
        path = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not path and self.current:
            path = str(self.current.path) if self.current.path else None
        if not path:
            self.message('Git listesinden bir dosya seçin.')
        return path

    def git_operation(self, args, success='Git işlemi tamamlandı.', after=None):
        def completed(code, text):
            if code:
                self.message(text or 'Git işlemi başarısız.')
            else:
                self.statusBar().showMessage(success, 6000)
                self.refresh_git()
                self.file_monitor.check()
                if after:
                    after()
        self.git_command(args, completed)

    def git_stage(self):
        path = self.selected_git_path()
        if not path:
            return
        doc = next((d for d in self.documents if d.path == Path(path)), None)
        if doc and doc.editor.document().isModified():
            if not self.save(doc=doc, allow_format=False):
                return
        self.git_operation(['add', '--', path], 'Dosya commit için hazırlandı.')

    def git_unstage(self):
        path = self.selected_git_path()
        if path:
            def head(code, _):
                args = [
                    'restore',
                    '--staged',
                    '--',
                    path] if code == 0 else [
                    'rm',
                    '--cached',
                    '--',
                    path]
                self.git_operation(args, 'Dosya hazırlamadan çıkarıldı; çalışma dosyası korundu.')
            self.git_command(['rev-parse', '--verify', 'HEAD'], head)

    def git_commit(self):
        def staged(code, text):
            files = [f for f in text.split('\0') if f]
            if code or not files:
                self.message('Commit için hazırlanmış dosya yok. Önce Hazırla (+) kullanın.')
                return
            dialog = QDialog(self)
            dialog.setWindowTitle('Commit oluştur')
            dialog.resize(620, 420)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(f'{len(files)} hazırlanmış dosya commit edilecek:'))
            listing = QListWidget()
            listing.addItems(files)
            layout.addWidget(listing)
            message = QLineEdit(placeholderText='Commit mesajı')
            layout.addWidget(message)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                       QDialogButtonBox.StandardButton.Cancel)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Commit oluştur')
            buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            message.textChanged.connect(
                lambda text: buttons.button(
                    QDialogButtonBox.StandardButton.Ok).setEnabled(
                    bool(
                        text.strip())))
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if dialog.exec() and message.text().strip():
                self.git_operation(['commit', '-m', message.text().strip()], 'Commit oluşturuldu.')
        self.git_command(['diff', '--cached', '--name-only', '-z'], staged)

    def git_history(self):
        def receive(code, text):
            if code:
                self.message(text)
            else:
                self.show_text('Git geçmişi · son 100 commit', text)
        self.git_command(['log', '-100', '--graph', '--decorate',
                         '--oneline', '--date=short'], receive)

    def git_branches(self):
        def receive(code, text):
            if code:
                self.message(text)
                return
            branches = text.strip().splitlines()
            dialog = QDialog(self)
            dialog.setWindowTitle('Git dalları')
            layout = QVBoxLayout(dialog)
            listing = QListWidget()
            listing.addItems(branches)
            layout.addWidget(listing)
            name = QLineEdit(placeholderText='Yeni dal adı')
            layout.addWidget(name)
            row = QHBoxLayout()

            def switch(create=False):
                branch = name.text().strip() if create else listing.currentItem(
                ).text().lstrip('* ').strip() if listing.currentItem() else ''
                if not branch:
                    return
                if any(d.editor.document().isModified() for d in self.documents):
                    self.message('Dal değiştirmeden önce açık belgeleri kaydedin.')
                    return
                args = ['switch', '-c', branch] if create else ['switch', '--', branch]
                # git switch takes a branch name, not a pathspec separator.
                if not create:
                    args = ['switch', '--no-guess', branch]
                self.git_operation(args, 'Dal değiştirildi.', dialog.accept)
            self.button(row, 'Seçili dala geç', lambda: switch())
            self.button(row, 'Yeni dal oluştur', lambda: switch(True))
            layout.addLayout(row)
            dialog.exec()
        self.git_command(['branch', '--no-color'], receive)

    def git_remote(self, operation):
        if operation == 'pull' and any(d.editor.document().isModified() for d in self.documents):
            self.message('Pull işleminden önce açık belgeleri kaydedin.')
            return

        def upstream(code, text):
            if code:
                self.message(
                    'Bu dal için uzak takip dalı ayarlı değil. Önce terminalden upstream ayarlayın.')
                return
            target = text.strip()
            choice = QMessageBox.question(self, 'Uzak Git işlemi',
                                          f'{target} için {operation} çalıştırılsın mı?' +
                                          (' Yalnızca fast-forward kabul edilir.' if operation ==
                                           'pull' else ''),
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Yes:
                self.git_operation(['pull', '--ff-only'] if operation ==
                                   'pull' else ['push'], operation + ' tamamlandı.')
        self.git_command(['rev-parse',
                          '--abbrev-ref',
                          '--symbolic-full-name',
                          '@{upstream}'],
                         upstream)

    def git_init(self):
        target = self.root
        answer = QMessageBox.question(self, 'Git deposu başlat',
                                      f'{target}\n\nBu klasörde git init çalıştırılsın mı?',
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            def add_python_ignores():
                from atelier.git.ignore import seed_python_gitignore, with_python_ignores
                path = target / '.gitignore'
                doc = next((doc for doc in self.documents if doc.path == path), None)
                try:
                    external = doc is not None and self.file_monitor.has_conflict(doc, path)
                    updated = seed_python_gitignore(path)
                except OSError as error:
                    self.message(f'Git deposu hazır. .gitignore güncellenemedi: {error}')
                    return
                if doc:
                    if doc.editor.document().isModified():
                        local = doc.editor.toPlainText()
                        merged = with_python_ignores(local.encode('utf-8')).decode('utf-8')
                        if merged != local:
                            self.replace_document_text(doc, merged)
                        if not external:
                            self.file_monitor.track(doc)
                            doc.saved_text = updated.decode(
                                'utf-8',
                                errors='replace').replace(
                                '\r\n',
                                '\n')
                    else:
                        self.reload_document(doc, confirm=False)
                self.statusBar().showMessage('Git deposu ve Python .gitignore kuralları hazır.', 6000)
                self.refresh_git()
            self.git_operation(['init'], 'Git deposu hazır.', after=add_python_ignores)

    def git_compare(self):
        path = self.current.path if self.current else None
        if not path:
            self.message('Önce kaydedilmiş bir dosya açın.')
            return
        if self.current.editor.document().isModified() and not self.save(allow_format=False):
            return
        from atelier.git.compare import GitCompare
        GitCompare(self, path).exec()

    def stage_selected_lines(self):
        doc = self.current
        if not doc or not doc.path:
            self.message('Önce bir dosya açıp kaydedin.')
            return
        if doc.editor.document().isModified() and not self.save(doc=doc, allow_format=False):
            return
        first, last = doc.editor.selected_blocks()
        self.prepare_partial_stage(doc.path, first, last)

    def prepare_partial_stage(self, path, first, last, review=True, after=None):
        path = Path(path).resolve()

        def root_received(code, text):
            if code:
                self.message(text)
                return
            repository = Path(text.strip())
            relative = path.relative_to(repository).as_posix()

            def base_received(code, base):
                if code:
                    self.message(
                        'Satır bazında hazırlamak için dosya Git tarafından izleniyor olmalıdır. Yeni dosyayı önce Git ekle ile hazırlayın.')
                    return
                try:
                    with path.open(encoding='utf-8', newline='') as source:
                        working = source.read()
                    if '\r\n' not in base:
                        working = working.replace('\r\n', '\n')
                except (OSError, UnicodeError) as error:
                    self.message(str(error))
                    return
                from atelier.git.partial import selected_patch
                patch = selected_patch(base, working, relative, first, last)
                if not patch:
                    self.message('Seçili satırlarda hazırlanmamış değişiklik bulunamadı.')
                    return
                if review and not self.review_change('Seçili Git değişiklikleri · yalnızca index değişir',
                                                     'Eşit olmayan satır değiştirme/silme grupları bölünmeden hazırlanır.\n\n' + patch):
                    return

                def checked(code, text):
                    if code:
                        self.message(
                            'Index değişmiş olabilir; seçim tekrar hazırlanmalıdır.\n' + text)
                        return
                    self.git_command(['apply', '--cached', '--whitespace=nowarn',
                                     '-'], applied, input_text=patch)

                def applied(code, text):
                    if code:
                        self.message(text)
                    else:
                        self.refresh_git()
                        if after:
                            after()
                self.git_command(['apply', '--cached', '--check', '-'], checked, input_text=patch)
            self.git_command(['show', ':' + relative], base_received)
        self.git_command(['rev-parse', '--show-toplevel'], root_received)
