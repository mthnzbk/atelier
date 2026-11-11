"""Project Python environments and asynchronous pip operations."""
import json
import os
import re
import shutil
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from atelier.runtime.paths import runtime_python


def environment_python(directory):
    directory = Path(directory)
    return directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


PYTHON_MISSING = 'Python bulunamadı. Python kurun veya Python ortamı menüsünden bir yorumlayıcı seçin.'


def valid_python_path(candidate):
    if not candidate:
        return ''
    path = Path(os.path.abspath(os.path.expanduser(str(candidate))))
    if os.name == 'nt' and any(part.casefold() == 'windowsapps' for part in path.parts):
        return ''
    if path.parent.name.casefold() == 'runtime' and (path.parent.parent / 'Atelier.exe').is_file():
        return ''
    return str(path) if path.is_file() and not venv_problem(path) else ''


def venv_problem(python):
    config = python.parent.parent / 'pyvenv.cfg'
    if python.parent.name.lower() not in ('scripts', 'bin') or not config.is_file():
        return ''
    try:
        values = {}
        for line in config.read_text(encoding='utf-8-sig').splitlines():
            key, separator, value = line.partition('=')
            if separator:
                values[key.strip().lower()] = value.strip()
        home = values.get('home')
        if not home or not Path(home).is_dir():
            return f'Temel Python klasörü bulunamadı ({home or config}).'
        if os.name == 'nt' and not (Path(home) / 'python.exe').is_file():
            return f'Temel Python dosyası bulunamadı ({Path(home) / "python.exe"}).'
    except (OSError, UnicodeError) as error:
        return f'pyvenv.cfg okunamadı ({error}).'
    return ''


def python_selection_details(root, selected, preferred, default):
    candidates = [(preferred, 'Kaydedilmiş proje seçimi')]
    candidates.extend((environment_python(root / name), f'Proje ortamı ({name})')
                      for name in ('.venv', 'venv') if (root / name).is_dir())
    candidates.append((default, 'Ayarlardaki Python'))
    issues = []
    for candidate, reason in candidates:
        if not candidate:
            continue
        if valid_python_path(candidate) == selected and selected:
            return reason, issues
        if not valid_python_path(candidate):
            path = Path(candidate)
            issues.append(f'{reason} · {venv_problem(path) or f"Python dosyası bulunamadı ({path})."}')
    return ('Sistem Python’u' if selected else 'Python bulunamadı'), issues


def discover_pythons(root, current, remembered=(), *, system_only=False):
    """Bounded local discovery. Never import or install anything in a candidate."""
    candidates = [] if system_only else [
        current, environment_python(Path(root) / '.venv'),
        environment_python(Path(root) / 'venv'), *remembered]
    for name in ('python', 'python3'):
        if found := shutil.which(name):
            candidates.append(found)
    containers = () if system_only else (
        Path.home() / '.virtualenvs', Path.home() / 'miniconda3' / 'envs',
        Path.home() / 'anaconda3' / 'envs')
    for container in containers:
        if container.is_dir():
            try:
                children = list(container.iterdir())[:100]
            except OSError:
                continue
            for child in children:
                candidates.append(str(environment_python(child)))
                if os.name == 'nt':  # Conda keeps Python directly in the environment.
                    candidates.append(str(child / 'python.exe'))
    if os.name == 'nt':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r'Software\Python\PythonCore', 0, winreg.KEY_READ | view) as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            version = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, version + r'\InstallPath') as install:
                                try:
                                    candidates.append(winreg.QueryValueEx(
                                        install, 'ExecutablePath')[0])
                                except OSError:
                                    candidates.append(
                                        str(Path(winreg.QueryValue(install, '')) / 'python.exe'))
                except OSError:
                    pass
    candidates.append(runtime_python())
    result, seen = [], set()
    for candidate in candidates:
        # abspath, not resolve: resolving a POSIX venv symlink loses its environment.
        path = valid_python_path(candidate)
        key = os.path.normcase(path)
        if path and key not in seen:
            seen.add(key)
            result.append(path)
    return result


