"""Main-window projects actions."""
import shlex
import uuid
from pathlib import Path
from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QLabel, QFileDialog, QDialog, QDialogButtonBox, QFormLayout, QMessageBox
from atelier.projects.environments import PYTHON_MISSING, select_project_python, valid_python_path


class ProjectsFeatures:
    def read_project_trust(self, root):
        decision = self.settings.value(self.project_profiles.key(root) + 'trust', '', type=str)
        return {'trusted': True, 'restricted': False}.get(decision)

    def require_project_trust(self):
        if self.project_trusted:
            return True
        self.message('Bu işlem için durum çubuğundaki Proje güveni düğmesinden projeye güven verin.')
        return False

    def show_project_trust(self):
        decision = QMessageBox(self)
        decision.setWindowTitle('Proje güveni')
        decision.setTextFormat(Qt.TextFormat.PlainText)
        decision.setText(str(self.root))
        explanation = 'Güven verirseniz Atelier bu projede Python, Git ve terminal süreçlerini çalıştırabilir.'
        if self.project_trusted:
            explanation += '\n\nKısıtlı moda geçerseniz bu projenin açık terminal oturumları kapanır.'
        decision.setInformativeText(explanation)
        trust = decision.addButton('Güven ver', QMessageBox.ButtonRole.AcceptRole)
        restrict = decision.addButton('Kısıtlı aç', QMessageBox.ButtonRole.DestructiveRole)
        cancel = decision.addButton(QMessageBox.StandardButton.Cancel)
        decision.setDefaultButton(cancel if self.project_trusted else restrict)
        decision.exec()
        if decision.clickedButton() == trust:
            self.set_project_trust(True)
        elif decision.clickedButton() == restrict:
            self.set_project_trust(False)

    def update_trust_ui(self):
        self.trust_button.setText('Güvenilir' if self.project_trusted else 'Kısıtlı')
        self.trust_button.setToolTip('Proje güveni')
        self.terminal_tabs.show_project()

    def stop_project_processes(self):
        self.git_generation += 1
        self.runner.kill()
        self.runner.waitForFinished(1000)
        self.debugger.shutdown()
        self.test_panel.shutdown()
        for process in list(self.processes):
            process.kill()
            process.waitForFinished(500)

    def set_project_trust(self, trusted):
        self.settings.setValue(self.project_profiles.key(self.root) + 'trust',
                               'trusted' if trusted else 'restricted')
        self.settings.sync()
        if trusted == self.project_trusted:
            return
        self.project_trusted = trusted
        if not trusted:
            self.stop_project_processes()
            self.terminal_tabs.discard_project(self.root)
            for doc in self.documents:
                self.cancel_save(doc)
        self.resolve_python_environment()
        self.update_trust_ui()
        self.start_lsp()
        self.refresh_git()

    def show_recent_projects(self):
        from atelier.ui.recent_projects import RecentProjectsDialog

        dialog = RecentProjectsDialog(self)
        dialog.exec()
        selected = dialog.selected_path
        dialog.deleteLater()
        if selected:
            self.open_recent_project(selected)

    def open_recent_project(self, path):
        self.set_project(Path(path))

    def choose_project(self):
        folder = QFileDialog.getExistingDirectory(self, 'Proje klasörü', str(self.root))
        if folder:
            self.set_project(Path(folder))

    def set_project(self, root, restart=True):
        root = Path(root).resolve()
        if not root.is_dir():
            self.message('Proje klasörü bulunamadı: ' + str(root))
            return
        switching = self.project_loaded and root != self.root
        if switching:
            if not self.checkpoint(force=True):
                self.message('Oturum kaydedilemedi. Proje geçişi iptal edildi.')
                return
            self.project_trusted = False
            self.stop_project_processes()
            self.closed_tabs.clear()
            for doc in list(self.documents):
                self.remove_document(doc)
            self.navigation_history.clear()
            self.navigation_index = -1
            self.watch_expressions = []
        self.cancel_search(clear=True)
        for doc in self.documents:
            self.cancel_save(doc)
        if self.project_loaded:
            self.project_profiles.save(self.root, self.python_preference, self.run_args, self.test_args)
        self.root = root
        self.notes_panel.set_project(root)
        trust = self.read_project_trust(root)
        self.project_trusted = trust is True
        if switching or not self.project_loaded:
            self.session_store.select(root)
            snapshot = self.session_store.load()
            self.closed_breakpoints = {
                path: {int(line): condition for line, condition in points.items()}
                for path, points in snapshot.get('closed_breakpoints', {}).items()
            }
            if not self.restore_enabled and not switching:
                for record in snapshot.get('documents', []):
                    if record.get('path') and record.get('breakpoints'):
                        self.closed_breakpoints[record['path']] = {
                            line: record.get('conditions', {}).get(str(line), '')
                            for line in record['breakpoints']
                        }
        profile = self.project_profiles.load(self.root, '')
        self.python_preference = self.settings.value(
            self.project_profiles.key(self.root) + 'interpreter', '', type=str)
        self.resolve_python_environment()
        self.run_args, self.test_args = profile['run_args'], profile['test_args']
        for name, value in self.project_profiles.load_save_actions(self.root).items():
            setattr(self, name, value)
        self.actions['format_save'].setChecked(self.format_on_save)
        self.project_loaded = True
        self.fs.setRootPath(str(self.root))
        self.tree.setRootIndex(self.fs.index(str(self.root)))
        self.project_label.setText(self.root.name or str(self.root))
        self.project_label.setToolTip(str(self.root))
        self.settings.setValue('project', str(self.root))
        self.recent_projects.touch(root)
        self.update_trust_ui()
        self.profile_selector.refresh()
        if restart:
            for doc in self.documents:
                if not doc.path:
                    doc.uri = (self.root / f'__untitled_{uuid.uuid4().hex}.py').as_uri()
            self.start_lsp()
        if switching:
            self.restoring = True
            try:
                self.restore_session(startup=False)
                if not self.documents:
                    self.new()
                self.refresh_watches()
                if hasattr(self, 'breakpoint_panel'):
                    self.breakpoint_panel.refresh()
            finally:
                self.restoring = False
        self.refresh_git()
        if trust is None:
            QTimer.singleShot(0, self, lambda: self.prompt_project_trust(root))

    def prompt_project_trust(self, root):
        if not self.closing and root == self.root and self.read_project_trust(root) is None:
            self.show_project_trust()

    def choose_python(self):
        self.manage_python()

    def resolve_python_environment(self):
        self.interpreter = select_project_python(
            self.root, self.python_preference, self.settings.value('interpreter', '')) if self.project_trusted else ''

    def rescan_python(self):
        previous = self.interpreter
        self.resolve_python_environment()
        if self.interpreter != previous:
            self.start_lsp()

    def show_python_status(self):
        from atelier.ui.python_status import PythonStatusDialog
        dialog = PythonStatusDialog(self)
        dialog.exec()
        dialog.deleteLater()

    def manage_python(self, prepare=False):
        if not self.require_project_trust():
            return
        from atelier.projects.environments import PythonEnvironmentDialog
        dialog = PythonEnvironmentDialog(self, prepare=prepare)
        dialog.exec()
        dialog.deleteLater()

    def activate_project_python(self, python):
        if not self.require_project_trust():
            return
        self.interpreter = self.python_preference = python
        self.project_profiles.save(self.root, python, self.run_args, self.test_args)
        self.start_lsp()
        if self.refresh_idle_terminal:
            self.terminal_tabs.refresh_idle_environment()

    def project_task_picker(self):
        from atelier.projects.tasks import ProjectTasksDialog
        try:
            dialog = ProjectTasksDialog(self)
        except (OSError, ValueError) as error:
            self.message(str(error))
            return
        dialog.exec()
        key = dialog.selected_task
        dialog.deleteLater()
        if key is not None:
            self.run_project_task(key)

    def run_project_task(self, key):
        if not self.require_project_trust():
            return
        if self.runner.state() != QProcess.ProcessState.NotRunning or self.debugger.active:
            self.message('Önce çalışan programı durdurun.')
            return
        if not valid_python_path(self.interpreter):
            self.message(PYTHON_MISSING)
            return
        if not self.save_modified_for_run():
            return
        from atelier.projects.config import load_project_config
        try:
            task = load_project_config(self.root)['tasks'].get(key)
            if task is None:
                raise ValueError(f'Proje komutu bulunamadı: {key}')
            cwd = (self.root / task['cwd']).resolve()
            if not cwd.is_relative_to(self.root) or not cwd.is_dir():
                raise ValueError(f'Proje komutunun çalışma klasörü bulunamadı: {cwd}')
        except (ValueError, OSError) as error:
            self.message(str(error))
            return
        self.append_output(f'\n▶ {task["label"]}\n', activate=True)
        self.launch_python(self.interpreter, ['-u', *task['args']], cwd, task['env'])

    def open_project_config(self):
        from atelier.projects.config import EXAMPLE, FILENAME
        path = self.root / FILENAME
        try:
            with path.open('x', encoding='utf-8') as handle:
                handle.write(EXAMPLE)
        except FileExistsError:
            pass
        except OSError as error:
            self.message(str(error))
            return
        self.open_path(path)

    def run_profiles_dialog(self):
        from atelier.projects.run_profiles import RunProfilesDialog
        try:
            dialog = RunProfilesDialog(self)
        except ValueError as error:
            self.message(str(error))
            return
        dialog.exec()
        dialog.deleteLater()
        self.profile_selector.refresh()

    def project_preferences(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Proje ayarları · ' + self.root.name)
        dialog.resize(700, 240)
        layout = QFormLayout(dialog)
        python = QLineEdit(self.interpreter)
        row = QHBoxLayout()
        row.addWidget(python)

        def browse():
            path, _ = QFileDialog.getOpenFileName(
                dialog, 'Python yorumlayıcısı', str(
                    Path(
                        python.text()).parent))
            if path:
                python.setText(path)
        self.button(row, 'Seç…', browse)
        run_args = QLineEdit(self.run_args)
        test_args = QLineEdit(self.test_args)
        test_args.setPlaceholderText('Ör. -k smoke --maxfail=1')
        layout.addRow('Proje', QLabel(str(self.root)))
        layout.addRow('Python', row)
        layout.addRow('Çalıştırma argümanları', run_args)
        layout.addRow('pytest argümanları', test_args)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec():
            if python.text().strip() and not valid_python_path(python.text().strip()):
                self.message('Python yorumlayıcısı bulunamadı.')
                return
            try:
                shlex.split(run_args.text())
                shlex.split(test_args.text())
            except ValueError as error:
                self.message(str(error))
                return
            if python.text().strip() != self.interpreter:
                self.python_preference = valid_python_path(python.text().strip())
            self.resolve_python_environment()
            self.run_args, self.test_args = run_args.text(), test_args.text()
            self.project_profiles.save(self.root, self.python_preference, self.run_args, self.test_args)
            self.start_lsp()
