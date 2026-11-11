import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import shutil,subprocess,unittest
from unittest.mock import patch
from PySide6.QtCore import QProcess
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QInputDialog
import tests.test_application as base


class V6Integration(unittest.TestCase):
    setUpClass=classmethod(base.StudioIntegration.setUpClass.__func__)
    setUp=base.StudioIntegration.setUp
    tearDown=base.StudioIntegration.tearDown
    wait=base.StudioIntegration.wait
    file=base.StudioIntegration.file

    def test_multi_regex_quick_open_settings_and_icon(self):
        from atelier.ui.quick_open import QuickOpen
        from atelier.ui.settings import SettingsDialog
        w=self.window;editor=w.editor
        editor.setPlainText('item item itemize')
        editor.moveCursor(QTextCursor.MoveOperation.Start)
        editor.select_next_occurrence();editor.select_next_occurrence()
        editor.multi_edit('value')
        self.assertEqual('value value itemize',editor.toPlainText())
        editor.undo();self.assertEqual('item item itemize',editor.toPlainText())
        editor.setPlainText('foo1 foo22 foobar')
        w.find_text.setText(r'foo(\d+)');w.find_regex.setChecked(True);w.replace_text.setText(r'bar\1')
        w.replace_all();self.assertEqual('bar1 bar22 foobar',editor.toPlainText())
        self.file('alpha_widget.py','value=1\n')
        self.file('notes.md','# note\n')
        picker=QuickOpen(w)
        self.wait(lambda:bool(picker.paths))
        picker.query.setText('awpy')
        self.assertEqual('alpha_widget.py',picker.listing.item(0).text())
        picker.open_selected()
        settings=SettingsDialog(w)
        settings.indent.setValue(2);settings.guide.setChecked(False)
        settings.save()
        self.assertEqual(2,w.tab_width,self.messages)
        self.assertFalse(w.editor.show_active_guide)
        self.assertFalse(w.windowIcon().isNull())
        w.project_query.setText(r'value\s*=');w.project_regex.setChecked(True);w.project_globs.setText('*.py')
        w.search_project();self.wait(lambda:w.search_results.count()==1)

    def test_quick_fix_and_coverage(self):
        w=self.window
        doc=self.file('calc.py','def calculate(value):\n    if value:\n        return 1\n    return 0\n')
        self.file('test_calc.py','from calc import calculate\ndef test_value():\n    assert calculate(True)==1\n')
        w.coverage_enabled=True
        w.test_panel.start('run')
        self.wait(lambda:w.test_panel.process.state()==QProcess.ProcessState.NotRunning and bool(w.coverage_data))
        self.assertIn(4,w.coverage_data[str(doc.path)])
        self.assertFalse(w.coverage_data[str(doc.path)][4])
        self.assertTrue(doc.editor.coverage_lines)
        w.tabs.setCurrentWidget(doc)
        edit={'changes':{doc.uri:[{'range':{'start':{'line':0,'character':0},'end':{'line':0,'character':0}},'newText':'# fixed\n'}]}}
        def request(method,params,callback):
            self.assertEqual('textDocument/codeAction',method)
            callback([{'title':'Fix example','edit':edit}])
        with patch.object(w.lsp,'request',side_effect=request),patch.object(QInputDialog,'getItem',return_value=('Fix example',True)):
            w.code_actions()
        self.assertTrue(doc.editor.toPlainText().startswith('# fixed'))

    @unittest.skipUnless(shutil.which('git'),'Git unavailable')
    def test_side_by_side_stage_and_unstage(self):
        from atelier.git.compare import GitCompare
        w=self.window
        def git(*args):return subprocess.run(['git','-C',str(self.root),*args],capture_output=True,check=True)
        git('init');git('config','user.name','Test');git('config','user.email','test@example.invalid')
        doc=self.file('diff.py','value = 1\n')
        git('add','diff.py');git('commit','-m','base')
        doc.editor.setPlainText('value = 2\n');w.save(doc=doc,allow_format=False)
        dialog=GitCompare(w,doc.path)
        self.wait(lambda:dialog.groups.count()==1)
        self.assertIn('value = 1',dialog.left.toPlainText())
        dialog.apply_group()
        self.wait(lambda:b'value = 2' in git('show',':diff.py').stdout)
        dialog.mode.setCurrentIndex(1)
        self.wait(lambda:dialog.groups.count()==1)
        dialog.apply_group()
        self.wait(lambda:b'value = 1' in git('show',':diff.py').stdout)
        self.assertIn('value = 2',doc.path.read_text())
        dialog.reject()


if __name__=='__main__':unittest.main(verbosity=2)
