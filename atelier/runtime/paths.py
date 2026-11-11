import sys
from pathlib import Path


def compiled():
    return '__compiled__' in globals()


def application_root():
    if compiled():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def asset_path(name):
    return application_root() / 'atelier' / 'assets' / name


def worker_script(name):
    if compiled():
        return application_root() / 'support' / name
    return application_root() / 'atelier' / 'workers' / name


def worker_command(kind, *args):
    if compiled():
        return str(application_root() / 'Atelier.exe'), ['--atelier-worker', kind, *args]
    return runtime_python(), ['-u', str(worker_script('entry.py')), kind, *args]


def python_tool_arguments(kind):
    if compiled():
        return ['-I', '-u', str(application_root() / 'support' / 'python_tool.py'), kind]
    return ['-m', {'lsp': 'pylsp', 'debug': 'debugpy.adapter'}[kind]]


def python_tool_command(kind, interpreter):
    return (interpreter if compiled() else runtime_python()), python_tool_arguments(kind)


def runtime_python():
    if compiled():
        return ''
    executable = Path(sys.executable)
    if executable.name.lower() == 'pythonw.exe' and executable.with_name('python.exe').exists():
        executable = executable.with_name('python.exe')
    return str(executable)
