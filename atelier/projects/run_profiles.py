import json, shlex
from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,QPlainTextEdit,QPushButton,QHBoxLayout,QInputDialog,QDialogButtonBox,QFileDialog


def local_profiles(window):
    key=window.project_profiles.key(window.root)
    try:profiles=json.loads(window.settings.value(key+'run_profiles','{}'))
    except (TypeError,ValueError):profiles={}
    return profiles,window.settings.value(key+'active_profile','')


def load_profiles(window):
    from atelier.projects.config import load_project_config
    local, _ = local_profiles(window)
    config = load_project_config(window.root)
    profiles = {**local, **config['profiles']}
    key = window.project_profiles.key(window.root)
    active = window.settings.value(key + 'active_profile', config['default_profile'])
    return profiles, active


def resolve_profile(window):
    from atelier.projects.environments import PYTHON_MISSING, valid_python_path
    profiles,name=load_profiles(window);profile=profiles.get(name,{})
    path=Path(profile.get('file') or (window.current.path if window.current else None) or '.')
    if not path.is_absolute():path=window.root/path
    cwd=Path(profile.get('cwd') or window.root)
    if not cwd.is_absolute():cwd=window.root/cwd
    python=profile_python(window, profile)
    args=profile.get('args',window.run_args)
    if isinstance(args,str):args=shlex.split(args)
    environment=profile.get('env',{})
    if not valid_python_path(python):raise ValueError(PYTHON_MISSING)
    if not path.is_file():raise ValueError('Çalıştırılacak dosya bulunamadı: '+str(path))
    if not cwd.is_dir():raise ValueError('Çalışma klasörü bulunamadı: '+str(cwd))
    return path,python,cwd,args,environment


def profile_python(window, profile):
    override = profile.get('python')
    if not override:
        return window.interpreter
    return str(window.root / Path(override).expanduser())


class RunProfilesDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.profiles,_=local_profiles(window)
        from atelier.projects.config import load_project_config
        self.shared=load_project_config(window.root)['profiles']
        _,self.active=load_profiles(window)
        self.setWindowTitle('Çalıştırma profilleri');self.resize(740,520)
        layout=QVBoxLayout(self);self.names=QComboBox();layout.addWidget(self.names)
        form=QFormLayout();self.fields={}
        self.edit_buttons = []
        for key,label in [('file','Dosya (boş: etkin dosya)'),('python','Python (boş: proje ortamı)'),('cwd','Çalışma dizini (boş: proje kökü)'),('args','Argümanlar')]:
            field = self.fields[key] = QLineEdit()
            if key == 'args':
                field.setPlaceholderText('--mode dev "iki kelime"')
                form.addRow(label, field)
            else:
                picker = QPushButton('Gözat…')
                picker.clicked.connect(lambda checked=False, name=key: self.choose_path(name))
                self.edit_buttons.append(picker)
                field_row = QHBoxLayout()
                field_row.addWidget(field, 1)
                field_row.addWidget(picker)
                form.addRow(label, field_row)
        self.environment=QPlainTextEdit();self.environment.setPlaceholderText('KEY=value\nHer satıra bir ortam değişkeni')
        form.addRow('Ortam değişkenleri',self.environment);layout.addLayout(form)
        row=QHBoxLayout()
        for label,callback in [('Yeni',self.add),('Profili kaydet',self.save_profile),('Sil',self.remove)]:
            button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
            if callback != self.add:
                self.edit_buttons.append(button)
        layout.addLayout(row)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept_profiles);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.names.currentTextChanged.connect(self.show_profile);self.reload()
    def reload(self):
        names = dict.fromkeys([*self.profiles, *self.shared])
        self.names.clear();self.names.addItem('Etkin dosya (varsayılan)');self.names.addItems(names)
        if self.active in names:self.names.setCurrentText(self.active)
    def show_profile(self,name):
        shared = name in self.shared
        editable = name in self.profiles and not shared
        profile=self.shared[name] if shared else self.profiles.get(name,{})
        for key,field in self.fields.items():
            value = profile.get(key,'')
            field.setText(shlex.join(value) if isinstance(value,list) else value)
            field.setReadOnly(not editable)
        self.environment.setReadOnly(not editable)
        for button in self.edit_buttons:button.setEnabled(editable)
        self.names.setToolTip('Bu profil atelier.toml dosyasından düzenlenir.' if shared else '')
        self.environment.setPlainText('\n'.join(f'{key}={value}' for key,value in profile.get('env',{}).items()))

    def choose_path(self, field):
        root = self.window.root
        current = root / (self.fields[field].text() or '.')
        if field == 'cwd':
            chosen = QFileDialog.getExistingDirectory(self, 'Çalışma dizinini seç', str(current))
        else:
            title = 'Giriş dosyasını seç' if field == 'file' else 'Python yorumlayıcısını seç'
            filters = 'Python (*.py *.pyw);;Tüm dosyalar (*)' if field == 'file' else 'Tüm dosyalar (*)'
            chosen, _ = QFileDialog.getOpenFileName(self, title, str(current), filters)
        if chosen:
            path = Path(chosen)
            self.fields[field].setText(path.relative_to(root).as_posix()
                                       if path.is_relative_to(root) else str(path))
    def add(self):
        name,ok=QInputDialog.getText(self,'Yeni profil','Profil adı:')
        if ok and name.strip():
            if name.strip() in self.shared:
                self.window.message('Bu ad atelier.toml içinde kullanılıyor.')
                return
            current = self.window.current
            initial = {}
            if current and current.path:
                path = current.path
                initial['file'] = path.relative_to(self.window.root).as_posix() if path.is_relative_to(self.window.root) else str(path)
            self.profiles.setdefault(name.strip(), initial)
            self.active = name.strip()
            self.reload()
    def save_profile(self):
        name=self.names.currentText()
        if name in self.shared or name not in self.profiles:return True
        try:
            profile={key:field.text().strip() for key,field in self.fields.items()};shlex.split(profile['args'])
            env={}
            for line in self.environment.toPlainText().splitlines():
                if not line.strip():continue
                key,separator,value=line.partition('=')
                if not separator or not key.strip() or '\x00' in line:raise ValueError('Ortam değişkenlerini KEY=value biçiminde yazın.')
                env[key.strip()]=value
            profile['env']=env;self.profiles[name]=profile;return True
        except ValueError as error:self.window.message(str(error));return False
    def remove(self):
        if self.names.currentText() in self.shared:return
        self.profiles.pop(self.names.currentText(),None);self.active='';self.reload()
    def accept_profiles(self):
        if not self.save_profile():return
        key=self.window.project_profiles.key(self.window.root)
        selected=self.names.currentText()
        active=selected if selected in self.profiles or selected in self.shared else ''
        self.window.settings.setValue(key+'run_profiles',json.dumps(self.profiles));self.window.settings.setValue(key+'active_profile',active);self.accept()
