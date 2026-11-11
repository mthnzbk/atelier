"""Rope projects on both regular and bundled Python runtimes."""
import inspect
import sys
from pathlib import Path
from rope.base import stdmods
from rope.base.project import Project

# Rope enumerates the inspect module's parent with os.listdir. The bundled
# standard library lives in a ZIP; Python already provides the module names.
if not Path(inspect.__file__).parent.is_dir():
    stdmods.python_modules = lambda: set(sys.stdlib_module_names)


class DirectoryProject(Project):
    def get_python_path_folders(self):
        # The bundled runtime includes a stdlib ZIP in sys.path. Rope's module
        # finder treats every entry as a folder and cannot list files in that ZIP.
        return [resource for resource in super().get_python_path_folders() if resource.is_folder()]
