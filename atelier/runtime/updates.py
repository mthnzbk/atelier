"""Stage user-selected offline update packages, checking paths and every hash."""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from PySide6.QtCore import QThread, Signal
from atelier.runtime.paths import application_root

ROOT_FILES = {'install.ps1', 'uninstall.ps1', 'kur.cmd', 'Atelier.cmd', 'BASLANGIC.txt'}


def safe_name(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or path.is_absolute() or any(
            part in ('', '.', '..') or part.endswith((' ', '.')) for part in name.split('/')):
        raise ValueError('Güncelleme paketinde geçersiz dosya yolu var.')
    if path.parts[0] not in ('app', 'runtime') and name not in ROOT_FILES | {'manifest.json'}:
        raise ValueError('Güncelleme paketinde beklenmeyen dosya var: ' + name)
    return path


def create_manifest(root, version):
    root = Path(root)
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc' and path != root / 'manifest.json':
            relative = path.relative_to(root).as_posix()
            safe_name(relative)
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'format': 1, 'version': version, 'platform': 'windows-x64', 'files': files}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def stage_package(archive, destination, progress=None, cancelled=None):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        infos = [info for info in package.infolist() if not info.is_dir()]
        if len(infos) > 40000 or sum(info.file_size for info in infos) > 2_000_000_000:
            raise ValueError('Güncelleme paketi beklenen boyutu aşıyor.')
        names = [info.filename for info in infos]
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError('Pakette yinelenen dosyalar var.')
        for info in infos:
            safe_name(info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Güncelleme paketi sembolik bağlantı içeremez.')
        if 'manifest.json' not in names or package.getinfo('manifest.json').file_size > 8_000_000:
            raise ValueError('Bu ZIP doğrulanabilir bir Atelier güncelleme paketi değil.')
        manifest = json.loads(package.read('manifest.json'))
        files = manifest.get('files', {})
        if manifest.get('format') != 1 or manifest.get(
                'platform') != 'windows-x64' or not isinstance(files, dict):
            raise ValueError('Paket biçimi/platformu desteklenmiyor.')
        if set(names) - {'manifest.json'} != set(files) or not {'app/main.py',
                                                                'runtime/python.exe', 'runtime/pythonw.exe'} <= set(files):
            raise ValueError('Paket dosya listesi eksik veya tutarsız.')
        for index, info in enumerate(infos):
            if cancelled and cancelled():
                raise InterruptedError('Güncelleme hazırlığı iptal edildi.')
            target = destination.joinpath(*safe_name(info.filename).parts)
            if not target.resolve().is_relative_to(destination):
                raise ValueError('Paket hedef klasör dışına çıkıyor.')
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with package.open(info) as source, target.open('wb') as output:
                while chunk := source.read(1024 * 1024):
                    if cancelled and cancelled():
                        raise InterruptedError('Güncelleme hazırlığı iptal edildi.')
                    digest.update(chunk)
                    output.write(chunk)
            if info.filename != 'manifest.json' and digest.hexdigest() != files[info.filename]:
                raise ValueError('Paket bütünlük kontrolü başarısız: ' + info.filename)
            if progress and index % 50 == 0:
                progress(int((index + 1) * 100 / max(1, len(infos))))
        return manifest


class UpdateWorker(QThread):
    ready = Signal(object, str)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, archive, destination, parent=None):
        super().__init__(parent)
        self.archive, self.destination = archive, Path(destination)

    def run(self):
        try:
            manifest = stage_package(
                self.archive,
                self.destination,
                self.progress.emit,
                self.isInterruptionRequested)
            self.ready.emit(manifest, str(self.destination))
        except Exception as error:
            self.failed.emit(str(error))


def launch_windows_update(payload, installation, parent_pid):
    installation, payload = Path(installation).resolve(), Path(payload).resolve()
    if os.name != 'nt' or not (
            installation / 'runtime/python.exe').is_file() or not (installation / 'app/main.py').is_file():
        raise ValueError('Bu kurulum otomatik Windows güncellemesini desteklemiyor.')
    script = payload / 'apply_update.ps1'
    shutil.copyfile(application_root() / 'tools' / 'windows' / 'apply_update.ps1', script)
    subprocess.Popen(['powershell.exe', '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                      '-ParentProcessId', str(parent_pid), '-InstallRoot', str(installation), '-Payload', str(payload)],
                     creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
