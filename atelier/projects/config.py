"""Read the shareable, project-local Atelier configuration."""
from pathlib import PureWindowsPath

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from atelier.projects.settings import SAVE_ACTIONS


FILENAME = 'atelier.toml'
EXAMPLE = """# Proje ayarları. Komutlar seçili Python ortamında çalışır.
# [save]
# format_on_save = true
# sort_imports = true
# format_web_on_save = true
# save_trim = true
# save_final_newline = true

[tasks.test]
label = "Testleri çalıştır"
args = ["-m", "pytest", "tests", "-q"]
# cwd = "."

# [profiles.app]
# file = "app.py"
# cwd = "."
# args = ["--port", "8000"]
"""


class ConfigError(ValueError):
    def __init__(self, field, detail):
        self.field = field
        super().__init__(f'{field} {detail}')


def table(value, name):
    if not isinstance(value, dict):
        raise ConfigError(name, 'bir TOML tablosu olmalı.')
    return value


def string(value, name):
    if not isinstance(value, str) or '\x00' in value:
        raise ConfigError(name, 'bir metin olmalı.')
    return value


def relative_path(value, name):
    value = string(value, name)
    path = PureWindowsPath(value)
    if not value or path.drive or path.root or '..' in path.parts:
        raise ConfigError(name, 'proje içinde göreli bir yol olmalı.')
    return path.as_posix()


def command_settings(section, name, profile=False):
    section = table(section, name)
    allowed = {'cwd', 'args', 'env', 'file' if profile else 'label'}
    if unknown := section.keys() - allowed:
        raise ConfigError(f'{name}.{sorted(unknown)[0]}', 'desteklenen bir ayar değil.')
    args = section.get('args', [])
    if not isinstance(args, list) or (not args and not profile):
        raise ConfigError(f'{name}.args', 'bir metin dizisi olmalı.')
    args = [string(value, f'{name}.args') for value in args]
    environment = table(section.get('env', {}), f'{name}.env')
    for key, value in environment.items():
        if not key or '=' in key or '\x00' in key:
            raise ConfigError(f'{name}.env', 'geçersiz değişken adı içeriyor.')
        string(value, f'{name}.env.{key}')
    result = dict(
        args=args,
        env=environment,
        cwd=relative_path(
            section.get(
                'cwd',
                '.'),
            f'{name}.cwd'))
    if profile:
        if 'file' in section:
            result['file'] = relative_path(section['file'], f'{name}.file')
    else:
        result['label'] = string(section.get('label', name.split('.', 1)[1]), f'{name}.label')
    return result


def validate_project_config(data):
    save = dict(table(data.get('save', {}), 'save'))
    for name, value in save.items():
        if name not in (*SAVE_ACTIONS, 'sort_imports') or type(value) is not bool:
            raise ConfigError(f'save.{name}', 'desteklenen bir true/false ayarı olmalı.')
    if 'sort_imports' in save:
        if 'save_imports' in save:
            raise ConfigError('save.sort_imports', 'save_imports ile aynı ayardır.')
        save['save_imports'] = save.pop('sort_imports')
    tasks = {key: command_settings(value, f'tasks.{key}')
             for key, value in table(data.get('tasks', {}), 'tasks').items()}
    profiles = {key: command_settings(value, f'profiles.{key}', profile=True)
                for key, value in table(data.get('profiles', {}), 'profiles').items()}
    default = string(data.get('default_profile', ''), 'default_profile')
    if default and default not in profiles:
        raise ConfigError('default_profile', 'profiles altında tanımlı bir profil olmalı.')
    return dict(save=save, tasks=tasks, profiles=profiles, default_profile=default)


def load_project_config(root):
    try:
        try:
            with (root / FILENAME).open('rb') as handle:
                data = tomllib.load(handle)
        except FileNotFoundError:
            data = {}
        return validate_project_config(data)
    except (OSError, ValueError) as error:
        raise ValueError(f'{FILENAME}: {error}') from error
