"""Find project notes in comment tokens without executing project code."""
from bisect import bisect_right
from io import StringIO
import re
import tokenize

from atelier.projects.scan import files
from atelier.storage.text_format import PYTHON_SUFFIXES, read_text_file


SUFFIXES = PYTHON_SUFFIXES | {'.js', '.mjs', '.cjs', '.css', '.html', '.htm',
                            '.yaml', '.yml', '.toml', '.sql'}
NOTE = re.compile(r'\b(TODO|FIXME)\b[ \t]*:?[ \t]*(.*)', re.IGNORECASE)
LIMIT = 3000


def comments(path, source):
    if path.suffix.lower() in PYTHON_SUFFIXES:
        try:
            for token in tokenize.generate_tokens(StringIO(source).readline):
                if token.type == tokenize.COMMENT:
                    yield token.start[0] - 1, token.start[1], token.string
        except (tokenize.TokenError, IndentationError):
            pass
        return

    from pygments.lexers import get_lexer_for_filename
    from pygments.token import Comment
    from pygments.util import ClassNotFound

    try:
        lexer = get_lexer_for_filename(path.name)
    except ClassNotFound:
        return
    starts = [0, *(match.end() for match in re.finditer('\n', source))]
    for offset, token, text in lexer.get_tokens_unprocessed(source):
        if token not in Comment:
            continue
        line = bisect_right(starts, offset) - 1
        column = offset - starts[line]
        for fragment in text.split('\n'):
            yield line, column, fragment
            line += 1
            column = 0


def project_notes(job):
    rows = []
    overlays = job.get('overlays', {})
    for path in files(job['root'], SUFFIXES):
        filename = str(path)
        try:
            source = overlays[filename] if filename in overlays else read_text_file(path)[0]
        except (OSError, ValueError, SyntaxError, LookupError):
            continue
        if not NOTE.search(source):
            continue
        lines = source.split('\n')
        for line, column, comment in comments(path, source):
            match = NOTE.search(comment)
            if not match:
                continue
            prefix = lines[line][:column + match.start()]
            message = re.sub(r'\s*(?:\*/|-->)\s*$', '', match[2]).strip()
            rows.append(dict(path=filename, line=line, character=len(prefix.encode('utf-16-le')) // 2,
                             kind=match[1].upper(), text=message[:400]))
            if len(rows) >= LIMIT:
                return dict(rows=rows, limited=True)
    return dict(rows=rows, limited=False)
