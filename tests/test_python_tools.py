import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json, unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QInputDialog,QMessageBox
from PySide6.QtTest import QTest
import tests.test_application as base


class V7Integration(unittest.TestCase):
    setUpClass=classmethod(base.StudioIntegration.setUpClass.__func__)
    setUp=base.StudioIntegration.setUp;tearDown=base.StudioIntegration.tearDown
    wait=base.StudioIntegration.wait;file=base.StudioIntegration.file

    def test_python_tools_signature_history_and_profiles(self):
        from atelier.languages.python_tools import missing_imports,insert_import
        w=self.window
        self.assertIn(('Path','from pathlib import Path'),missing_imports(self.root,'Path("x")\n'))
        text=insert_import('"""doc"""\nfrom __future__ import annotations\nPath("x")\n','from pathlib import Path')
        self.assertLess(text.index('__future__'),text.index('from pathlib'))
        doc=self.file('refactor.py','import os\nimport sys\nprint(sys.version)\n')
        with patch.object(w,'review_change',return_value=True):w.python_refactor('imports')
        self.assertNotIn('import os',doc.editor.toPlainText(),self.messages)
        doc.editor.setPlainText('value = (1 + 2) * 3\nprint(value)\n')
        source=doc.editor.toPlainText();cursor=doc.editor.textCursor();cursor.setPosition(source.index('1 + 2'));cursor.setPosition(source.index('1 + 2')+5,QTextCursor.MoveMode.KeepAnchor);doc.editor.setTextCursor(cursor)
        with patch.object(w,'review_change',return_value=True),patch.object(QInputDialog,'getText',return_value=('subtotal',True)):w.python_refactor('variable')
        self.assertIn('subtotal',doc.editor.toPlainText(),self.messages)
        original=doc.editor.toPlainText();doc.editor.appendPlainText('# history');w.save(doc=doc,allow_format=False)
        versions=w.file_history.entries(doc.path)
        self.assertTrue(any(w.file_history.read(doc.path,entry)==original for entry in versions))
        doc.editor.setPlainText('def greet(name):\n    message = "Hi " + name\n    print(message)\n')
        source=doc.editor.toPlainText();cursor=doc.editor.textCursor();cursor.setPosition(source.index('    message'));cursor.setPosition(len(source),QTextCursor.MoveMode.KeepAnchor);doc.editor.setTextCursor(cursor)
        with patch.object(w,'review_change',return_value=True),patch.object(QInputDialog,'getText',return_value=('show_message',True)):w.python_refactor('method')
        self.assertIn('def show_message',doc.editor.toPlainText(),self.messages)
        popup=doc.editor.signature_popup
        popup.update_help({'activeParameter':1,'signatures':[{'label':'f(first, second)','parameters':[{'label':'first'},{'label':'second'}]},{'label':'f(value)','parameters':[{'label':'value'}]}]})
        self.assertIn('>second</b>',popup.label.text());popup.cycle(1);self.assertEqual(1,popup.index);popup.hide()
        program=self.file('profile.py','import os,sys\nprint(os.getenv("MODE"),sys.argv[1],os.getcwd())\n')
        cwd=self.root/'cwd';cwd.mkdir()
        key=w.project_profiles.key(w.root)
        w.settings.setValue(key+'run_profiles',json.dumps({'test':{'file':str(program.path),'cwd':str(cwd),'args':'argument','env':{'MODE':'profile-ok'}}}))
        w.settings.setValue(key+'active_profile','test')
        w.run_file();self.wait(lambda:'profile-ok argument' in w.output.toPlainText())
        self.assertIn(str(cwd),w.output.toPlainText())
        self.assertEqual((str(program.path),1),w.output.location(f'  File "{program.path}", line 2, in <module>'))

    def test_tree_multi_shortcut_height_and_terminal_stability(self):
        from atelier.ui.settings import SettingsDialog
        w=self.window
        one=self.file('one.py','a=1\n');two=self.file('two.py','b=2\n')
        for doc in (one,two):
            index=w.fs.index(str(doc.path));w.tree.selectionModel().select(index,QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)
        self.assertEqual({one.path,two.path},set(w.selected_tree_paths()))
        with patch('send2trash.send2trash',side_effect=lambda paths:[Path(path).unlink() for path in paths]) as trash,patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(w.tree_delete_many([one.path,two.path]));self.assertEqual(2,len(trash.call_args.args[0]))
        settings=SettingsDialog(w);self.assertGreaterEqual(next(iter(settings.keys.values())).minimumHeight(),38);settings.reject()
        w.show_terminal();self.wait(lambda:w.terminal.ready)
        pid=w.terminal.process.processId();QTest.qWait(700)
        w.append_output('background output\n')
        self.assertIs(w.terminal_tabs,w.bottom.currentWidget(),'Background output must not steal the terminal tab')
        for _ in range(20):w.terminal.resize_terminal()
        QTest.qWait(500);rendered=w.terminal.render_count
        QTest.qWait(800)
        self.assertEqual(pid,w.terminal.process.processId());self.assertLessEqual(w.terminal.render_count-rendered,1)
        chunks=[];w.terminal.received.connect(chunks.append);w.terminal.send_input('echo TERMINAL_STABLE\r')
        self.wait(lambda:'TERMINAL_STABLE' in ''.join(chunks))
        w.terminal.shutdown()


if __name__=='__main__':unittest.main(verbosity=2)
