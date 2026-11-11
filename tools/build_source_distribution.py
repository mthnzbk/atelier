"""Build the source-based Windows distribution used by offline updates."""

import argparse
from pathlib import Path
import shutil

from atelier.runtime.updates import create_manifest
from atelier.version import APP_VERSION
from tools.windows_runtime import PROJECT_ROOT, prepare_runtime, requirements


def build(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    app = destination / "app"
    app.mkdir()
    prepare_runtime(destination / "runtime", requirements(), app_path="../app")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for name in ("atelier", "examples", "tools/windows"):
        shutil.copytree(PROJECT_ROOT / name, app / name, ignore=ignore)
    for name in ("main.py", "requirements.txt", "README.md"):
        shutil.copyfile(PROJECT_ROOT / name, app / name)
    for name in ("install.ps1", "uninstall.ps1", "kur.cmd"):
        shutil.copyfile(PROJECT_ROOT / "tools" / "windows" / name, destination / name)
    (destination / "Atelier.cmd").write_text(
        '@echo off\ncd /d "%~dp0app\\examples"\n'
        'start "" "%~dp0runtime\\pythonw.exe" "%~dp0app\\main.py"\n',
        encoding="ascii",
    )
    (destination / "BASLANGIC.txt").write_text(
        "Atelier Python Studio - Windows x64\n\n"
        "Kurmak icin kur.cmd dosyasini acin.\n"
        "Kurulum yapmadan Atelier.cmd ile baslatin.\n",
        encoding="utf-8",
    )
    create_manifest(destination, APP_VERSION)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    print(build(parser.parse_args().destination))