def select_project_python(root, preferred='', default=''):
    for candidate in (preferred, environment_python(root / '.venv'),
                      environment_python(root / 'venv'), default):
        if path := valid_python_path(candidate):
            return path
    return next(iter(discover_pythons(root, '', system_only=True)), '')


def package_spec(name, version=''):
    name, version = name.strip(), version.strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9_,.-]+\])?', name):
        raise ValueError('Paket adını yazın; örnek: requests veya requests[socks].')
    if version and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.!+_-]*', version):
        raise ValueError(
            'Geçerli bir sürüm yazın; örnek: 2.32.3. Boş bırakılırsa güncel sürüm kurulur.')
    return name + ('==' + version if version else '')


def clean_environment():
    env = QProcessEnvironment.systemEnvironment()
    for key in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'CONDA_PREFIX'):
        env.remove(key)
    env.insert('PYTHONIOENCODING', 'utf-8')
    env.insert('PIP_NO_INPUT', '1')
    env.insert('PIP_DISABLE_PIP_VERSION_CHECK', '1')
    return env


def project_install_options(root):
    from atelier.projects.config import tomllib

    options = {}
    requirements = root / 'requirements.txt'
    if requirements.is_file():
        with requirements.open(encoding='utf-8-sig') as handle:
            text = handle.read(12001)
        preview = text[:12000] + ('\n…' if len(text) > 12000 else '')
        options['requirements.txt'] = (['-r', str(requirements)], preview)
    manifest = root / 'pyproject.toml'
    if manifest.is_file():
        with manifest.open('rb') as handle:
            data = tomllib.load(handle)
        project = data.get('project', {})
        poetry = data.get('tool', {}).get('poetry', {})
        if project or poetry or data.get('build-system'):
            dependencies = project.get('dependencies', []) or [
                f'{name} {version}' for name, version in poetry.get('dependencies', {}).items()
                if name.lower() != 'python']
            preview = '\n'.join(dependencies) or 'Bağımlılıklar varsa proje metadatasından çözümlenir.'
            options['pyproject.toml'] = (['.'], preview)
    return options


