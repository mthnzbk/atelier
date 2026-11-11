import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse


def uri_path(uri):
    parsed = urlparse(uri)
    path = unquote(parsed.path)
    if os.name == 'nt' and re.match(r'^/[A-Za-z]:', path):
        path = path[1:]
    if parsed.netloc:
        path = '//' + parsed.netloc + path
    return Path(path).resolve()
