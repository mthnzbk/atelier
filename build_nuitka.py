"""Build Atelier for Windows x64 and package its Python tools."""

import argparse
from importlib.metadata import distribution
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

from atelier.version import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent
EXE_NAME = "Atelier.exe"
RELEASE_NAME = f"Atelier-{APP_VERSION}-windows-x64.zip"
PYGMENTS_MODULES = (
    "lexers.python", "lexers.markup", "lexers.data", "lexers.html", "lexers.css",
    "lexers.javascript", "lexers.configs", "lexers.sql", "styles.monokai", "styles.friendly",
)
TOOL_DISTRIBUTIONS = (
    "python-lsp-server", "python-lsp-jsonrpc", "jedi", "parso", "pluggy",
    "docstring-to-markdown", "importlib-metadata", "zipp", "typing-extensions",
    "pycodestyle", "pyflakes", "autopep8", "debugpy",
    "pytest", "coverage", "iniconfig", "packaging", "colorama", "pygments", "tomli",
)


def compiler_command(output, compiler="msvc"):
    assets = PROJECT_ROOT / "atelier" / "assets"
    toolchain = ["--mingw64", "--assume-yes-for-downloads"] if compiler == "mingw64" else ["--msvc=latest"]
    return [
        sys.executable, "-m", "nuitka",
        "--mode=standalone",
        "--enable-plugin=pyside6",
        "--include-qt-plugins=sensible,imageformats",
        "--noinclude-custom-mode=pygments:bytecode",
        *(f"--include-module=pygments.{name}" for name in PYGMENTS_MODULES),
        "--include-package=markdown.extensions",
        "--include-package-data=qtawesome",
        "--include-distribution-metadata=Markdown",
        f"--include-data-dir={assets}=atelier/assets",
        f"--windows-icon-from-ico={output / 'atelier.ico'}",
        "--windows-console-mode=disable",
        *toolchain,
        "--product-name=Atelier",
        "--file-description=Atelier Python Studio",
        f"--file-version={APP_VERSION}",
        f"--product-version={APP_VERSION}",
        f"--output-filename={EXE_NAME}",
        f"--output-dir={output}",
        str(PROJECT_ROOT / "main.py"),
    ]


def write_windows_icon(target):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    image = QImage(str(PROJECT_ROOT / "atelier" / "assets" / "atelier-logo.png"))
    icon = image.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
    if not icon.save(str(target), "ICO"):
        raise RuntimeError("Windows uygulama simgesi oluşturulamadı.")


def stage_support(bundle):
    support = bundle / "support"
    support.mkdir()
    for name in ("python_tool.py", "pytest_host.py", "import_index.py"):
        shutil.copyfile(PROJECT_ROOT / "atelier" / "workers" / name, support / name)
    for name in TOOL_DISTRIBUTIONS:
        package = distribution(name)
        for entry in package.files or ():
            if (entry.is_absolute() or ".." in entry.parts or "__pycache__" in entry.parts
                    or entry.suffix in {".pyc", ".pyd", ".dll", ".so", ".dylib", ".exe"}):
                continue
            source = package.locate_file(entry)
            if source.is_file():
                target = support / "vendor" / entry
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)


def build(output, compiler="msvc"):
    if (sys.platform != "win32" or struct.calcsize("P") != 8
            or platform.machine().lower() not in {"amd64", "x86_64"}):
        raise SystemExit("Bu build betiği Windows x64 CPython gerektirir.")
    if sys.version_info < (3, 12):
        raise SystemExit("Bu build betiği CPython 3.12 veya üzerini gerektirir.")
    if compiler == "mingw64" and sys.version_info[:2] != (3, 12):
        raise SystemExit("MinGW64 seçeneği CPython 3.12 gerektirir.")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "Atelier"
    if destination.exists():
        raise SystemExit(f"{destination} zaten var. Farklı bir --output-dir seçin.")
    with tempfile.TemporaryDirectory(prefix=".atelier-nuitka-", dir=output) as directory:
        staging = Path(directory)
        write_windows_icon(staging / "atelier.ico")
        subprocess.run(compiler_command(staging, compiler), cwd=PROJECT_ROOT, check=True)
        bundles = [folder for folder in staging.glob("*.dist") if (folder / EXE_NAME).is_file()]
        if len(bundles) != 1:
            raise RuntimeError("Nuitka çıktı klasöründe Atelier.exe bulunamadı.")
        bundle = bundles[0]
        stage_support(bundle)
        if not bundle.resolve().is_relative_to(output) or not destination.resolve().is_relative_to(output):
            raise RuntimeError("Dağıtım yolları çıktı klasörünün dışında.")
        bundle.rename(destination)
    return destination / EXE_NAME


def build_release(output, compiler="msvc"):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    destination = output / RELEASE_NAME
    if destination.exists():
        raise SystemExit(f"{destination} zaten var. Farklı bir --output-dir seçin.")
    with tempfile.TemporaryDirectory(prefix=".atelier-release-", dir=output) as directory:
        staging = Path(directory)
        bundle = build(staging, compiler).parent
        archive = staging / RELEASE_NAME
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            for file in sorted(bundle.rglob("*")):
                relative_path = file.relative_to(staging)
                if file.is_file() and "__pycache__" not in relative_path.parts:
                    zipped.write(file, relative_path)
        archive.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "dist")
    parser.add_argument("--compiler", choices=("msvc", "mingw64"), default="msvc")
    parser.add_argument("--release", action="store_true",
                        help="Sürümlü Windows dağıtım ZIP dosyasını oluştur.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Yalnızca derleme komutunu ve çıktı yolunu göster.")
    args = parser.parse_args()
    if args.dry_run:
        print(subprocess.list2cmdline(
            compiler_command(args.output_dir.resolve() / ".nuitka-stage", args.compiler)))
        destination = args.output_dir.resolve()
        print(destination / RELEASE_NAME if args.release else destination / "Atelier" / EXE_NAME)
    else:
        command = build_release if args.release else build
        print(command(args.output_dir, args.compiler))


if __name__ == "__main__":
    main()
