"""Main-window debugging actions."""
from pathlib import Path
from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QListWidgetItem, QInputDialog


class DebuggingFeatures:
    def toggle_current_breakpoint(self):
        if self.current:
            self.toggle_breakpoint(self.current, self.editor.textCursor().blockNumber() + 1)

    def toggle_breakpoint(self, doc, line):
        if not 1 <= line <= doc.editor.blockCount():
            return
        if line in doc.breakpoints:
            doc.breakpoints.remove(line)
            doc.breakpoint_cursors.pop(line, None)
            doc.breakpoint_conditions.pop(line, None)
        else:
            doc.breakpoints.add(line)
            anchor = QTextCursor(doc.editor.document().findBlockByNumber(line - 1))
            doc.breakpoint_cursors[line] = anchor
        for editor in doc.editors:
            editor.gutter.update()
        if self.debugger.active and doc.path:
            self.debugger.conditions[str(doc.path)] = dict(doc.breakpoint_conditions)
            self.debugger.set_breakpoints(doc.path, doc.breakpoints)

    def show_breakpoints(self):
        from atelier.debugger.panel import BreakpointPanel
        if not hasattr(self, 'breakpoint_panel'):
            self.breakpoint_panel = BreakpointPanel(self)
        panel = self.breakpoint_panel
        panel.refresh()
        panel.timer.start()
        panel.show()
        panel.raise_()
        panel.activateWindow()

    def restore_breakpoints(self, doc, points):
        doc.breakpoints.clear()
        doc.breakpoint_conditions.clear()
        doc.breakpoint_cursors.clear()
        for line, condition in points.items():
            if 1 <= line <= doc.editor.blockCount():
                doc.breakpoints.add(line)
                doc.breakpoint_cursors[line] = QTextCursor(
                    doc.editor.document().findBlockByNumber(line - 1))
                if condition:
                    doc.breakpoint_conditions[line] = condition
        for editor in doc.editors:
            editor.gutter.update()

    def remove_closed_breakpoint(self, path, line):
        points = self.closed_breakpoints.get(path)
        if points is None or line not in points:
            return
        del points[line]
        if not points:
            del self.closed_breakpoints[path]
        if self.debugger.active:
            self.debugger.conditions[path] = dict(points)
            self.debugger.set_breakpoints(path, points)

    def start_debug(self):
        if self.debugger.active or self.runner.state() != QProcess.ProcessState.NotRunning:
            self.message('Önce çalışan programı durdurun.')
            return
        if not self.current or not self.prepare_run_documents():
            return
        from atelier.projects.run_profiles import resolve_profile
        try:
            path, python, cwd, args, environment = resolve_profile(self)
        except ValueError as error:
            self.message(str(error))
            return
        points = {
            path: set(lines) for path,
            lines in self.closed_breakpoints.items() if Path(path).is_file()}
        points.update({str(d.path): set(d.breakpoints) for d in self.documents if d.path})
        self.debugger.conditions = {
            path: dict(lines) for path,
            lines in self.closed_breakpoints.items() if path in points}
        self.debugger.conditions.update(
            {str(d.path): dict(d.breakpoint_conditions) for d in self.documents if d.path})
        self.bottom.show()
        self.bottom.setCurrentIndex(2)
        self.output_root = cwd
        self.debugger.start(path, python, cwd, points, args, environment)

    def debug_state(self, state):
        for action in self.debug_toolbar_actions:
            action.setVisible(self.debugger.active)
        self.statusBar().showMessage('Debugger · ' + state, 5000)
        if state != 'Duraklatıldı':
            self.refresh_watches()
            for doc in self.documents:
                for editor in doc.editors:
                    editor.execution_line = None
                doc.paint_diagnostics()
        if state == 'Bitti':
            self.stack_list.clear()
            self.variables_tree.clear()

    def debug_paused(self, frames):
        self.bottom.show()
        self.bottom.setCurrentIndex(2)
        self.stack_list.clear()
        for frame in frames:
            item = QListWidgetItem(
                f"{
                    frame['name']} · {
                    Path(
                        frame.get(
                            'source',
                            {}).get(
                            'path',
                            '')).name}:{
                    frame['line']}")
            item.setData(Qt.ItemDataRole.UserRole, frame)
            self.stack_list.addItem(item)
        if self.stack_list.count():
            self.stack_list.setCurrentRow(0)
            self.select_frame(self.stack_list.item(0))

    def select_frame(self, item):
        frame = item.data(Qt.ItemDataRole.UserRole)
        for doc in self.documents:
            for editor in doc.editors:
                editor.execution_line = None
            doc.paint_diagnostics()
        path = frame.get('source', {}).get('path')
        if path:
            doc = self.open_path(path)
            if doc:
                self.goto(doc, {'line': frame['line'] - 1, 'character': 0})
                for editor in doc.editors:
                    editor.execution_line = frame['line']
                doc.paint_diagnostics()
        self.debugger.inspect_frame(frame['id'])

    def show_variables(self, variables):
        self.variables_tree.clear()
        self.add_variables(self.variables_tree, variables)
        self.refresh_watches()

    def add_variables(self, parent, variables):
        for variable in variables:
            item = QTreeWidgetItem(
                parent, [
                    variable['name'], variable.get(
                        'value', ''), variable.get(
                        'type', '')])
            reference = variable.get('variablesReference', 0)
            item.setData(0, Qt.ItemDataRole.UserRole, reference)
            item.setData(
                0,
                Qt.ItemDataRole.UserRole + 1,
                self.debugger.scope_reference if isinstance(
                    parent,
                    QTreeWidget) else parent.data(
                    0,
                    Qt.ItemDataRole.UserRole + 2))
            item.setData(0, Qt.ItemDataRole.UserRole + 2, reference)
            if reference:
                QTreeWidgetItem(item, ['…'])

    def expand_variable(self, item):
        reference = item.data(0, Qt.ItemDataRole.UserRole)
        if not reference:
            return
        item.setData(0, Qt.ItemDataRole.UserRole, 0)
        generation = self.debugger.frame_generation

        def receive(body):
            from shiboken6 import isValid
            if self.debugger.thread is None or self.debugger.frame_generation != generation or not isValid(
                    item):
                return
            item.takeChildren()
            self.add_variables(item, body.get('variables', []))
        self.debugger.send('variables', {'variablesReference': reference}, receive)

    def edit_breakpoint_condition(self, doc=None, line=None):
        doc = doc or self.current
        if not doc or doc.language != 'python':
            return
        line = line or doc.editor.textCursor().blockNumber() + 1
        condition, ok = QInputDialog.getText(self, 'Koşullu kesme noktası',
                                             f'{line}. satırda yalnızca bu ifade doğruysa dur (boş: koşulsuz):', text=doc.breakpoint_conditions.get(line, ''))
        if not ok:
            return
        if line not in doc.breakpoints:
            self.toggle_breakpoint(doc, line)
        if condition.strip():
            doc.breakpoint_conditions[line] = condition.strip()
        else:
            doc.breakpoint_conditions.pop(line, None)
        if self.debugger.active and doc.path:
            self.debugger.conditions[str(doc.path)] = dict(doc.breakpoint_conditions)
            self.debugger.set_breakpoints(doc.path, doc.breakpoints)
        self.statusBar().showMessage(
            f'{line}. satır kesme noktası: ' + (condition or 'koşulsuz'), 5000)

    def add_watch(self):
        expression = self.watch_input.text().strip()
        if expression and expression not in self.watch_expressions:
            self.watch_expressions.append(expression)
        self.watch_input.clear()
        self.refresh_watches()

    def remove_watch(self):
        item = self.watch_tree.currentItem()
        if item and item.text(0) in self.watch_expressions:
            self.watch_expressions.remove(item.text(0))
            self.refresh_watches()

    def refresh_watches(self):
        self.watch_tree.clear()
        for expression in self.watch_expressions:
            QTreeWidgetItem(self.watch_tree, [expression, 'Duraklatılınca hesaplanır'])
            if self.debugger.thread is not None:
                frame = self.debugger.frame_id

                def receive(result, expression=expression, frame=frame):
                    if self.debugger.thread is None or self.debugger.frame_id != frame:
                        return
                    for i in range(self.watch_tree.topLevelItemCount()):
                        row = self.watch_tree.topLevelItem(i)
                        if row.text(0) == expression:
                            row.setText(1, result.get('result', ''))
                self.debugger.evaluate(expression, receive)

    def edit_variable(self, item, column=1):
        if self.debugger.thread is None:
            return
        reference = item.data(0, Qt.ItemDataRole.UserRole + 1)
        value, ok = QInputDialog.getText(
            self, 'Değişken değerini değiştir', item.text(0) + ' =', text=item.text(1))
        if ok and reference:
            self.debugger.set_variable(item.text(0), value, reference,
                                       lambda _: self.debugger.inspect_frame(self.debugger.frame_id))
