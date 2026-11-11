"""Offline checks using a real temporary venv and a tiny local wheel fixture."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
import zipfile
import subprocess
from unittest.mock import patch

from PySide6.QtCore import QProcess, QSettings
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
import tests.test_application as base
from atelier.projects.environments import PythonEnvironmentDialog, environment_python, package_spec, discover_pythons


class V8Integration(unittest.TestCase):
    setUpClass = classmethod(base.StudioIntegration.setUpClass.__func__)
    setUp = base.StudioIntegration.setUp
    tearDown = base.StudioIntegration.tearDown
    wait = base.StudioIntegration.wait
    file = base.StudioIntegration.file

    def idle(self, dialog):
        try:
            self.wait(lambda: dialog.operation is None, timeout=45)
        except AssertionError:
            self.fail(f'Operation: {dialog.operation}; state: {dialog.process.state()}; status: {dialog.status.text()}\n{dialog.log.toPlainText()}')

    def test_prepare_project_installs_and_selects_venv(self):
        from atelier.projects.environments import project_install_options

        wheel = self.root / 'atelier_setup-1.0-py3-none-any.whl'
        files = {
            'atelier_setup.py': 'VALUE = 42\n',
            'atelier_setup-1.0.dist-info/METADATA': 'Metadata-Version: 2.1\nName: atelier-setup\nVersion: 1.0\n',
            'atelier_setup-1.0.dist-info/WHEEL': 'Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
        }
        files['atelier_setup-1.0.dist-info/RECORD'] = ''.join(
            name + ',,\n' for name in [*files, 'atelier_setup-1.0.dist-info/RECORD'])
        with zipfile.ZipFile(wheel, 'w') as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        (self.root / 'requirements.txt').write_text(f'--no-index\n./{wheel.name}\n', encoding='utf-8')
        manifest = self.root / 'pyproject.toml'
        manifest.write_text('[project]\nname = "sample"\nversion = "1.0"\ndependencies = ["requests"]\n',
                            encoding='utf-8')
        options = project_install_options(self.root)
        self.assertEqual((['.'], 'requests'), options['pyproject.toml'])
        manifest.unlink()
        dialog = PythonEnvironmentDialog(self.window)
        try:
            self.idle(dialog)
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Cancel):
                dialog.prepare_project()
            self.assertFalse((self.root / '.venv').exists())
            with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok):
                dialog.prepare_project()
            self.idle(dialog)
            python = str(environment_python(self.root / '.venv'))
            self.assertEqual('Proje ortamı hazır.', dialog.status.text(), dialog.log.toPlainText())
            self.assertEqual(python, self.window.interpreter)
            self.wait(lambda: self.window.lsp.initialized)
            result = subprocess.run([python, '-c', 'from atelier_setup import VALUE; print(VALUE)'],
                                    capture_output=True, text=True, check=True, timeout=10)
            self.assertEqual('42', result.stdout.strip())
            manifest.write_text(
                '[build-system]\nrequires = []\nbuild-backend = "local_backend"\nbackend-path = ["."]\n'
                '[project]\nname = "atelier-setup"\nversion = "1.0"\n', encoding='utf-8')
            (self.root / 'local_backend.py').write_text(
                'from pathlib import Path\nfrom shutil import copyfile\n'
                'def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\n'
                f'    name = {wheel.name!r}\n'
                '    copyfile(Path(__file__).with_name(name), Path(wheel_directory) / name)\n'
                '    return name\n', encoding='utf-8')
            with (patch.object(QInputDialog, 'getItem', return_value=('pyproject.toml', True)),
                  patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok),
                  patch.dict(os.environ, {'PIP_NO_INDEX': '1'})):
                dialog.prepare_project()
                self.idle(dialog)
            self.assertEqual('Proje ortamı hazır.', dialog.status.text(), dialog.log.toPlainText())
            self.assertIn('Building wheel for atelier-setup', dialog.log.toPlainText())
        finally:
            self.idle(dialog)
            dialog.reject()

    def test_environment_and_package_lifecycle(self):
        w = self.window
        dialog = PythonEnvironmentDialog(w)
        dialog.show()
        try:
            self.idle(dialog)
            self.assertIsNotNone(dialog.metadata, dialog.log.toPlainText())
            target = self.root / '.venv'
            dialog.venv_path.setText(str(target))
            dialog.create_environment()
            self.idle(dialog)
            python = str(environment_python(target))
            self.assertEqual(python, dialog.python, dialog.log.toPlainText())
            self.assertTrue(dialog.metadata['pip'])
            self.assertTrue((target / '.gitignore').is_file())
            self.assertNotEqual(dialog.metadata['base'], dialog.metadata['prefix'])
            self.assertIn(python, discover_pythons(self.root, w.interpreter))
            from atelier.projects.settings import ProjectSettings
            fresh = QSettings(str(self.root / 'fresh.ini'), QSettings.Format.IniFormat)
            self.assertEqual(python, ProjectSettings(fresh).load(self.root, 'fallback')['interpreter'])
            old = w.lsp
            dialog.use_environment()
            self.assertIsNot(old, w.lsp)
            self.wait(lambda: w.lsp.initialized)
            self.assertEqual(python, w.interpreter)
            self.assertEqual(python, w.project_profiles.load(self.root, '')['interpreter'])
            self.assertNotEqual(python, w.project_profiles.load(self.root / 'other', 'fallback')['interpreter'])
            self.file('identity.py', 'import sys\nprint("ENV_PREFIX=" + sys.prefix)\n')
            w.run_file()
            self.wait(lambda: 'ENV_PREFIX=' in w.output.toPlainText())
            self.wait(lambda: w.runner.state() == QProcess.ProcessState.NotRunning)
            self.assertIn(str(target), w.output.toPlainText())

            # A local fixture avoids downloads and does not build the application.
            wheel = self.root / 'atelier_fixture-1.0-py3-none-any.whl'
            files = {
                'atelier_fixture.py': 'VALUE = 42\n',
                'atelier_fixture-1.0.dist-info/METADATA': 'Metadata-Version: 2.1\nName: atelier-fixture\nVersion: 1.0\n',
                'atelier_fixture-1.0.dist-info/WHEEL': 'Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
            }
            files['atelier_fixture-1.0.dist-info/RECORD'] = ''.join(name + ',,\n' for name in [*files, 'atelier_fixture-1.0.dist-info/RECORD'])
            with zipfile.ZipFile(wheel, 'w') as archive:
                for name, text in files.items():
                    archive.writestr(name, text)
            requirements = self.root / 'fixture-requirements.txt'
            requirements.write_text(str(wheel), encoding='utf-8')
            with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(requirements), '')):
                dialog.install_requirements()
            self.idle(dialog)
            names = [dialog.packages.topLevelItem(i).text(0) for i in range(dialog.packages.topLevelItemCount())]
            self.assertIn('atelier-fixture', names, dialog.log.toPlainText())
            dialog.filter.setText('atelier')
            self.assertTrue(all(dialog.packages.topLevelItem(i).isHidden() == ('atelier' not in dialog.packages.topLevelItem(i).text(0)) for i in range(dialog.packages.topLevelItemCount())))
            exported = self.root / 'export.txt'
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(exported), '')):
                dialog.export_requirements()
            self.idle(dialog)
            self.assertIn('atelier', exported.read_text(encoding='utf-8'))
            dialog.pip(['check'], 'check')
            self.idle(dialog)
            self.assertIn('No broken requirements', dialog.log.toPlainText())
            for i in range(dialog.packages.topLevelItemCount()):
                item = dialog.packages.topLevelItem(i)
                item.setSelected(item.text(0) == 'atelier-fixture')
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                dialog.uninstall()
            self.idle(dialog)
            self.assertFalse(any(dialog.packages.topLevelItem(i).text(0) == 'atelier-fixture' for i in range(dialog.packages.topLevelItemCount())))
            dialog.create_environment()  # Must never overwrite an existing directory.
            self.assertIsNone(dialog.operation)
            self.assertIn('zaten var', self.messages[-1])
        finally:
            self.idle(dialog)
            dialog.reject()

    def test_validation_failure_and_cancellation(self):
        self.assertEqual('requests[socks]==2.32.3', package_spec('requests[socks]', '2.32.3'))
        for name in ('--target=x', 'hello;whoami', '', '../package'):
            with self.assertRaises(ValueError):
                package_spec(name)
        dialog = PythonEnvironmentDialog(self.window)
        try:
            self.idle(dialog)
            dialog.start(['-c', 'import time; time.sleep(20)'], 'check')
            self.wait(lambda: dialog.process.state() == QProcess.ProcessState.Running)
            dialog.cancel()
            self.idle(dialog)
            self.assertIn('durduruldu', dialog.status.text())
            self.assertTrue(dialog.environments.isEnabled())
            dialog.start(['-c', 'raise SystemExit(3)'], 'check')
            self.idle(dialog)
            self.assertIn('başarısız', dialog.status.text())
            self.assertTrue(dialog.environments.isEnabled())
            dialog.start(['-c', 'print(1)'], 'check', str(self.root / 'missing-python'))
            self.idle(dialog)
            self.assertIn('başarısız', dialog.status.text())
        finally:
            dialog.reject()


if __name__ == '__main__':
    unittest.main()