class PythonEnvironmentDialog(QDialog):
    def __init__(self, window, prepare=False):
        super().__init__(window)
        self.window = window
        self.root = Path(window.root)
        self.setWindowTitle('Python ortamları ve paketler — ' + self.root.name)
        self.resize(960, 730)
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_errors)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(self.process_error)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.cancel)
        self.operation = None
        self.cancelled = False
        self.output = bytearray()
        self.mutable = []
        layout = QVBoxLayout(self)
        self.active = QLabel('Projenin etkin Python ortamı: ' + window.interpreter)
        self.active.setWordWrap(True)
        layout.addWidget(self.active)
        row = QHBoxLayout()
        self.environments = QComboBox()
        self.environments.setMinimumContentsLength(40)
        row.addWidget(self.environments, 1)
        self.mutable.append(self.environments)
        self.button(row, 'Gözat…', self.browse)
        self.button(row, 'Yenile', self.discover)
        layout.addLayout(row)
        self.info = QLabel('Bir ortam seçin.')
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        use = QHBoxLayout()
        self.button(use, 'Bu proje için kullan', self.use_environment)
        self.button(use, 'Proje ortamını hazırla…', self.prepare_project)
        use.addStretch()
        layout.addLayout(use)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)
        env_page = QWidget()
        form = QFormLayout(env_page)
        tabs.addTab(env_page, 'Ortam oluştur')
        form.addRow(QLabel('Üstte seçili Python temel alınır. Mevcut bir klasörün üzerine yazılmaz.'))
        self.venv_path = QLineEdit(str(self.root / '.venv'))
        self.mutable.append(self.venv_path)
        form.addRow('Yeni ortam klasörü', self.venv_path)
        create_row = QHBoxLayout()
        self.button(create_row, 'Klasör seç…', self.browse_directory)
        self.button(create_row, 'Sanal ortam oluştur', self.create_environment)
        form.addRow(create_row)
        note = QLabel('Oluşturma bitince yeni ortam seçilir. “Bu proje için kullan” ile etkinleştirebilirsiniz. '
                      'Çalıştırma profilinde ayrıca Python belirtilmişse o tercih geçerlidir. '
                      'Açık terminal eski ortamda kalır; değiştirmek için terminalde “Yeni terminal” seçin.')
        note.setWordWrap(True)
        form.addRow(note)
        packages = QWidget()
        package_layout = QVBoxLayout(packages)
        tabs.addTab(packages, 'Paketler')
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Kurulu paketlerde filtrele…')
        self.filter.textChanged.connect(self.filter_packages)
        package_layout.addWidget(self.filter)
        self.packages = QTreeWidget()
        self.packages.setHeaderLabels(['Paket', 'Kurulu sürüm', 'Güncel sürüm'])
        self.packages.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.packages.setSortingEnabled(True)
        self.packages.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.packages.setColumnWidth(0, 290)
        package_layout.addWidget(self.packages, 1)
        install_row = QHBoxLayout()
        self.package = QLineEdit()
        self.package.setPlaceholderText('Paket adı (ör. requests)')
        self.package_version = QLineEdit()
        self.package_version.setPlaceholderText('Sürüm (isteğe bağlı)')
        install_row.addWidget(self.package, 2)
        install_row.addWidget(self.package_version, 1)
        self.mutable.extend([self.package, self.package_version, self.packages])
        self.button(install_row, 'Kur', self.install)
        package_layout.addLayout(install_row)
        actions = QHBoxLayout()
        self.button(actions, 'Listeyi yenile', self.refresh_packages)
        self.button(actions, 'Güncellemeleri denetle', self.outdated)
        self.button(actions, 'Seçileni güncelle', self.upgrade)
        self.button(actions, 'Seçileni kaldır', self.uninstall)
        package_layout.addLayout(actions)
        files = QHBoxLayout()
        self.button(files, 'requirements kur…', self.install_requirements)
        self.button(files, 'requirements dışa aktar…', self.export_requirements)
        self.button(files, 'Bağımlılıkları kontrol et', lambda: self.pip(['check'], 'check'))
        package_layout.addLayout(files)
        tools = QHBoxLayout()
        self.button(tools, 'pip kur / onar',
                    lambda: self.start(['-m', 'ensurepip', '--upgrade'], 'mutate'))
        self.button(tools, 'Test / debug araçlarını kur', self.install_tools)
        package_layout.addLayout(tools)
        note = QLabel('İşlemler üstte seçili ortamda yapılır. Testler için pytest/coverage, hata ayıklama için debugpy gerekir. '
                      'Paket kurma ve güncelleme internet bağlantısı gerektirebilir.')
        note.setWordWrap(True)
        package_layout.addWidget(note)
        self.status = QLabel('Hazır')
        layout.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setMaximumHeight(150)
        layout.addWidget(self.log)
        footer = QHBoxLayout()
        self.stop_button = QPushButton('İşlemi durdur')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.cancel)
        footer.addWidget(self.stop_button)
        footer.addStretch()
        close = QPushButton('Kapat')
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        layout.addLayout(footer)
        self.environments.currentIndexChanged.connect(self.selection_changed)
        self.discover(probe=not prepare)
        if prepare:
            QTimer.singleShot(0, self.prepare_project)

    def button(self, layout, text, callback):
        button = QPushButton(text)
        button.clicked.connect(callback)
        layout.addWidget(button)
        self.mutable.append(button)
        return button

    @property
    def python(self):
        return self.environments.currentData() or ''

    def discover(self, selected=None, *, probe=True):
        remembered = self.window.settings.value('python/known', []) or []
        if isinstance(remembered, str):
            remembered = [remembered]
        selected = selected or self.python or self.window.interpreter
        paths = discover_pythons(self.root, self.window.interpreter, remembered + [selected])
        self.environments.blockSignals(True)
        self.environments.clear()
        for path in paths:
            self.environments.addItem(path, path)
        index = self.environments.findData(selected)
        self.environments.setCurrentIndex(max(0, index))
        self.environments.blockSignals(False)
        if probe:
            self.selection_changed()

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Python çalıştırılabilir dosyası', str(
                self.root), 'Tüm dosyalar (*)')
        if path:
            self.discover(os.path.abspath(path))

    def browse_directory(self):
        parent = QFileDialog.getExistingDirectory(self, 'Yeni ortamın üst klasörü', str(self.root))
        if parent:
            self.venv_path.setText(str(Path(parent) / '.venv'))

    def selection_changed(self):
        self.packages.clear()
        self.metadata = None
        if self.python:
            script = ('import sys,json,importlib.util; print(json.dumps(dict(executable=sys.executable,'
                      'version=sys.version.split()[0],prefix=sys.prefix,base=sys.base_prefix,'
                      'pip=importlib.util.find_spec("pip") is not None)))')
            self.start(['-c', script], 'probe')

    def set_busy(self, busy):
        for widget in self.mutable:
            widget.setEnabled(not busy)
        self.stop_button.setEnabled(busy)

    def start(self, arguments, operation, python=None):
        if self.operation is not None:
            return
        self.operation, self.cancelled = operation, False
        self.output.clear()
        self.set_busy(True)
        self.status.setText('Çalışıyor…')
        self.process.setWorkingDirectory(str(self.root))
        self.process.setProcessEnvironment(clean_environment())
        self.process.setProgram(python or self.python)
        self.process.setArguments(['-u', *arguments])
        self.log.appendPlainText('> ' + (python or self.python) + ' ' +
                                 ' '.join(arguments if operation != 'probe' else ['(ortam bilgisi)']))
        self.process.start()
        if operation in ('probe', 'list'):
            self.timeout.start(20000)

    def pip(self, arguments, operation='mutate'):
        self.start(['-m', 'pip', '--disable-pip-version-check',
                   '--no-input', '--no-color', *arguments], operation)

    def read_output(self):
        data = bytes(self.process.readAllStandardOutput())
        self.output.extend(data)
        if self.operation not in ('probe', 'list', 'outdated', 'freeze'):
            cursor = self.log.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(data.decode('utf-8', 'replace'))
            self.log.setTextCursor(cursor)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.log.appendPlainText(self.process.errorString())
            self.process_finished(-1, QProcess.ExitStatus.CrashExit)

    def read_errors(self):
        text = bytes(self.process.readAllStandardError()).decode('utf-8', 'replace')
        if text:
            self.log.appendPlainText(text.rstrip())

    def process_finished(self, code, exit_status):
        if self.operation is None:
            return
        self.timeout.stop()
        self.read_output()
        self.read_errors()
        operation, self.operation = self.operation, None
        self.set_busy(False)
        text = self.output.decode('utf-8', 'replace')
        if self.cancelled or code != 0 or exit_status != QProcess.ExitStatus.NormalExit:
            if operation == 'prepare_create':
                try:
                    self.prepared_python.parent.parent.rmdir()
                except OSError:
                    pass
            self.status.setText(
                'İşlem durduruldu; değişiklikler kısmen uygulanmış olabilir.' if self.cancelled else 'İşlem başarısız. Ayrıntıları aşağıda görebilirsiniz.')
            if operation in ('probe', 'list', 'outdated', 'freeze'):
                self.log.appendPlainText(text)
            if operation == 'probe':
                self.metadata = None
                self.info.setText('Bu Python çalıştırılamadı. Başka bir ortam seçin.')
            return
        self.status.setText('Tamamlandı')
        try:
            if operation == 'probe':
                self.metadata = json.loads(text)
                kind = 'Sanal ortam' if self.metadata['prefix'] != self.metadata['base'] else 'Python kurulumu'
                self.info.setText(
                    f"{kind} · Python {
                        self.metadata['version']} · pip {
                        'hazır' if self.metadata['pip'] else 'kurulu değil'}")
                known = self.window.settings.value('python/known', []) or []
                if isinstance(known, str):
                    known = [known]
                self.window.settings.setValue(
                    'python/known', list(dict.fromkeys([*known, self.python])))
                if self.metadata['pip']:
                    self.refresh_packages()
            elif operation in ('list', 'outdated'):
                rows = json.loads(text)
                if operation == 'list':
                    self.packages.clear()
                    for row in rows:
                        QTreeWidgetItem(self.packages, [row['name'], row['version'], ''])
                else:
                    latest = {row['name'].lower().replace('_', '-'): row['latest_version']
                              for row in rows}
                    for i in range(self.packages.topLevelItemCount()):
                        item = self.packages.topLevelItem(i)
                        item.setText(2, latest.get(item.text(0).lower().replace('_', '-'), ''))
                self.filter_packages()
                self.status.setText(f'{self.packages.topLevelItemCount()} paket' +
                                    (' · Güncellemeler denetlendi' if operation == 'outdated' else ''))
            elif operation == 'create':
                ignore = self.created_path / '.gitignore'
                if not ignore.exists():
                    ignore.write_text('# Virtual environment\n*\n', encoding='utf-8')
                self.discover(str(environment_python(self.created_path)))
            elif operation == 'prepare_create':
                ignore = self.prepared_python.parent.parent / '.gitignore'
                if not ignore.exists():
                    ignore.write_text('# Virtual environment\n*\n', encoding='utf-8')
                self.install_project_dependencies()
            elif operation == 'prepare_install':
                self.finish_project_setup()
            elif operation == 'freeze':
                Path(self.export_path).write_text(text, encoding='utf-8')
                self.status.setText('Dışa aktarıldı: ' + self.export_path)
            elif operation == 'mutate':
                if self.python == self.window.interpreter:
                    self.window.start_lsp()
                self.selection_changed()
        except (ValueError, KeyError, OSError) as error:
            self.status.setText('Sonuç işlenemedi: ' + str(error))
            self.log.appendPlainText(text)

    def use_environment(self):
        if not self.metadata:
            self.window.message('Önce çalışır bir Python ortamı seçin.')
            return
        # A running/debugging process keeps its original interpreter until restarted.
        self.window.activate_project_python(self.python)
        self.active.setText('Projenin etkin Python ortamı: ' + self.python)
        self.status.setText(
            'Ortam proje için kaydedildi. Yeni çalıştırmalar ve testler bu ortamı kullanacak.')

    def prepare_project(self):
        if self.operation is not None:
            return
        target = self.root / '.venv'
        python = environment_python(target)
        exists = target.exists() or target.is_symlink()
        if exists and (not valid_python_path(python) or not (target / 'pyvenv.cfg').is_file()):
            self.window.message('.venv kullanılamıyor. Python durumu panelinden sorunu inceleyin veya başka bir ortam seçin.')
            return
        base = valid_python_path(self.python or self.window.interpreter)
        if not exists and not base:
            self.window.message(PYTHON_MISSING)
            return
        try:
            options = project_install_options(self.root)
        except (ValueError, TypeError, AttributeError, OSError) as error:
            self.window.message('Bağımlılıklar okunamadı. ' + str(error))
            return
        choice = next(iter(options), '')
        if len(options) > 1:
            choice, accepted = QInputDialog.getItem(
                self, 'Bağımlılık kaynağı', 'Kurulacak bağımlılıkların kaynağı', list(options), editable=False)
            if not accepted:
                return
        arguments, preview = options.get(choice, ([], 'Bağımlılık dosyası bulunamadı.'))
        confirm = QMessageBox(self)
        confirm.setWindowTitle('Proje ortamını hazırla')
        confirm.setText(f'Mevcut ortam etkinleştirilecek.\n{target.resolve()}' if exists
                        else f'.venv oluşturulacak. Temel Python\n{base}')
        summary = preview[:1000] + ('\n…' if len(preview) > 1000 else '')
        confirm.setInformativeText(f'{choice} kullanılarak paketler kurulacak.\n\n{summary}' if choice else preview)
        if choice:
            confirm.setDetailedText(preview)
        confirm.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if confirm.exec() != QMessageBox.StandardButton.Ok:
            return
        self.prepared_python = python
        self.project_install_args = arguments
        if exists:
            self.install_project_dependencies()
        else:
            try:
                target.mkdir()
            except OSError as error:
                self.window.message('.venv oluşturulamadı. ' + str(error))
                return
            self.start(['-m', 'venv', str(target)], 'prepare_create', python=base)

    def install_project_dependencies(self):
        if self.project_install_args:
            self.start(['-m', 'pip', 'install', '--no-input', *self.project_install_args],
                       'prepare_install', python=str(self.prepared_python))
        else:
            self.finish_project_setup()

    def finish_project_setup(self):
        python = valid_python_path(self.prepared_python)
        if not python:
            self.status.setText('Oluşturulan .venv çalıştırılamıyor.')
            return
        self.window.activate_project_python(python)
        self.active.setText('Projenin etkin Python ortamı: ' + python)
        self.discover(python, probe=False)
        self.metadata = None
        self.packages.clear()
        self.info.setText('Yeni paket listesini görmek için Yenile’yi seçin.')
        self.status.setText('Proje ortamı hazır.')

    def create_environment(self):
        raw = self.venv_path.text().strip()
        if not raw:
            self.window.message('Yeni ortam klasörünü yazın.')
            return
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = self.root / path
        path = path.absolute()
        if path.exists():
            self.window.message(
                'Bu klasör zaten var. Yeni bir klasör adı seçin; mevcut dosyalar korunur.')
            return
        self.created_path = path
        self.start(['-m', 'venv', str(path)], 'create')

    def refresh_packages(self):
        self.pip(['list', '--format=json'], 'list')

    def outdated(self):
        self.pip(['list', '--outdated', '--format=json'], 'outdated')

    def filter_packages(self):
        text = self.filter.text().casefold()
        for i in range(self.packages.topLevelItemCount()):
            item = self.packages.topLevelItem(i)
            item.setHidden(text not in item.text(0).casefold())

    def install(self):
        try:
            spec = package_spec(self.package.text(), self.package_version.text())
        except ValueError as error:
            self.window.message(str(error))
            return
        self.pip(['install', spec])

    def selected_packages(self):
        names = [item.text(0) for item in self.packages.selectedItems() if not item.isHidden()]
        if not names:
            self.window.message('Listeden en az bir paket seçin.')
        return names

    def upgrade(self):
        if names := self.selected_packages():
            self.pip(['install', '--upgrade', *names])

    def uninstall(self):
        names = self.selected_packages()
        if names and QMessageBox.question(self, 'Paketleri kaldır', self.python +
                                          '\n\nKaldırılacak paketler:\n' + ', '.join(names)) == QMessageBox.StandardButton.Yes:
            self.pip(['uninstall', '-y', *names])

    def install_requirements(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Bağımlılık dosyasını kur', str(
                self.root), 'Requirements (*.txt *.in);;Tüm dosyalar (*)')
        if path:
            self.pip(['install', '-r', path])

    def export_requirements(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Kurulu sürümleri dışa aktar', str(
                self.root / 'requirements.txt'), 'Requirements (*.txt)')
        if path:
            self.export_path = path
            self.pip(['freeze'], 'freeze')

    def install_tools(self):
        self.pip(['install', 'pytest>=8,<10', 'coverage>=7.6,<8', 'debugpy>=1.8,<2'])

    def cancel(self):
        if self.operation is not None:
            self.cancelled = True
            self.process.kill()

    def reject(self):
        if self.operation is not None:
            self.status.setText(
                'Kapatmadan önce işlemin bitmesini bekleyin veya “İşlemi durdur” seçeneğini kullanın.')
            return
        super().reject()
