"""Stage the verified Windows Python runtime used by editor subprocesses."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile


PYTHON_URL = "https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip"
PYTHON_SHA256 = "90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def requirements():
    return [
        line.strip()
        for line in (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def prepare_runtime(runtime, packages, app_path=None):
    runtime.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="atelier-runtime-") as directory:
        archive = Path(directory) / "python.zip"
        urllib.request.urlretrieve(PYTHON_URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != PYTHON_SHA256:
            raise RuntimeError("Python çalışma ortamı arşivinin SHA-256 değeri uyuşmuyor.")
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(runtime)

    site = runtime / "Lib" / "site-packages"
    site.mkdir(parents=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--target", str(site),
         "--python-version", "3.14", "--platform", "win_amd64",
         "--implementation", "cp", "--abi", "cp314", "--only-binary=:all:", "--no-compile",
         *packages, "pip"],
        check=True,
    )
    paths = ["python314.zip", ".", "Lib/site-packages"]
    if app_path:
        paths.append(app_path)
    paths.append("import site")
    (runtime / "python314._pth").write_text("\n".join(paths) + "\n", encoding="utf-8")
    (site / "sitecustomize.py").write_text(
        "import os, sys\n"
        "sys.path.append(os.getcwd())\n"
        "if sys.argv and os.path.isfile(sys.argv[0]):\n"
        "    sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))\n",
        encoding="utf-8",
    )
