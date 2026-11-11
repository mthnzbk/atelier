"""Rope-backed module/package renames, including import references."""
from pathlib import Path
from atelier.languages.rope_project import DirectoryProject
from rope.refactor.rename import Rename


def rename_changes(root, path, new_name):
    root, path = Path(root).resolve(), Path(path).resolve()
    project = DirectoryProject(str(root), ropefolder=None)
    try:
        resource = project.get_resource(path.relative_to(root).as_posix())
        module_name = Path(new_name).stem if path.suffix == '.py' else new_name
        changes = Rename(project, resource).get_changes(module_name)
        return project, changes
    except Exception:
        project.close()
        raise
