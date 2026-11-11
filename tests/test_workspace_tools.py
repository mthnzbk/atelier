import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import shutil
import subprocess
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtTest import QTest
import tests.test_application as base


class V5Integration(unittest.TestCase):
    setUpClass = classmethod(base.StudioIntegration.setUpClass.__func__)
    setUp = base.StudioIntegration.setUp
    tearDown = base.StudioIntegration.tearDown
    wait = base.StudioIntegration.wait
    file = base.StudioIntegration.file
    request = base.StudioIntegration.request

    def test_incremental_highlighting_minimap_and_monitor(self):
        from atelier.editor.widget import Editor
        from atelier.ui.icons import NAMES, qta
        for name in NAMES.values():
            self.assertFalse(qta.icon('mdi6.' + name).isNull(), name)
        editor = Editor()
        editor.resize(900, 600)
        editor.show()
        started = time.perf_counter()
        editor.setPlainText('\n'.join(f'value_{i} = {i}' for i in range(20000)))
        self.app.processEvents()
        loaded = time.perf_counter()-started
        editor.highlighter.highlighted_blocks = 0
        cursor = editor.textCursor()
        cursor.setPosition(5)
        editor.setTextCursor(cursor)
        editor.insertPlainText('x')
        QTest.qWait(300)
        self.assertLess(editor.highlighter.highlighted_blocks, 30, 'A single-line edit must not lex the full document')
        editor.minimap.grab()
        key = editor.minimap.cache.cacheKey()
        editor.verticalScrollBar().setValue(1000)
        editor.minimap.grab()
        self.assertEqual(key, editor.minimap.cache.cacheKey())
        print(f'PERF: 20000 lines load={loaded:.3f}s; edit lexed={editor.highlighter.highlighted_blocks} blocks', flush=True)
        editor.close()
        doc = self.file('monitor.py', 'value = 1\n')
        with patch('atelier.storage.monitor.fingerprint') as fingerprint:
            self.window.file_monitor.check()
            self.window.file_monitor.check()
            fingerprint.assert_not_called()
        doc.editor.setPlainText('def outer():\n    if True:\n        return 1\n')
        doc.editor.structure.rebuild()
        self.assertEqual([0, 4], doc.editor.structure.guide_columns[2])
        self.assertFalse(doc.editor.gutter.grab().isNull())

    def test_project_profiles_references_symbols_and_history(self):
        w = self.window
        one, two = self.root / 'one', self.root / 'two'
        one.mkdir()
        two.mkdir()
        w.set_project(one)
        w.run_args, w.test_args = '--one', '-k one'
        w.set_project(two)
        self.assertEqual('', w.run_args)
        w.run_args, w.test_args = '--two', '-k two'
        w.set_project(one)
        self.assertEqual(('--one', '-k one'), (w.run_args, w.test_args))
        self.wait(lambda: w.lsp.initialized)
        path = one / 'navigate.py'
        path.write_text('def greet(name):\n    return name\n\ngreet("Ada")\ngreet("Bob")\n')
        doc = w.open_path(path)
        w.goto(doc, {'line': 3, 'character': 2})
        w.references()
        self.wait(lambda: w.navigation_results.count() >= 3)
        w.document_symbols()
        self.wait(lambda: w.navigation_results.count() and 'greet' in w.navigation_results.item(0).text())
        w.open_navigation_result(w.navigation_results.item(0))
        self.assertEqual(0, w.editor.textCursor().blockNumber())
        w.navigate_history(-1)
        self.assertEqual(3, w.editor.textCursor().blockNumber())
        w.navigate_history(1)
        self.assertEqual(0, w.editor.textCursor().blockNumber())
        module = one / 'library.py'
        module.write_text('value = 1\n\ndef calculate():\n    return value\n')
        caller = one / 'caller.py'
        caller.write_text('from library import calculate\ncalculate()\n')
        calling = w.open_path(caller)
        w.goto(calling, {'line': 1, 'character': 2})
        w.definition()
        self.wait(lambda: w.current.path == module)
        self.assertEqual(2, w.editor.textCursor().blockNumber())
        w.navigate_history(-1)
        self.assertEqual(caller, w.current.path)
        self.assertEqual(1, w.editor.textCursor().blockNumber())

    def test_tree_create_rename_refactor_and_trash(self):
        w = self.window
        folder = w.tree_create(self.root, folder=True, name='package')
        created = w.tree_create(folder, name='notes.md')
        self.assertTrue(created.exists())
        renamed = w.tree_rename(created, name='guide.md')
        self.assertEqual(renamed, w.current.path)
        module = self.file('old_module.py', 'def answer():\n    return 42\n')
        consumer = self.file('consumer.py', 'from old_module import answer\nprint(answer())\n')
        with patch.object(w, 'review_change', return_value=True):
            new_path = w.tree_rename(module.path, refactor=True, name='new_module.py')
        self.assertTrue(new_path and new_path.exists(), self.messages)
        self.assertIn('from new_module import answer', consumer.path.read_text())
        self.assertEqual('new_module.py', module.path.name)
        with patch.object(base.QMessageBox, 'question', return_value=base.QMessageBox.StandardButton.Yes), \
             patch('send2trash.send2trash', side_effect=lambda path: Path(path).unlink()) as trash:
            self.assertTrue(w.tree_delete(renamed))
            trash.assert_called_once_with(str(renamed))
        self.assertFalse(renamed.exists())
        with self.assertRaises(ValueError):
            w.checked_tree_path(self.root.parent / 'outside.py')

    @unittest.skipUnless(shutil.which('git'), 'Git not installed')
    def test_partial_git_preserves_unselected_lines(self):
        w = self.window
        def git(*args):
            return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True)
        git('init')
        git('config', 'user.name', 'Test')
        git('config', 'user.email', 'test@example.invalid')
        doc = self.file('partial file.py', 'a = 1\nb = 2\nc = 3\nd = 4\n')
        git('add', 'partial file.py')
        git('commit', '-m', 'base')
        changed = 'a = 10\nb = 2\nc = 3\nd = 40\n'
        doc.editor.setPlainText(changed)
        w.save(doc=doc, allow_format=False)
        applied = []
        w.prepare_partial_stage(doc.path, 0, 0, review=False, after=lambda: applied.append(True))
        self.wait(lambda: bool(applied))
        staged = git('show', ':partial file.py').stdout.decode()
        self.assertIn('a = 10', staged)
        self.assertIn('d = 4\n', staged)
        self.assertNotIn('d = 40', staged)
        self.assertEqual(changed, doc.path.read_text())
        applied.clear()
        w.prepare_partial_stage(doc.path, 3, 3, review=False, after=lambda: applied.append(True))
        self.wait(lambda: bool(applied))
        self.assertIn(b'd = 40', git('show', ':partial file.py').stdout)

    def test_update_package_validation_and_corruption(self):
        from atelier.runtime.updates import create_manifest, stage_package
        payload = self.root / 'payload'
        (payload / 'app').mkdir(parents=True)
        (payload / 'runtime').mkdir()
        (payload / 'app/main.py').write_text('print("new")\n')
        (payload / 'runtime/python.exe').write_bytes(b'python')
        (payload / 'runtime/pythonw.exe').write_bytes(b'pythonw')
        create_manifest(payload, '5.0.0')
        archive = self.root / 'valid.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            for path in payload.rglob('*'):
                if path.is_file():
                    zipped.write(path, path.relative_to(payload).as_posix())
        manifest = stage_package(archive, self.root / 'staged')
        self.assertEqual('5.0.0', manifest['version'])
        bad = self.root / 'bad.zip'
        with zipfile.ZipFile(archive) as original, zipfile.ZipFile(bad, 'w') as zipped:
            for name in original.namelist():
                zipped.writestr(name, b'corrupt' if name == 'app/main.py' else original.read(name))
        with self.assertRaises(ValueError):
            stage_package(bad, self.root / 'bad-stage')
        malicious = self.root / 'unsafe.zip'
        with zipfile.ZipFile(malicious, 'w') as zipped:
            zipped.writestr('../escape.txt', 'bad')
        with self.assertRaises(ValueError):
            stage_package(malicious, self.root / 'unsafe-stage')
        self.assertFalse((self.root / 'escape.txt').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows update helper')
    def test_update_apply_backup_and_rollback(self):
        script = Path(__file__).resolve().parents[1] / 'tools' / 'windows' / 'apply_update.ps1'
        def skeleton(root, value):
            (root / 'app').mkdir(parents=True)
            (root / 'runtime').mkdir()
            (root / 'app/main.py').write_text(value)
            (root / 'runtime/python.exe').write_text(value)
            (root / 'manifest.json').write_text('{}')
        installed, payload = self.root / 'installed', self.root / 'update'
        skeleton(installed, 'old')
        skeleton(payload, 'new')
        settings = self.root / 'user-settings.ini'
        settings.write_text('preserved')
        def apply(target, staged):
            subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                '-ParentProcessId', '2147483647', '-InstallRoot', str(target), '-Payload', str(staged), '-NoLaunch'],
                capture_output=True, check=True)
        apply(installed, payload)
        self.assertEqual('new', (installed / 'app/main.py').read_text())
        backup = next(installed.glob('.atelier-backup-*'))
        self.assertEqual('old', (backup / 'app/main.py').read_text())
        self.assertEqual('preserved', settings.read_text())
        failing, broken = self.root / 'rollback', self.root / 'broken'
        skeleton(failing, 'original')
        (broken / 'app').mkdir(parents=True)
        (broken / 'app/main.py').write_text('partial')
        (broken / 'manifest.json').write_text('{}')
        apply(failing, broken)
        self.assertEqual('original', (failing / 'app/main.py').read_text())
        self.assertEqual('original', (failing / 'runtime/python.exe').read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
