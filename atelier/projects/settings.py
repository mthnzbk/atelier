import hashlib
import os

SAVE_ACTIONS = (
    'format_on_save',
    'format_web_on_save',
    'save_imports',
    'save_trim',
    'save_final_newline')


class ProjectSettings:
    def __init__(self, settings):
        self.settings = settings

    def key(self, root):
        digest = hashlib.sha256(os.path.normcase(
            str(root.resolve())).encode('utf-8')).hexdigest()[:24]
        return 'projects/' + digest + '/'

    def load(self, root, fallback):
        key = self.key(root)
        from atelier.projects.environments import environment_python, valid_python_path
        interpreter = valid_python_path(self.settings.value(key + 'interpreter', ''))
        if not interpreter:
            for name in ('.venv', 'venv'):
                if interpreter := valid_python_path(environment_python(root / name)):
                    break
        return {
            'interpreter': interpreter or fallback,
            'run_args': self.settings.value(key + 'run_args', ''),
            'test_args': self.settings.value(key + 'test_args', ''),
        }

    def save(self, root, interpreter, run_args, test_args):
        key = self.key(root)
        for name, value in dict(interpreter=interpreter, run_args=run_args,
                                test_args=test_args, path=str(root)).items():
            self.settings.setValue(key + name, value)

    def load_save_actions(self, root):
        key = self.key(root) + 'save/'
        return {name: self.settings.value(key + name, self.settings.value(name, False, type=bool), type=bool)
                for name in SAVE_ACTIONS}

    def save_actions(self, root, options):
        key = self.key(root) + 'save/'
        for name in SAVE_ACTIONS:
            self.settings.setValue(key + name, options[name])
