"""New daily workflows and regression scenarios, exercised from source."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QProcess
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QInputDialog, QToolTip

import tests.test_application as base
from atelier.git.merge import MergeDialog, parse_conflicts
from atelier.ui.symbol_search import SymbolSearch


class V9Integration(unittest.TestCase):
    setUpClass = classmethod(base.StudioIntegration.setUpClass.__func__)
    setUp = base.StudioIntegration.setUp
    tearDown = base.StudioIntegration.tearDown
    wait = base.StudioIntegration.wait
    file = base.StudioIntegration.file

    @unittest.skipUnless(shutil.which('git'), 'Git not installed')
    def test_real_git_merge_conflicts_and_stage(self):
        w = self.window
        def git(*args, check=True):
            return subprocess.run(['git', *args], cwd=self.root, check=check, capture_output=True, text=True, encoding='utf-8')
        git('init', '-b', 'main'); git('config', 'user.email', 'test@example.invalid'); git('config', 'user.name', 'Test')
        git('config', 'merge.conflictStyle', 'diff3')
        path = self.root / 'çakışma dosyası.txt'
        common = ''.join(f'line {i}\n' for i in range(12))
        path.write_text('start\nbase 1\n' + common + 'base 2\nend\n', encoding='utf-8')
        git('add', '--', path.name); git('commit', '-m', 'base'); git('switch', '-c', 'incoming')
        path.write_text('start\ntheirs 1\n' + common + 'theirs 2\nend\n', encoding='utf-8')
        git('commit', '-am', 'incoming'); git('switch', 'main')
        path.write_text('start\nours 1\n' + common + 'ours 2\nend\n', encoding='utf-8')
        git('commit', '-am', 'local'); self.assertNotEqual(0, git('merge', 'incoming', check=False).returncode)
        original = path.read_text(encoding='utf-8')
        self.assertEqual(2, len([part for part in parse_conflicts(original) if isinstance(part, dict)]))
        with self.assertRaises(ValueError):
            parse_conflicts('<<<<<<< HEAD\nmissing end\n')
        inspected = []
        expected = 'start\nours 1\n' + common + 'ours 2\ntheirs 2\nend\n'
        def resolve(dialog):
            dialog.apply(stage=True)  # unresolved result must not be written/staged
            inspected.append(path.read_text(encoding='utf-8') == original)
            dialog.choose('ours'); dialog.choose('both')
            inspected.append(dialog.result.toPlainText() == expected)
            with patch.object(w, 'save', return_value=False):
                dialog.apply(stage=True)
            inspected.append(dialog.doc.editor.toPlainText() == original)
            dialog.apply(stage=True)
            return 1
        with patch.object(MergeDialog, 'exec', resolve):
            w.resolve_conflicts(path)
            self.wait(lambda: len(inspected) == 3)
        self.assertEqual([True, True, True], inspected)
        self.wait(lambda: not w.processes)
        self.assertEqual(expected, path.read_text(encoding='utf-8'))
        self.assertEqual('', git('ls-files', '-u').stdout)
        self.assertEqual(expected, git('show', ':' + path.name).stdout)

    def test_project_save_actions_and_stale_edits(self):
        w = self.window
        w.format_on_save = w.save_imports = w.save_trim = w.save_final_newline = True
        w.format_web_on_save = True
        w.store_save_actions()
        self.assertTrue(all(w.project_profiles.load_save_actions(w.root).values()))
        self.assertFalse(any(w.project_profiles.load_save_actions(w.root / 'other').values()))
        doc = self.file('save.py', 'import sys\nimport os\n\nvalue=1   \nprint(os.name,sys.version)')
        self.assertTrue(w.save(doc=doc))
        self.wait(lambda: not w.save_workers)
        saved = doc.path.read_text(encoding='utf-8')
        self.assertIn('import os\nimport sys', saved, w.statusBar().currentMessage())
        self.assertIn('value = 1\n', saved)
        self.assertTrue(saved.endswith('\n'))
        self.assertEqual(saved, doc.editor.toPlainText())
        self.assertFalse(doc.editor.document().isModified())

        w.format_on_save = w.save_imports = False
        doc.editor.setPlainText('value = """spaces  \nsecond   \n"""\nprint(value)   ')
        self.assertTrue(w.save(doc=doc))
        self.wait(lambda: not w.save_workers)
        self.assertIn('spaces  \nsecond   \n', doc.saved_text)
        self.assertTrue(doc.saved_text.endswith('print(value)\n'))

        doc.editor.setPlainText('value=2   ')
        self.assertTrue(w.save(doc=doc))
        doc.editor.appendPlainText('# continued editing')
        self.wait(lambda: not w.save_workers)
        self.assertEqual('value=2   ', doc.path.read_text(encoding='utf-8'))
        self.assertTrue(doc.editor.toPlainText().endswith('# continued editing'))
        self.assertTrue(doc.editor.document().isModified())
        doc.editor.document().setModified(False)

        doc.editor.setPlainText('value=3   ')
        self.assertTrue(w.save(doc=doc))
        doc.path.write_text('changed outside\n', encoding='utf-8')
        self.wait(lambda: not w.save_workers)
        self.assertEqual('changed outside\n', doc.path.read_text(encoding='utf-8'))
        notes = [self.file(f'note_{i}.txt', 'initial\n') for i in range(4)]
        for note in notes:
            note.editor.setPlainText('queued   ')
            note.editor.document().setModified(True)
        self.assertTrue(w.save_all())
        self.wait(lambda: not w.save_workers and not w.save_queue)
        self.assertTrue(all(note.path.read_text(encoding='utf-8') == 'queued\n' for note in notes))

    def test_symbols_cancelled_search_and_large_file(self):
        w = self.window
        doc = self.file('entities.py', 'class Entity:\n    def old_name(self):\n        return 1\n')
        doc.editor.setPlainText('class Entity:\n    async def current_name(self):\n        return 1\n')
        self.file('invalid.py', 'def broken(\n')
        env = self.root / 'custom-env'; env.mkdir()
        (env / 'pyvenv.cfg').write_text('home = fake\n', encoding='utf-8')
        (env / 'hidden.py').write_text('def hidden(): pass\n', encoding='utf-8')
        symbols = SymbolSearch(w)
        self.wait(lambda: symbols.worker.completed)
        symbols.query.setText('current_name')
        self.wait(lambda: symbols.listing.count() == 1)
        self.assertEqual({'Entity', 'Entity.current_name'}, {row['name'] for row in symbols.rows})
        symbols.open_selected()
        self.assertIs(doc, w.current)
        self.assertEqual(1, doc.editor.textCursor().blockNumber())
        doc.editor.document().setModified(False)

        # This regex stalls a backtracking engine, so a process must be killable.
        (self.root / 'regex.txt').write_text('a' * 60 + '!\n', encoding='utf-8')
        w.project_regex.setChecked(True); w.project_query.setText('^(a+)+$'); w.search_project()
        self.wait(lambda: bool(w.workers) and w.workers[0].isRunning())
        QTest.qWait(400)
        w.cancel_search()
        self.wait(lambda: not w.workers, timeout=5)
        self.assertIn('durduruldu', w.search_label.text())
        w.project_regex.setChecked(False); w.project_query.setText('old_name'); w.search_project()
        self.wait(lambda: w.search_results.count() == 1)

        large = self.file('large.py', '# ' + 'a' * 80 + '\n' + 'value = 1\n' * 22000)
        self.assertTrue(large.large_file); self.assertIsNone(large.synced)
        self.assertIsNone(large.editor.highlighter.document())
        self.assertFalse(large.editor.minimap_enabled)
        self.assertFalse(large.editor.structure.enabled)
        self.assertIn('Büyük dosya', w.position_label.text())
        w.toggle_split(); w.apply_theme(); w.toggle_minimap()
        self.assertTrue(all(not view.minimap_enabled and view.highlighter.document() is None for view in large.editors))
        large.editor.appendPlainText('print(value)')
        self.assertTrue(w.save(doc=large))
        self.assertFalse(w.save_workers)
        self.assertTrue(large.path.read_text(encoding='utf-8').endswith('print(value)'))

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing errors')
    def test_atomic_save_retries_transient_sharing_error(self):
        w = self.window
        doc = self.file('locked.py', 'value = 1\n')
        doc.editor.setPlainText('value = 2\n')
        real_replace, attempts = os.replace, []
        def briefly_locked(source, target):
            if Path(target) == doc.path:
                attempts.append(target)
                if len(attempts) == 1:
                    raise PermissionError(13, 'test lock', str(target), 32)
            return real_replace(source, target)
        with patch('atelier.app.features.files.os.replace', side_effect=briefly_locked):
            self.assertTrue(w.save(doc=doc, allow_format=False))
        self.assertEqual(2, len(attempts))
        self.assertEqual('value = 2\n', doc.path.read_text(encoding='utf-8'))

        doc.editor.setPlainText('value = 3\n')
        doc.editor.document().setModified(True)
        def externally_changed(source, target):
            if Path(target) == doc.path:
                doc.path.write_text('external = True\n', encoding='utf-8')
                raise PermissionError(13, 'test lock', str(target), 5)
            return real_replace(source, target)
        with patch('atelier.app.features.files.os.replace', side_effect=externally_changed):
            self.assertFalse(w.save(doc=doc, allow_format=False))
        self.assertEqual('external = True\n', doc.path.read_text(encoding='utf-8'))
        self.assertEqual('value = 3\n', doc.editor.toPlainText())
        self.assertTrue(doc.editor.document().isModified())
        self.assertFalse(list(self.root.glob('locked.py.*.tmp')))

    def test_debug_hover_and_breakpoint_panel(self):
        w = self.window
        doc = self.file('hover_debug.py', 'number = 40\nnumber += 2\nprint(number)\n')
        w.toggle_breakpoint(doc, 2)
        w.show_breakpoints(); panel = w.breakpoint_panel
        self.assertEqual(1, panel.tree.topLevelItemCount())
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
        with patch.object(QInputDialog, 'getText', return_value=('number == 40', True)):
            panel.condition()
        self.assertEqual('number == 40', doc.breakpoint_conditions[2])
        panel.close()
        w.start_debug()
        self.wait(lambda: doc.editor.execution_line == 2 and w.debugger.frame_id is not None, timeout=35)
        cursor = QTextCursor(doc.editor.document().findBlockByNumber(1)); cursor.movePosition(QTextCursor.MoveOperation.Right, n=2)
        point = doc.editor.cursorRect(cursor).center(); doc.editor.hover_position = point
        with patch.object(QToolTip, 'showText') as tooltip:
            w.hover(doc, doc.editor, point)
            self.wait(lambda: tooltip.called)
            self.assertIn('number (int) = 40', tooltip.call_args.args[1])
        w.debugger.action('continue')
        self.wait(lambda: not w.debugger.active)
        self.assertIsNone(doc.editor.execution_line)
        self.assertIsNone(w.debugger.frame_id)
        panel.refresh(); panel.tree.topLevelItem(0).setSelected(True); panel.remove()
        self.assertFalse(doc.breakpoints)

    def test_stability_tab_lsp_external_file_and_terminal(self):
        w = self.window
        w.show_terminal(); self.wait(lambda: w.terminal.ready)
        pid = w.terminal.process.processId()
        chunks = []; w.terminal.received.connect(chunks.append)
        for index in range(8):
            doc = self.file(f'rapid_{index}.py', 'import os\nos.pa\n')
            w.toggle_split(); w.complete(doc)
            w.toggle_split(); w.close_tab(w.tabs.indexOf(doc))
            w.terminal.send_input(f'python -c "print(\'ATELIER-ENDURANCE-\' + str({index}))"\r')
            self.wait(lambda: f'ATELIER-ENDURANCE-{index}' in ''.join(chunks))
            w.bottom.setCurrentIndex(0); w.bottom.setCurrentWidget(w.terminal_tabs)
            w.append_output('background output\n'); w.terminal.resize_terminal()
            QTest.qWait(1500)
            self.assertEqual(pid, w.terminal.process.processId())
            self.assertIs(w.terminal_tabs, w.bottom.currentWidget())
        local = self.file('externally_removed.py', 'retained = True\n')
        local.path.unlink()
        self.wait(lambda: local.external_pending)
        self.assertIn('retained = True', local.editor.toPlainText())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(w.save(doc=local))
        self.assertFalse(local.path.exists())
        for _ in range(2):
            w.start_lsp(); self.wait(lambda: w.lsp.initialized)
        self.assertEqual(pid, w.terminal.process.processId())
        QTest.qWait(400); renders = w.terminal.render_count
        QTest.qWait(1000); self.assertEqual(renders, w.terminal.render_count)
        w.terminal.shutdown()
        self.assertEqual(QProcess.ProcessState.NotRunning, w.terminal.process.state())


if __name__ == '__main__':
    unittest.main()
