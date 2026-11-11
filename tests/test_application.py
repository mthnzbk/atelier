"""Real LSP, Qt, process, Git, and debugpy integration checks."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QSettings, QProcess, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QListWidgetItem, QInputDialog
from PySide6.QtGui import QTextCursor
from atelier.app.window import Window


class StudioIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atelier-test-')
        self.root = Path(self.temp.name).resolve()
        settings = QSettings(str(self.root / 'test.ini'), QSettings.Format.IniFormat)
        settings.setValue('interpreter', sys.executable)
        trust = patch.object(Window, 'read_project_trust', return_value=True)
        trust.start()
        self.addCleanup(trust.stop)
        self.window = Window(root=self.root, settings=settings)
        self.messages = []
        self.window.message = self.messages.append
        self.window.show()
        self.wait(lambda: self.window.lsp.initialized)

    def tearDown(self):
        for doc in self.window.documents:
            doc.editor.document().setModified(False)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(self.window, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.temp.cleanup()

    def wait(self, predicate, timeout=25):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            self.app.processEvents()
            if predicate():
                return
            QTest.qWait(30)
        git = [(self.window.git_list.item(i).text(), self.window.git_list.item(i).data(Qt.ItemDataRole.UserRole))
               for i in range(self.window.git_list.count())]
        self.fail('Timeout. Output: ' + self.window.output.toPlainText() + '\nMessages: ' + str(self.messages) + '\nGit: ' + str(git))

    def request(self, method, params):
        replies = []
        self.window.lsp.request(method, params, replies.append)
        self.wait(lambda: bool(replies))
        return replies[0]

    def file(self, name, content):
        path = self.root / name
        path.write_text(content, encoding='utf-8')
        return self.window.open_path(path)

    def test_completion_diagnostics_split_and_editing(self):
        w = self.window
        editor = w.editor
        QTest.keyClicks(editor, 'import os')
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QTest.keyClicks(editor, 'os.pa')
        self.wait(lambda: editor.popup.isVisible() and editor.popup.count() > 0)
        labels = [editor.popup.item(i).text() for i in range(editor.popup.count())]
        self.assertIn('path', labels)
        editor.popup.setCurrentRow(labels.index('path'))
        QTest.keyClick(editor, Qt.Key.Key_Return)
        self.assertIn('os.path', editor.toPlainText())
        w.sync_document(w.current)
        version = w.current.version
        for _ in range(3):
            editor.highlighter.rehighlight()
            QTest.qWait(300)
        self.assertEqual(version, w.current.version)
        self.assertFalse(w.current.timer.isActive())
        editor.popup.hide()
        QTest.keyClick(editor, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        self.wait(lambda: editor.popup.isVisible() and editor.popup.count() > 0)
        editor.setPlainText('print(unknown_name)\n')
        self.wait(lambda: any('unknown_name' in d['message'] for d in w.current.diagnostics))
        self.assertIn(0, editor.diagnostic_lines)
        self.assertTrue(any(s.cursor.hasSelection() for s in editor.extraSelections()))
        editor.setPlainText('print(\n')
        self.wait(lambda: bool(w.current.diagnostics))
        w.toggle_split()
        doc = w.current
        self.assertEqual(2, len(doc.editors))
        self.assertIs(doc.editors[0].document(), doc.editors[1].document())
        doc.editors[1].insertPlainText('# shared\n')
        self.assertEqual(doc.editors[0].toPlainText(), doc.editors[1].toPlainText())
        w.toggle_split()
        editor.setPlainText('')
        QTest.keyClicks(editor, 'print(')
        self.assertEqual('print()', editor.toPlainText())
        QTest.keyClicks(editor, '42)')
        self.assertEqual('print(42)', editor.toPlainText())
        editor.toggle_comment()
        self.assertEqual('# print(42)', editor.toPlainText())
        editor.toggle_comment()
        self.assertEqual('print(42)', editor.toPlainText())
        editor.selectAll()
        editor.indent_selection()
        self.assertEqual('    print(42)', editor.toPlainText())
        editor.indent_selection(True)
        self.assertEqual('print(42)', editor.toPlainText())
        editor.setPlainText('\n'.join(str(i) for i in range(120)))
        self.app.processEvents()
        self.assertEqual(editor.viewportMargins().left(), editor.gutter_width())
        self.assertFalse(editor.gutter.grab().isNull())

    def test_peek_definition_opens_inline_and_navigates_on_request(self):
        from PySide6.QtWidgets import QPushButton

        window = self.window
        target = self.root / 'preview_provider.py'
        target.write_text('# Provider\ndef greet(name):\n    return name.upper()\n', encoding='utf-8')
        source = self.file('preview_caller.py', 'from preview_provider import greet\nresult = greet("Ada")\n')
        editor = source.editor
        cursor = editor.textCursor()
        cursor.setPosition(editor.document().findBlockByNumber(1).position() + len('result = gr'))
        editor.setTextCursor(cursor)
        count = window.tabs.count()

        QTest.keyClick(editor, Qt.Key.Key_F12, Qt.KeyboardModifier.AltModifier)
        self.wait(lambda: window.definition_preview is not None)
        preview = window.definition_preview
        self.assertIs(source, window.current)
        self.assertEqual(count, window.tabs.count())
        self.assertIs(editor.viewport(), preview.parentWidget())
        self.assertTrue(preview.code.isReadOnly())
        self.assertIn('def greet(name):', preview.code.toPlainText())
        self.assertEqual(1, preview.code.textCursor().blockNumber())
        QTest.keyClick(preview.code, Qt.Key.Key_Escape)
        self.assertIsNone(window.definition_preview)
        self.assertTrue(editor.hasFocus())
        self.assertIs(source, window.current)

        window.actions['peek_definition'].trigger()
        self.wait(lambda: window.definition_preview is not None)
        open_button = next(button for button in window.definition_preview.findChildren(QPushButton)
                           if button.text() == 'Sekmede aç')
        open_button.click()
        self.assertIsNone(window.definition_preview)
        self.assertEqual(target, window.current.path)
        self.assertEqual(1, window.editor.textCursor().blockNumber())

    def test_lsp_navigation_rename_format_and_environment(self):
        w = self.window
        doc = self.file('example.py', 'def greet(name):\n    """Say hello."""\n    return name\n\nvalue=greet("Ada")\nprint(value)\n')
        w.sync_document(doc)
        params = {'textDocument': {'uri': doc.uri}, 'position': {'line': 4, 'character': 8}}
        definition = self.request('textDocument/definition', params)
        self.assertTrue(definition)
        self.assertEqual(0, definition[0]['range']['start']['line'])
        hover = self.request('textDocument/hover', params)
        self.assertIn('greet', str(hover))
        signature = self.request('textDocument/signatureHelp', {'textDocument': {'uri': doc.uri}, 'position': {'line': 4, 'character': 12}})
        self.assertTrue(signature['signatures'])
        rename = self.request('textDocument/rename', {**params, 'newName': 'welcome'})
        self.assertTrue(w.apply_workspace_edit(rename))
        self.assertIn('def welcome', doc.editor.toPlainText())
        self.assertIn('value=welcome', doc.editor.toPlainText())
        formatted = []
        w.format_document(doc, lambda: formatted.append(True))
        self.wait(lambda: bool(formatted))
        self.assertIn('value = welcome', doc.editor.toPlainText())
        self.assertTrue(w.save(doc=doc, allow_format=False))
        self.assertIn('welcome', doc.path.read_text())
        # Environment replacement restarts the server and reopens all documents.
        old_server = w.lsp
        w.start_lsp()
        self.wait(lambda: w.lsp.initialized and doc.synced is not None)
        self.assertIsNot(old_server, w.lsp)
        self.assertEqual(sys.executable, w.lsp.interpreter)

    def test_search_replace_run_and_theme(self):
        w = self.window
        doc = self.file('alpha.py', 'value = "orange"\nprint(value)\n')
        self.file('beta.py', '# orange\n')
        w.tabs.setCurrentWidget(doc)
        w.find_text.setText('orange')
        w.replace_text.setText('apple')
        w.replace_all()
        self.assertIn('apple', doc.editor.toPlainText())
        self.assertTrue(w.save(doc=doc, allow_format=False))
        w.project_query.setText('apple')
        w.search_project()
        self.wait(lambda: w.search_results.count() == 1)
        w.project_replace.setText('banana')
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok):
            w.replace_project()
            self.wait(lambda: 'banana' in doc.path.read_text())
        w.run_file()
        self.wait(lambda: '[Çıkış kodu: 0]' in w.output.toPlainText())
        self.assertIn('banana', w.output.toPlainText())
        w.theme = 'Açık'
        w.font_size = 15
        w.apply_theme()
        self.assertIn('#ffffff', QApplication.instance().styleSheet())
        self.app.processEvents()
        self.assertEqual(15, doc.editor.font().pointSize())
        w.theme = 'Gece'
        w.apply_theme()
        self.assertFalse(w.grab().isNull())
        note = self.file('notes.md', '# Project notes\n')
        self.assertIsNone(note.synced, 'Non-Python documents must not be sent to pylsp')
        formatted = []
        w.format_document(note, lambda: formatted.append(True))
        self.assertTrue(formatted)

    @unittest.skipUnless(shutil.which('git'), 'Git not installed')
    def test_git_diff(self):
        w = self.window
        def git(*args):
            return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True)
        git('init')
        git('config', 'user.name', 'Test')
        git('config', 'user.email', 'test@example.invalid')
        doc = self.file('tracked.py', 'answer = 1\n')
        git('add', 'tracked.py')
        git('commit', '-m', 'initial')
        doc.editor.setPlainText('answer = 2\n')
        w.save(doc=doc, allow_format=False)
        w.refresh_git()
        self.wait(lambda: '+answer = 2' in w.diff.toPlainText())
        self.assertIn(0, doc.editor.git_lines)
        self.wait(lambda: any('tracked.py' in w.git_list.item(i).text() for i in range(w.git_list.count())))
        nested = self.root / 'package'
        nested.mkdir()
        nested_path = nested / 'new.py'
        nested_path.write_text('answer = 3\n')
        w.set_project(nested)
        self.wait(lambda: any(w.git_list.item(i).data(Qt.ItemDataRole.UserRole) == str(nested_path)
                              for i in range(w.git_list.count())))

    def test_debugger_breakpoint_step_variables_and_continue(self):
        w = self.window
        doc = self.file('debug_target.py', 'value = 40\nvalue += 2\nprint(value)\n')
        w.toggle_breakpoint(doc, 2)
        w.start_debug()
        self.wait(lambda: w.debugger.thread is not None, timeout=35)
        self.wait(lambda: w.variables_tree.topLevelItemCount() > 0)
        values = {w.variables_tree.topLevelItem(i).text(0): w.variables_tree.topLevelItem(i).text(1)
                  for i in range(w.variables_tree.topLevelItemCount())}
        self.assertEqual('40', values.get('value'))
        w.debugger.action('next')
        self.wait(lambda: doc.editor.execution_line == 3)
        self.wait(lambda: any(w.variables_tree.topLevelItem(i).text(0) == 'value' and
                              w.variables_tree.topLevelItem(i).text(1) == '42'
                              for i in range(w.variables_tree.topLevelItemCount())))
        w.debugger.action('continue')
        self.wait(lambda: not w.debugger.active)
        self.assertIn('42', w.output.toPlainText())

    def test_callable_completion_and_markdown(self):
        w = self.window
        editor = w.editor
        for kind, name in [(3, 'len'), (2, 'append'), (7, 'Task'), (4, 'Thing')]:
            editor.setPlainText(name[:2])
            editor.moveCursor(QTextCursor.MoveOperation.End)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, {'label': name, 'kind': kind})
            editor.accept_completion(item)
            self.assertEqual(name + '()', editor.toPlainText())
            self.assertEqual(len(name) + 1, editor.textCursor().position())
        editor.setPlainText('le("abc")')
        cursor = editor.textCursor()
        cursor.setPosition(2)
        editor.setTextCursor(cursor)
        item = QListWidgetItem('len')
        item.setData(Qt.ItemDataRole.UserRole, {'label': 'len', 'kind': 3, 'insertText': 'len()'})
        editor.accept_completion(item)
        self.assertEqual('len("abc")', editor.toPlainText())
        editor.setPlainText('from math import sq')
        editor.moveCursor(QTextCursor.MoveOperation.End)
        item.setData(Qt.ItemDataRole.UserRole, {'label': 'sqrt', 'kind': 3})
        editor.accept_completion(item)
        self.assertEqual('from math import sqrt', editor.toPlainText())
        # Real language-server completion, not just synthetic CompletionItems.
        editor.setPlainText('le')
        editor.moveCursor(QTextCursor.MoveOperation.End)
        w.complete()
        self.wait(lambda: editor.popup.count() > 0)
        candidates = [editor.popup.item(i) for i in range(editor.popup.count())]
        candidate = next(item for item in candidates if item.data(Qt.ItemDataRole.UserRole)['label'].split('(')[0] == 'len')
        editor.accept_completion(candidate)
        self.assertEqual('len()', editor.toPlainText())
        doc = self.file('guide.md', '# Title\n\n**Bold** and `code`\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```python\nprint(42)\n```\n')
        self.assertEqual('markdown', doc.language)
        self.assertIsNone(doc.synced)
        self.assertEqual('markdown', doc.editor.highlighter.language)
        self.assertIn('<table>', doc.preview.rendered_html)
        self.assertIn('<strong>Bold</strong>', doc.preview.rendered_html)
        self.assertIn('Title', doc.preview.browser.toPlainText())
        doc.editor.appendPlainText('\n## Live update\n')
        self.wait(lambda: 'Live update' in doc.preview.rendered_html)
        doc.markdown_mode.setCurrentIndex(3)
        self.assertEqual(1, doc.preview.tabs.currentIndex())
        self.assertIn('<html>', doc.preview.html_source.toPlainText())

    def test_external_changes_and_folding(self):
        w = self.window
        doc = self.file('watched.py', 'def outer():\n    value = 1\n    return value\n\nprint(outer())\n')
        doc.editor.structure.rebuild()
        self.assertIn(0, doc.editor.structure.regions)
        doc.editor.structure.toggle(0)
        self.assertFalse(doc.editor.document().findBlockByNumber(1).isVisible())
        w.goto(doc, {'line': 1, 'character': 0})
        self.assertTrue(doc.editor.document().findBlockByNumber(1).isVisible())
        self.assertFalse(doc.editor.minimap.grab().isNull())
        disk = 'def outer():\n    return 42\n'
        doc.path.write_text(disk, encoding='utf-8')
        self.wait(lambda: doc.external_pending)
        self.assertIn('value = 1', doc.editor.toPlainText())
        self.assertTrue(doc.external_bar.isVisible())
        self.assertTrue(w.reload_document(doc))
        self.assertEqual(disk, doc.editor.toPlainText())
        self.assertFalse(doc.external_pending)
        doc.editor.appendPlainText('# local change')
        doc.path.write_text('# external change\n', encoding='utf-8')
        w.file_monitor.check()
        doc.keep_external_local()
        self.assertTrue(doc.editor.document().isModified())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(w.save(doc=doc, allow_format=False))
        self.assertEqual('# external change\n', doc.path.read_text())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(w.save(doc=doc, allow_format=False))
        w.file_monitor.check()
        self.assertFalse(doc.external_pending, 'Own writes must not create false external alerts')
        doc.path.unlink()
        w.file_monitor.check()
        self.assertTrue(doc.external_pending)
        self.assertIn('# local change', doc.editor.toPlainText())

    def test_interactive_terminal(self):
        w = self.window
        chunks = []
        w.terminal.received.connect(chunks.append)
        w.show_terminal()
        self.wait(lambda: w.terminal.ready)
        w.terminal.send_input('echo ATELIER_TERMINAL_OK\r')
        self.wait(lambda: 'ATELIER_TERMINAL_OK' in ''.join(chunks))
        # A real REPL checks PTY stdin, prompts, and persistent terminal state.
        command = '"' + sys.executable + '" -q\r' if os.name == 'nt' else sys.executable + ' -q\r'
        w.terminal.send_input(command)
        self.wait(lambda: '>>>' in ''.join(chunks))
        w.terminal.send_input('print(6 * 7)\r')
        self.wait(lambda: '42' in ''.join(chunks))
        w.terminal.send_input('exit()\r')
        w.terminal.shutdown()
        self.assertEqual(QProcess.ProcessState.NotRunning, w.terminal.process.state())

    @unittest.skipUnless(shutil.which('git'), 'Git not installed')
    def test_git_stage_unstage_commit_history(self):
        w = self.window
        def git(*args):
            return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True)
        git('init')
        git('config', 'user.name', 'Test')
        git('config', 'user.email', 'test@example.invalid')
        doc = self.file('stage.py', 'value = 42\n')
        w.refresh_git()
        self.wait(lambda: any('stage.py' in w.git_list.item(i).text() for i in range(w.git_list.count())))
        for i in range(w.git_list.count()):
            if 'stage.py' in w.git_list.item(i).text():
                w.git_list.setCurrentRow(i)
                break
        w.git_stage()
        self.wait(lambda: b'stage.py' in git('diff', '--cached', '--name-only').stdout)
        w.git_unstage()
        self.wait(lambda: not git('diff', '--cached', '--name-only').stdout.strip())
        self.assertTrue(doc.path.exists())
        w.git_stage()
        self.wait(lambda: b'stage.py' in git('diff', '--cached', '--name-only').stdout)
        committed = []
        w.git_operation(['commit', '-m', 'integration commit'], after=lambda: committed.append(True))
        self.wait(lambda: bool(committed))
        self.assertIn(b'integration commit', git('log', '-1', '--format=%s').stdout)
        output = []
        w.git_command(['log', '-1', '--oneline'], lambda code, text: output.append((code, text)))
        self.wait(lambda: bool(output))
        self.assertIn('integration commit', output[0][1])

    @unittest.skipUnless(shutil.which('git'), 'Git not installed')
    def test_git_local_push_pull_and_branch(self):
        w = self.window
        def git(*args):
            return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True)
        git('init')
        git('config', 'user.name', 'Test')
        git('config', 'user.email', 'test@example.invalid')
        self.file('remote_test.py', 'value = 1\n')
        git('add', 'remote_test.py')
        git('commit', '-m', 'initial')
        remote = self.root / 'local-remote.git'
        git('init', '--bare', str(remote))
        git('remote', 'add', 'origin', str(remote))
        git('push', '-u', 'origin', 'HEAD')
        git('config', 'user.test', 'local-only')
        (self.root / 'remote_test.py').write_text('value = 2\n')
        git('add', 'remote_test.py')
        git('commit', '-m', 'second')
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            w.git_remote('push')
            self.wait(lambda: git('rev-parse', 'HEAD').stdout == git('rev-parse', '@{upstream}').stdout)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            w.git_remote('pull')
            self.wait(lambda: not w.processes)
        changed = []
        w.git_operation(['switch', '-c', 'feature/editor-test'], after=lambda: changed.append(True))
        self.wait(lambda: bool(changed))
        self.assertEqual(b'feature/editor-test', git('branch', '--show-current').stdout.strip())
        history = []
        w.show_text = lambda title, text: history.append(text)
        w.git_history()
        self.wait(lambda: bool(history))
        self.assertIn('second', history[0])

    def test_snippets_and_command_palette(self):
        from atelier.ui.palette import CommandPalette
        w = self.window
        editor = w.editor
        QTest.keyClicks(editor, 'def')
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        self.assertEqual('function_name', editor.textCursor().selectedText())
        QTest.keyClicks(editor, 'greet')
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        self.assertEqual('parameters', editor.textCursor().selectedText())
        QTest.keyClicks(editor, 'name')
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        self.assertEqual('pass', editor.textCursor().selectedText())
        QTest.keyClicks(editor, 'return name')
        self.assertEqual('def greet(name):\n    return name', editor.toPlainText())
        palette = CommandPalette(w)
        palette.query.setText('test panel')
        self.assertEqual(1, palette.listing.count())
        palette.execute()
        self.assertIs(w.test_panel, w.bottom.currentWidget())

    def test_web_language_highlighting_and_html_completion(self):
        w = self.window
        samples = {'json': '{"key": true}', 'yaml': 'key: true', 'yml': 'key: true',
                   'html': '<main>text</main>', 'css': '/* first\nsecond */\na { color: red; }',
                   'js': '/* first\nsecond */\nconst value = 1;', 'toml': '[save]\nformat_on_save = true',
                   'sql': "SELECT 'Ada' AS name;"}
        for suffix, source in samples.items():
            with self.subTest(suffix=suffix):
                doc = self.file(f'sample.{suffix}', source)
                self.assertIsNotNone(doc.editor.highlighter.document_lexer)
                self.assertIsNone(doc.synced)
                self.assertTrue(doc.editor.highlighter.document_tokens[0][1])
                if suffix in ('css', 'js'):
                    from pygments.token import Comment
                    self.assertTrue(any(token in Comment for _, _, token in doc.editor.highlighter.document_tokens[1][1]))
        doc = w.open_path(self.root / 'sample.html')
        editor = doc.editor
        editor.setPlainText('')
        editor.setFocus()
        QTest.keyClicks(editor, '<div')
        self.wait(lambda: editor.popup.isVisible())
        self.assertEqual('div', editor.popup.currentItem().text())
        QTest.keyClick(editor, Qt.Key.Key_Return)
        self.assertEqual('<div></div>', editor.toPlainText())
        self.assertEqual(5, editor.textCursor().position())
        editor.setPlainText('<di class="main">text</div>')
        cursor = editor.textCursor()
        cursor.setPosition(3)
        editor.setTextCursor(cursor)
        w.complete()
        for index in range(editor.popup.count()):
            if editor.popup.item(index).text() == 'div':
                editor.popup.setCurrentRow(index)
                break
        QTest.keyClick(editor, Qt.Key.Key_Return)
        self.assertEqual('<div class="main">text</div>', editor.toPlainText())
        editor.setPlainText('<a hr>')
        cursor = editor.textCursor()
        cursor.setPosition(5)
        editor.setTextCursor(cursor)
        w.complete()
        self.assertEqual('href', editor.popup.currentItem().text())
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        self.assertEqual('<a href="">', editor.toPlainText())
        editor.setPlainText('html5')
        editor.moveCursor(QTextCursor.MoveOperation.End)
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        self.assertIn('<!doctype html>', editor.toPlainText())
        self.assertEqual('tr', editor.textCursor().selectedText())
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        self.assertEqual('Başlık', editor.textCursor().selectedText())

    def test_structured_diagnostics_and_two_space_indentation(self):
        w = self.window
        for name, invalid, valid in (
            ('broken.json', '{\n  "a": }\n', '{"a": 1}'),
            ('broken.yaml', 'root:\n\tbad: 1\n', 'root:\n  good: 1\n'),
            ('broken.toml', '[save]\nx = @\n', '[save]\nx = true\n'),
            ('atelier.toml', '[tasks.test]\nargs = "-m pytest"\n', '[tasks.test]\nargs = ["-m", "pytest"]\n'),
        ):
            with self.subTest(name=name):
                doc = self.file(name, invalid)
                self.wait(lambda: bool(doc.diagnostics))
                self.assertEqual(1, doc.diagnostics[0]['range']['start']['line'])
                self.assertTrue(any(name + ':2:' in w.problems.item(i).text() for i in range(w.problems.count())))
                doc.editor.setPlainText(valid)
                self.wait(lambda: not doc.validation_timer.isActive() and not w.validation_workers and not w.validation_pending)
                self.assertFalse(doc.diagnostics)
        for suffix in ('html', 'css', 'js', 'json', 'yaml', 'toml'):
            doc = self.file('indent.' + suffix, '')
            QTest.keyClick(doc.editor, Qt.Key.Key_Tab)
            self.assertEqual('  ', doc.editor.toPlainText(), suffix)

    def test_json_format_manual_and_on_save(self):
        w = self.window
        doc = self.file('example.json', '{"number":1e+999,"same":1,"same":2}')
        w.format_document(doc)
        self.wait(lambda: not w.save_workers)
        self.assertIn('\n  "number": 1e+999,', doc.editor.toPlainText())
        self.assertEqual(2, doc.editor.toPlainText().count('"same"'))
        self.assertTrue(doc.editor.document().isModified())
        self.assertNotIn('\n', doc.path.read_text(encoding='utf-8'))
        (self.root / 'atelier.toml').write_text('[save]\nformat_web_on_save = true\n', encoding='utf-8')
        doc.editor.setPlainText('{"items":[1,2]}')
        self.assertTrue(w.save(doc=doc))
        self.wait(lambda: not w.save_workers)
        self.assertEqual('{\n  "items": [\n    1,\n    2\n  ]\n}\n', doc.path.read_text(encoding='utf-8'))

    def test_python_formatters_format_html_css_and_js(self):
        w = self.window
        for suffix, source, expected in (
            ('html', '<main>\n<p>hi</p>\n</main>', '\n  <p>hi</p>\n'),
            ('css', 'p{color:red}', '\n  color: red\n'),
            ('js', 'function f(){return 1;}', '\n  return 1;\n'),
        ):
            doc = self.file('sample.' + suffix, source)
            w.format_document(doc)
            self.wait(lambda: not w.save_workers)
            self.assertIn(expected, doc.editor.toPlainText(), self.messages)
        w.format_web_on_save = True
        doc.editor.setPlainText('function f(){return 2;}')
        self.assertTrue(w.save(doc=doc))
        self.wait(lambda: not w.save_workers)
        self.assertIn('  return 2;', doc.path.read_text(encoding='utf-8'))

    def test_project_task_manager_preserves_shared_configuration(self):
        from atelier.projects.tasks import ProjectTasksDialog
        from atelier.ui.palette import CommandPalette
        from atelier.projects.config import load_project_config
        w = self.window
        path = self.root / 'atelier.toml'
        path.write_text(
            '# Project notes\n[save]\nsave_trim = true # keep this\n'
            '[profiles.app]\nfile = "app.py"\n'
            '[tasks.test]\nlabel = "Test" # task label\nargs = ["-m", "pytest"]\n'
            '[tasks.test.env]\nMODE = "fast"\n', encoding='utf-8')
        document = w.open_path(path)
        dialog = ProjectTasksDialog(w)
        dialog.save_change('test', dict(label='Tests', args=['-m', 'pytest', 'two words'], cwd='.'))
        text = path.read_text(encoding='utf-8')
        self.assertIn('# Project notes', text)
        self.assertIn('save_trim = true # keep this', text)
        self.assertIn('# task label', text)
        config = load_project_config(self.root)
        self.assertEqual('app.py', config['profiles']['app']['file'])
        self.assertEqual({'MODE': 'fast'}, config['tasks']['test']['env'])
        self.assertEqual('two words', config['tasks']['test']['args'][-1])
        self.assertEqual(text, document.editor.toPlainText())

        dialog.save_change('quick', dict(label='Quick check', args=['-c', 'print("TASK_MANAGER_OK")'], cwd='.'))
        palette = CommandPalette(w)
        palette.filter('quick check')
        self.assertEqual(1, palette.listing.count())
        palette.execute()
        self.wait(lambda: 'TASK_MANAGER_OK' in w.output.toPlainText() and w.runner.state() == QProcess.ProcessState.NotRunning)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            dialog.delete_selected()
        self.assertNotIn('quick', load_project_config(self.root)['tasks'])
        document.editor.appendPlainText('# unsaved')
        with self.assertRaisesRegex(ValueError, 'Önce editördeki'):
            dialog.save_change('test', dict(label='Blocked', args=['-m', 'pytest'], cwd='.'))
        document.editor.document().setModified(False)
        with path.open('a', encoding='utf-8') as handle:
            handle.write('\n# External edit\n')
        with self.assertRaisesRegex(ValueError, 'değişti'):
            dialog.save_change('test', dict(label='Blocked', args=['-m', 'pytest'], cwd='.'))
        self.assertIn('# External edit', path.read_text(encoding='utf-8'))

    def test_shared_config_applies_to_tasks_profiles_and_save(self):
        from atelier.ui.palette import CommandPalette
        from atelier.projects.run_profiles import RunProfilesDialog
        w = self.window
        (self.root / 'sub').mkdir()
        target = self.root / 'sub' / 'app.py'
        target.write_text('import sys\nprint("PROFILE", sys.argv[1])\n', encoding='utf-8')
        config = self.root / 'atelier.toml'
        config.write_text(
            'default_profile = "app"\n'
            '[tasks.probe]\nlabel = "Probe project task"\ncwd = "sub"\n'
            "args = ['-c', 'import os; print(os.getenv(\"ATELIER_TEST\")); print(\"app.py:2: diagnostic\")']\n"
            '[tasks.probe.env]\nATELIER_TEST = "TASK_OK"\n'
            '[profiles.app]\nfile = "sub/app.py"\nargs = ["two words"]\n'
            '[save]\nsave_trim = true\n', encoding='utf-8')
        palette = CommandPalette(w)
        palette.filter('probe')
        self.assertEqual(1, palette.listing.count())
        palette.execute()
        self.wait(lambda: 'TASK_OK' in w.output.toPlainText() and w.runner.state() == QProcess.ProcessState.NotRunning)
        self.assertEqual((str(target), 1), w.output.location('app.py:2: diagnostic'))
        profiles = RunProfilesDialog(w)
        self.assertEqual('app', profiles.names.currentText())
        self.assertTrue(profiles.fields['args'].isReadOnly())
        profiles.reject()
        w.run_file()
        self.wait(lambda: 'PROFILE two words' in w.output.toPlainText() and w.runner.state() == QProcess.ProcessState.NotRunning)
        note = self.file('save.txt', 'clean\n')
        note.editor.setPlainText('clean   \n')
        self.assertTrue(w.save(doc=note))
        self.wait(lambda: note.path.read_text(encoding='utf-8') == 'clean\n' and not w.save_workers)

    def test_session_recovery_and_qsettings(self):
        w = self.window
        doc = self.file('restored.py', 'value = 1\n')
        doc.editor.appendPlainText('# unsaved recovery')
        w.toggle_breakpoint(doc, 1)
        doc.breakpoint_conditions[1] = 'value > 0'
        w.toggle_split()
        cursor = doc.editor.textCursor()
        cursor.setPosition(3)
        doc.editor.setTextCursor(cursor)
        w.watch_expressions = ['value * 2']
        w.sidebar.hide()
        w.showMaximized()
        self.app.processEvents()
        w.checkpoint()
        snapshot = w.session_store.path.read_bytes()
        settings = w.settings
        for d in w.documents:
            d.editor.document().setModified(False)
        w.close()
        w.session_store.path.write_bytes(snapshot)
        self.window = Window(root=self.root, settings=settings)
        self.window.message = self.messages.append
        self.window.show()
        self.wait(lambda: self.window.lsp.initialized)
        restored = self.window.current
        self.assertEqual(doc.path, restored.path)
        self.assertIn('# unsaved recovery', restored.editor.toPlainText())
        self.assertTrue(restored.editor.document().isModified())
        self.assertEqual(2, len(restored.editors))
        self.assertEqual(3, restored.editor.textCursor().position())
        self.assertIn(1, restored.breakpoints)
        self.assertEqual('value > 0', restored.breakpoint_conditions[1])
        self.assertEqual(['value * 2'], self.window.watch_expressions)
        self.assertTrue(self.window.isMaximized())
        self.assertTrue(self.window.sidebar.isHidden())
        self.assertIn('window/geometry', self.window.settings.allKeys())

    def test_editor_stays_open_without_python(self):
        from atelier.projects.environments import PYTHON_MISSING

        window = self.window
        with patch('atelier.app.features.projects.select_project_python', return_value=''):
            window.rescan_python()
        self.assertTrue(window.isVisible())
        self.assertFalse(window.lsp.initialized)
        self.assertEqual('Python bulunamadı', window.python_label.text())
        window.editor.setPlainText('print(42)')
        window.run_file()
        window.start_debug()
        window.test_panel.start('run')
        self.assertEqual([PYTHON_MISSING, PYTHON_MISSING], self.messages)
        self.assertEqual(PYTHON_MISSING, window.test_panel.label.text())
        self.assertEqual('print(42)', window.editor.toPlainText())

    def test_python_status_explains_broken_venv_and_restarts_lsp(self):
        from atelier.projects.environments import environment_python
        from atelier.ui.python_status import PythonStatusDialog
        from PySide6.QtWidgets import QPushButton

        window = self.window
        broken = self.root / '.venv'
        candidate = environment_python(broken)
        candidate.parent.mkdir(parents=True)
        candidate.touch()
        missing = self.root / 'missing-base-python'
        (broken / 'pyvenv.cfg').write_text(f'home = {missing}\n', encoding='utf-8')
        window.rescan_python()
        self.assertNotEqual(str(candidate), window.interpreter)
        panel = PythonStatusDialog(window)
        try:
            self.wait(lambda: panel.fields['Python sürümü'].text().startswith('Python '))
            self.assertEqual(window.interpreter, panel.fields['Yorumlayıcı'].text())
            self.assertIn(str(missing), panel.details.toPlainText())
            self.assertEqual('LSP hazır', panel.fields['Dil sunucusu'].text())
            window.lsp.kill()
            self.wait(lambda: 'çıkış kodu' in panel.details.toPlainText())
            restart = next(button for button in panel.findChildren(QPushButton)
                           if button.text() == 'LSP’yi yeniden başlat')
            restart.click()
            self.wait(lambda: panel.fields['Dil sunucusu'].text() == 'LSP hazır')
            self.assertNotIn('çıkış kodu', panel.details.toPlainText())
        finally:
            panel.close()

    def test_project_trust_gates_processes_and_remembers_choice(self):
        from atelier.app.features.projects import ProjectsFeatures

        window = self.window
        restricted = self.root / 'review project'
        restricted.mkdir()
        def restrict_dialog():
            dialog = QApplication.activeModalWidget()
            if isinstance(dialog, QMessageBox):
                button = next((button for button in dialog.buttons()
                               if button.text() == 'Kısıtlı aç'), None)
                if button:
                    button.click()
                else:
                    dialog.reject()

        with (patch.object(Window, 'read_project_trust', ProjectsFeatures.read_project_trust),
              patch.object(window, 'show_project_trust', wraps=window.show_project_trust) as prompt):
            window.set_project(restricted)
            QTimer.singleShot(100, restrict_dialog)
            self.wait(lambda: window.read_project_trust(restricted) is False)
            prompt.assert_called_once()
            self.assertFalse(window.project_trusted)
            self.assertFalse(window.lsp.initialized)
            self.assertIsNone(window.terminal)
            self.assertEqual('', window.interpreter)
            source = restricted / 'example.py'
            source.write_text('print(42)\n', encoding='utf-8')
            doc = window.open_path(source)
            self.assertEqual('print(42)\n', doc.editor.toPlainText())
            doc.editor.setPlainText('print(43)\n')
            self.assertTrue(window.save(doc=doc))
            window.project_query.setText('print(43)')
            window.search_project()
            self.wait(lambda: window.search_results.count() == 1)
            git = []
            window.git_command(['status'], lambda code, text: git.append(code))
            self.assertEqual([1], git)
            self.assertFalse(window.git_reads)
            window.run_file()
            window.run_project_task('probe')
            window.test_panel.start('run')
            self.assertEqual(3, len(self.messages))
            self.assertTrue(all('Proje güveni' in message for message in self.messages))
            window.set_project_trust(True)
            self.wait(lambda: window.lsp.initialized and window.terminal.ready)
            self.assertTrue(window.read_project_trust(restricted))
            window.set_project_trust(False)
            self.assertFalse(window.read_project_trust(restricted))
            self.assertFalse(window.lsp.initialized)
            self.assertIsNone(window.terminal)
            prompt.reset_mock()
            window.set_project(restricted)
            self.app.processEvents()
            prompt.assert_not_called()

    def test_terminal_tabs_keep_independent_project_sessions(self):
        window = self.window
        self.wait(lambda: window.terminal.ready)
        first = window.terminal
        first_pid = first.process.processId()
        window.new_terminal()
        self.wait(lambda: window.terminal.ready)
        second = window.terminal
        self.assertIsNot(first, second)
        self.assertNotEqual(first_pid, second.process.processId())
        chunks = []
        second.received.connect(chunks.append)
        second.send_input('echo SECOND_TERMINAL\r')
        self.wait(lambda: ''.join(chunks).count('SECOND_TERMINAL') >= 2)
        other = self.root / 'second-project'
        other.mkdir()
        window.set_project(other)
        self.wait(lambda: window.terminal.ready)
        self.assertEqual(other, window.terminal.root)
        window.set_project(self.root)
        self.assertIs(second, window.terminal)
        tabs = window.terminal_tabs.pages[self.root]
        window.terminal_tabs.close_session(tabs, tabs.indexOf(second), confirm=False)
        self.assertIs(first, window.terminal)
        self.assertEqual(first_pid, first.process.processId())

    def test_startup_terminal_and_profile_pickers(self):
        from atelier.projects.run_profiles import RunProfilesDialog
        from PySide6.QtWidgets import QFileDialog

        window = self.window
        self.wait(lambda: window.terminal.ready)
        pid = window.terminal.process.processId()
        window.show_terminal()
        self.assertEqual(pid, window.terminal.process.processId())
        entry = self.file('profile_main.py', 'import os, sys\nprint("PROFILE", os.getcwd(), sys.argv[1])\n')
        cwd = self.root / 'work dir'
        cwd.mkdir()
        dialog = RunProfilesDialog(window)
        with patch.object(QInputDialog, 'getText', return_value=('Launch profile', True)):
            dialog.add()
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(entry.path), '')):
            dialog.choose_path('file')
        with patch.object(QFileDialog, 'getExistingDirectory', return_value=str(cwd)):
            dialog.choose_path('cwd')
        dialog.fields['args'].setText('"two words"')
        dialog.accept_profiles()
        window.new()
        selector = window.profile_selector
        selector.populate()
        selector.profile_menu.actions()[0].trigger()
        self.assertEqual('Etkin dosya', selector.text())
        selector.populate()
        named = next(action for action in selector.profile_menu.actions() if action.text() == 'Launch profile')
        named.trigger()
        self.assertEqual('Launch profile', selector.text())
        self.assertIn(str(entry.path), selector.toolTip())
        self.assertIn(window.interpreter, selector.toolTip())
        window.run_file()
        self.wait(lambda: f'PROFILE {cwd} two words' in window.output.toPlainText())
        self.wait(lambda: window.runner.state() == QProcess.ProcessState.NotRunning)
        with patch.object(window.debugger, 'start') as start:
            window.start_debug()
        args = start.call_args.args
        self.assertEqual(entry.path, args[0])
        self.assertEqual(cwd, args[2])
        self.assertEqual(['two words'], args[4])

    @unittest.skipUnless(os.name == 'nt', 'Windows command prompt')
    def test_terminal_refreshes_only_at_idle_prompt(self):
        from atelier.projects.environments import environment_python

        window = self.window
        terminal = window.terminal
        self.wait(lambda: terminal.ready and terminal.prompt_idle)
        original = window.interpreter
        target = self.root / '.venv'
        subprocess.run([original, '-m', 'venv', '--without-pip', str(target)],
                       check=True, timeout=25)
        first_pid = terminal.process.processId()
        window.activate_project_python(str(environment_python(target)))
        self.wait(lambda: terminal.ready and terminal.prompt_idle)
        self.assertNotEqual(first_pid, terminal.process.processId())
        output = []
        terminal.received.connect(output.append)
        terminal.send_input('echo %VIRTUAL_ENV%\r')
        self.wait(lambda: str(target) in ''.join(output) and terminal.prompt_idle)
        second_pid = terminal.process.processId()
        terminal.send_input('ping -n 5 127.0.0.1 >nul & echo ATELIER-BUSY-DONE\r')
        self.assertFalse(terminal.prompt_idle)
        window.activate_project_python(original)
        self.assertEqual(second_pid, terminal.process.processId())
        self.wait(lambda: terminal.prompt_idle and 'ATELIER-BUSY-DONE' in ''.join(output))
        self.assertEqual(second_pid, terminal.process.processId())

    def test_visual_tab_order_and_reopen_shortcuts(self):
        w = self.window
        untitled = w.current
        a = self.file('a.py', 'a = 1\n')
        b = self.file('b.py', 'b = 2\n')
        c = self.file('c.py', 'c = 3\n')
        w.close_tab(w.tabs.indexOf(untitled))
        w.tabs.setCurrentWidget(a)
        a.editor.setFocus()
        self.app.processEvents()
        QTest.keyClick(a.editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
        self.assertIs(w.current, b)
        QTest.keyClick(b.editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
        self.assertIs(w.current, c)
        QTest.keyClick(c.editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
        self.assertIs(w.current, a)
        QTest.keyClick(a.editor, Qt.Key.Key_Tab,
                       Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertIs(w.current, c)
        w.tabs.tabBar().moveTab(w.tabs.indexOf(c), 0)
        QTest.keyClick(c.editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
        self.assertIs(w.current, a)
        w.tabs.setCurrentWidget(b)
        cursor = b.editor.textCursor()
        cursor.setPosition(3)
        b.editor.setTextCursor(cursor)
        index = w.tabs.currentIndex()
        w.close_tab(index)
        QTest.keyClick(w.editor, Qt.Key.Key_T,
                       Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(self.root / 'b.py', w.current.path)
        self.assertEqual(3, w.editor.textCursor().position())
        self.assertEqual(index, w.tabs.currentIndex())

    def test_terminal_caret_tracks_vt_cursor_and_visibility(self):
        w = self.window
        w.show_terminal()
        terminal = w.terminal
        self.wait(lambda: terminal.ready and bool(terminal.view.toPlainText().strip()))
        view = terminal.view
        self.wait(view.hasFocus)
        terminal.clear()
        terminal.stream.feed('A界B\x1b[D')
        terminal.render()
        self.assertEqual(2, view.terminal_cursor.position())
        painted = view.viewport().grab().toImage()
        terminal.stream.feed('\x1b[?25l')
        terminal.render()
        self.assertIsNone(view.terminal_cursor)
        self.assertNotEqual(painted, view.viewport().grab().toImage())
        terminal.stream.feed('\x1b[?25h')
        terminal.render()
        self.assertEqual(painted, view.viewport().grab().toImage())

    def test_recent_projects_pin_and_restore_from_palette(self):
        from atelier.projects.recent import RecentProjects
        from atelier.ui.palette import CommandPalette
        from atelier.ui.recent_projects import RecentProjectsDialog
        w = self.window
        original = self.root / 'first-recent-project'
        other = self.root / 'second-recent-project'
        original.mkdir()
        other.mkdir()
        path = original / 'restored.py'
        path.write_text('value = 12\n', encoding='utf-8')
        w.set_project(original)
        w.open_path(path)
        dialog = RecentProjectsDialog(w)
        self.assertEqual(str(original), dialog.current_record()['path'])
        dialog.pin_button.click()
        self.assertTrue(dialog.current_record()['pinned'])
        w.set_project(other)
        records = RecentProjects(w.settings).entries()
        self.assertEqual(str(original), records[0]['path'])
        self.assertTrue(records[0]['pinned'])
        palette = CommandPalette(w)
        palette.filter('first-recent-project')
        self.assertEqual(1, palette.listing.count())
        palette.execute()
        self.assertEqual(original, w.root)
        self.assertEqual(path, w.current.path)
        self.assertEqual('value = 12\n', w.current.editor.toPlainText())
        dialog.reload(str(original))
        dialog.pin_button.click()
        self.assertFalse(dialog.current_record()['pinned'])
        dialog.forget_button.click()
        self.assertTrue(original.is_dir())
        self.assertNotIn(str(original), [record['path'] for record in w.recent_projects.entries()])

    def test_project_switch_restores_split_session_and_closed_breakpoints(self):
        w = self.window
        path = self.root / 'workspace.py'
        doc = self.file(path.name, 'value = 1\nprint(value)\n')
        closed = self.file('closed.py', 'value = 2\n')
        w.toggle_breakpoint(closed, 1)
        closed.breakpoint_conditions[1] = 'value == 2'
        w.close_tab(w.tabs.indexOf(closed))
        w.tabs.setCurrentWidget(doc)
        w.toggle_split()
        for view, position in zip(doc.editors, (2, 8)):
            cursor = view.textCursor()
            cursor.setPosition(position)
            view.setTextCursor(cursor)
        doc.active_editor = doc.editors[1]
        doc.editor.appendPlainText('# local change')
        w.autorecovery_enabled = False
        w.restore_enabled = False
        other = self.root / 'other'
        other.mkdir()
        w.set_project(other)
        self.assertFalse(w.closed_breakpoints)
        self.assertTrue(all(tab.path is None for tab in w.documents))
        w.set_project(self.root)
        restored = w.current
        self.assertEqual(path, restored.path)
        self.assertEqual([2, 8], [view.textCursor().position() for view in restored.editors])
        self.assertIs(restored.editors[1], restored.editor)
        self.assertIn('# local change', restored.editor.toPlainText())
        self.assertTrue(restored.editor.document().isModified())
        self.assertFalse(restored.external_pending)
        self.assertEqual({1: 'value == 2'}, w.closed_breakpoints[str(closed.path)])
        w.show_breakpoints()
        panel = w.breakpoint_panel
        self.assertEqual(1, panel.tree.topLevelItemCount())
        self.assertEqual('value == 2', panel.tree.topLevelItem(0).text(2))
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
        panel.navigate()
        self.assertEqual(closed.path, w.current.path)
        self.assertEqual({1: 'value == 2'}, w.current.breakpoint_conditions)
        panel.close()

    @unittest.skipUnless(shutil.which('git'), 'Git not installed')
    def test_git_init_seeds_python_ignore_without_changing_existing_rules(self):
        w = self.window
        path = self.root / '.gitignore'
        existing = b'# User rules\r\nlocal.txt\r\n!dist/\r\n'
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            w.git_init()
            self.wait(lambda: path.is_file() and not w.processes)
            self.assertIn(b'__pycache__/', path.read_bytes())
            path.write_bytes(existing)
            doc = w.open_path(path)
            doc.editor.appendPlainText('unsaved-rule')
            w.git_init()
            self.wait(lambda: b'__pycache__/' in path.read_bytes() and not w.processes)
            merged = path.read_bytes()
            self.assertTrue(merged.endswith(existing))
            self.assertIn(b'.venv/\r\n', merged)
            self.assertNotIn(b'unsaved-rule', merged)
            self.assertIn('unsaved-rule', doc.editor.toPlainText())
            self.assertIn('__pycache__/', doc.editor.toPlainText())
            self.assertTrue(doc.editor.document().isModified())
            w.git_init()
            self.wait(lambda: not w.processes)
        self.assertEqual(merged, path.read_bytes())
        check = subprocess.run(['git', 'check-ignore', '__pycache__/sample.pyc', 'dist/keep.txt'],
                               cwd=self.root, capture_output=True, check=True)
        self.assertEqual([b'__pycache__/sample.pyc'], check.stdout.splitlines())

    def test_test_panel_discovery_execution_and_navigation(self):
        w = self.window
        self.file('test_sample.py', 'def test_ok():\n    assert 6 * 7 == 42\n\ndef test_failure():\n    assert 1 == 2\n')
        w.show_tests()
        w.test_panel.start('collect')
        self.wait(lambda: w.test_panel.process.state() == QProcess.ProcessState.NotRunning and len(w.test_panel.items) == 2)
        w.test_panel.start('run')
        self.wait(lambda: w.test_panel.process.state() == QProcess.ProcessState.NotRunning and len(w.test_panel.results) == 2)
        self.assertEqual('passed', w.test_panel.results['test_sample.py::test_ok']['outcome'])
        self.assertEqual('failed', w.test_panel.results['test_sample.py::test_failure']['outcome'])
        item = w.test_panel.items['test_sample.py::test_failure']
        w.test_panel.open_result(item)
        self.assertEqual('test_sample.py', w.current.path.name)
        self.assertEqual(4, w.editor.textCursor().blockNumber())
        w.test_panel.tree.setCurrentItem(w.test_panel.items['test_sample.py::test_ok'])
        w.test_panel.run_selected()
        self.wait(lambda: w.test_panel.process.state() == QProcess.ProcessState.NotRunning and len(w.test_panel.results) == 1)

    def test_conditional_debugger_watch_and_variable_edit(self):
        w = self.window
        doc = self.file('condition.py', 'for i in range(4):\n    value = i\nprint(value)\n')
        w.toggle_breakpoint(doc, 2)
        doc.breakpoint_conditions[2] = 'i == 2'
        w.watch_expressions = ['i * 10']
        w.start_debug()
        self.wait(lambda: w.debugger.thread is not None, timeout=35)
        self.wait(lambda: any(w.variables_tree.topLevelItem(i).text(0) == 'i' for i in range(w.variables_tree.topLevelItemCount())))
        item = next(w.variables_tree.topLevelItem(i) for i in range(w.variables_tree.topLevelItemCount()) if w.variables_tree.topLevelItem(i).text(0) == 'i')
        self.assertEqual('2', item.text(1))
        self.wait(lambda: w.watch_tree.topLevelItemCount() and w.watch_tree.topLevelItem(0).text(1) == '20')
        with patch.object(QInputDialog, 'getText', return_value=('7', True)):
            w.edit_variable(item)
        self.wait(lambda: w.watch_tree.topLevelItem(0).text(1) == '70')
        w.debugger.action('continue')
        self.wait(lambda: not w.debugger.active)

    @unittest.skipUnless(shutil.which('git'), 'Git not installed')
    def test_git_init_and_tree_colors(self):
        w = self.window
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            w.git_init()
        self.wait(lambda: (self.root / '.git').exists())
        doc = self.file('colored.py', 'value = 1\n')
        w.refresh_git()
        self.wait(lambda: str(doc.path) in w.fs.git_states)
        index = w.fs.index(str(doc.path))
        self.assertEqual('#94a3b8', w.fs.data(index, Qt.ItemDataRole.ForegroundRole).name())
        w.git_stage()
        self.wait(lambda: w.fs.git_states.get(str(doc.path)) == 'A ')
        self.assertEqual('#34d399', w.fs.data(index, Qt.ItemDataRole.ForegroundRole).name())
        doc.editor.setPlainText('value = 2\n')
        w.save(doc=doc, allow_format=False)
        self.wait(lambda: w.fs.git_states.get(str(doc.path)) == 'AM')
        self.assertEqual('#fbbf24', w.fs.data(index, Qt.ItemDataRole.ForegroundRole).name())


if __name__ == '__main__':
    unittest.main(verbosity=2)
