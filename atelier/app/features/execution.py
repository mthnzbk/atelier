"""Main-window execution actions."""
from pathlib import Path
from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTreeWidgetItem, QInputDialog


class ExecutionFeatures:
    def choose_args(self):
        text, ok = QInputDialog.getText(
            self, 'Program argümanları', 'Argümanlar (boşluklu değerleri çift tırnakla yazın):', text=self.run_args)
        if ok:
            self.run_args = text
            self.project_profiles.save(self.root, self.python_preference, self.run_args, self.test_args)

    def run_file(self):
        if not self.current or self.runner.state() != QProcess.ProcessState.NotRunning or self.debugger.active:
            self.message('Önce çalışan programı durdurun.')
            return
        if not self.prepare_run_documents():
            return
        from atelier.projects.run_profiles import resolve_profile
        try:
            path, python, cwd, args, environment = resolve_profile(self)
        except ValueError as error:
            self.message(str(error))
            return
        self.append_output(f'\n▶ {path.name}\n', activate=True)
        self.launch_python(python, ['-u', str(path), *args], cwd, environment)

    def launch_python(self, python, args, cwd, environment):
        self.output_root = cwd
        self.runner.setWorkingDirectory(str(cwd))
        from atelier.projects.environments import clean_environment
        env = clean_environment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        env.insert('PYTHONUNBUFFERED', '1')
        for key, value in environment.items():
            env.insert(key, value)
        self.runner.setProcessEnvironment(env)
        self.runner.start(python, args)

    def append_output(self, text, activate=False):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()
        if activate:
            self.bottom.show()
            self.bottom.setCurrentIndex(1)

    def send_stdin(self):
        if self.runner.state() != QProcess.ProcessState.NotRunning:
            value = self.stdin.text()
            self.runner.write((value + '\n').encode('utf-8'))
            self.append_output(value + '\n')
            self.stdin.clear()
        elif self.debugger.active:
            self.message(
                'Debugger giriş istemlerini desteklemez; input() kullanan programı F5 ile çalıştırın.')

    def stop_execution(self):
        if self.runner.state() != QProcess.ProcessState.NotRunning:
            self.runner.kill()
        self.debugger.stop()

    def show_terminal(self):
        self.bottom.show()
        self.bottom.setCurrentWidget(self.terminal_tabs)
        if self.project_trusted:
            session = self.terminal or self.terminal_tabs.new_session()
            session.start()
            session.view.setFocus()

    def new_terminal(self):
        if self.require_project_trust():
            self.bottom.show()
            self.bottom.setCurrentWidget(self.terminal_tabs)
            self.terminal_tabs.new_session()

    def prepare_run_documents(self):
        if not self.require_project_trust():
            return False
        from atelier.projects.run_profiles import load_profiles, profile_python
        try:
            profiles, active = load_profiles(self)
        except ValueError as error:
            self.message(str(error))
            return False
        from atelier.projects.environments import PYTHON_MISSING, valid_python_path
        if not valid_python_path(profile_python(self, profiles.get(active, {}))):
            self.message(PYTHON_MISSING)
            return False
        if profiles.get(active, {}).get('file'):
            return self.save_modified_for_run()
        for doc in self.documents:
            self.cancel_save(doc)
        return self.save_all(allow_format=False)

    def save_modified_for_run(self):
        for doc in self.documents:
            self.cancel_save(doc)
            if doc.editor.document().isModified() and not self.save(doc=doc, allow_format=False):
                return False
        return True

    def apply_coverage(self, rows):
        self.coverage_data = {str(Path(row['path']).resolve()): {
            **{line: True for line in row['executed']}, **{line: False for line in row['missing']}} for row in rows}
        for doc in self.documents:
            for editor in doc.editors:
                editor.coverage_lines = dict(self.coverage_data.get(str(doc.path), {}))
            doc.paint_diagnostics()
        self.test_panel.coverage_tree.clear()
        self.test_panel.coverage_tree.setVisible(bool(rows))
        for row in rows:
            count = len(row['executed']) + len(row['missing'])
            item = QTreeWidgetItem(self.test_panel.coverage_tree,
                                   [Path(row['path']).name,
                                    f'{100 * len(row["executed"]) / count:.0f}%' if count else '—',
                                       str(len(row['missing']))])
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                (row['path'],
                 row['missing'][0] -
                    1 if row['missing'] else 0))

    def toggle_coverage(self):
        if any(editor.coverage_lines for doc in self.documents for editor in doc.editors):
            for doc in self.documents:
                for editor in doc.editors:
                    editor.coverage_lines = {}
                doc.paint_diagnostics()
        else:
            rows = [{'path': path,
                     'executed': [line for line,
                                  value in lines.items() if value],
                     'missing': [line for line,
                                 value in lines.items() if not value]} for path,
                    lines in self.coverage_data.items()]
            self.apply_coverage(rows)
