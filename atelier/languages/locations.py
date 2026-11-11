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


def definition_target(result):
    locations = result if isinstance(result, list) else [result]
    for location in locations:
        if not isinstance(location, dict):
            continue
        uri = location.get('uri') or location.get('targetUri')
        region = location.get('range') or location.get('targetSelectionRange')
        if not isinstance(uri, str) or not isinstance(region, dict):
            continue
        position = region.get('start')
        if not isinstance(position, dict) or not all(
                isinstance(position.get(key), int) and position[key] >= 0 for key in ('line', 'character')):
            continue
        try:
            if urlparse(uri).scheme == 'file':
                return uri_path(uri), position
        except (OSError, ValueError):
            continue
    return None
