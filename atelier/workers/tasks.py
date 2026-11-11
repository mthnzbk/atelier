"""One JSON request/result per process, without Qt or a UI event loop."""
import ast
import base64
import difflib
import io
import json
import sys
import tokenize
from pathlib import Path
from atelier.projects.scan import files, read_source
from atelier.search.patterns import allowed_file, pattern


def search(job):
    matcher = pattern(
        job['query'], job.get(
            'regex', False), job.get(
            'whole', False), job.get(
                'case', False))
    found = []
    for path in files(job['root']):
        if not allowed_file(path, job.get('globs', '')):
            continue
        try:
            source = read_source(path)
        except (OSError, UnicodeError, SyntaxError):
            continue
        for line, text in enumerate(source.splitlines()):
            for match in matcher.finditer(text):
                found.append((str(path), line, match.start(), text[:300]))
                if len(found) >= 5000:
                    return found
    return found


def replace(job):
    matcher = pattern(
        job['query'], job.get(
            'regex', False), job.get(
            'whole', False), job.get(
                'case', False))
    prepared, size = [], 0
    for path in files(job['root']):
        if not allowed_file(path, job.get('globs', '')):
            continue
        try:
            raw = path.read_bytes()
            encoding = tokenize.detect_encoding(
                io.BytesIO(raw).readline)[0] if path.suffix.lower() in (
                '.py', '.pyw') else 'utf-8'
            text = raw.decode(encoding).replace('\r\n', '\n').replace('\r', '\n')
            updated, count = matcher.subn(job['replacement'] if job.get(
                'regex') else lambda _: job['replacement'], text)
        except (OSError, UnicodeError, SyntaxError):
            continue
        if not count:
            continue
        size += len(raw) + len(updated.encode('utf-8'))
        if len(prepared) >= 100 or size > 20_000_000:
            raise ValueError(
                'Değiştirme önizlemesi sınırı aşıldı (100 dosya / 20 MB). Dosya filtresini daraltın.')
        prepared.append(
            dict(
                path=str(path),
                original=base64.b64encode(raw).decode('ascii'),
                updated=updated,
                count=count))
    return prepared


def symbols(job):
    rows, visited, skipped = [], 0, 0
    overlays = job.get('overlays', {})
    paths = dict.fromkeys(
        [*(str(path) for path in files(job['root'], {'.py', '.pyw'}, 10000)), *overlays])
    for filename in paths:
        visited += 1
        if visited > 3000 or len(rows) >= 10000:
            break
        try:
            tree = ast.parse(
                overlays[filename] if filename in overlays else read_source(
                    Path(filename)))
        except (SyntaxError, UnicodeError, OSError, RecursionError):
            skipped += 1
            continue
        stack = [(tree, '')]
        while stack and len(rows) < 10000:
            node, scope = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = scope + node.name
                rows.append(dict(name=name, path=filename, line=node.lineno - 1, character=node.col_offset,
                                 kind='class' if isinstance(node, ast.ClassDef) else 'def'))
                scope = name + '.'
            stack.extend((child, scope) for child in reversed(list(ast.iter_child_nodes(node))))
    return dict(rows=rows, skipped=skipped, limited=visited > 3000 or len(rows) >= 10000)


def save(job):
    source, options = job['source'], job['options']
    if options.get('format_web_on_save'):
        from atelier.languages.formatting import format_web
        source = format_web(source, job['language'])
    if job['python']:
        if options.get('save_imports'):
            from rope.base.libutils import get_string_module
            from rope.refactor.importutils import ImportTools
            from atelier.languages.rope_project import DirectoryProject
            root, path = Path(job['root']), Path(job['path'])
            if root not in path.parents:
                root = path.parent
            project = DirectoryProject(str(root), ropefolder=None)
            try:
                resource = project.get_file(path.relative_to(root).as_posix())
                module = get_string_module(project, source, resource)
                source = ImportTools(project).organize_imports(module, unused=False, selfs=False)
            finally:
                project.close()
        if options.get('format_on_save'):
            import autopep8
            source = autopep8.fix_code(source, options={'max_line_length': 100})
    if options.get('save_trim'):
        protected = set()
        if job['python']:
            try:
                for token in tokenize.generate_tokens(io.StringIO(source).readline):
                    if tokenize.tok_name[token.type] in (
                            'STRING', 'FSTRING_MIDDLE', 'TSTRING_MIDDLE'):
                        protected.update(range(token.start[0], token.end[0]))
            except (tokenize.TokenError, SyntaxError):
                # An unfinished literal may extend to the end of the file.
                protected.update(range(1, source.count('\n') + 2))
        lines = []
        for index, line in enumerate(source.splitlines(keepends=True), 1):
            if index in protected:
                lines.append(line)
                continue
            text = line.rstrip('\r\n')
            ending = line[len(text):]
            suffix = '  ' if job.get('markdown') and text.endswith('  ') else ''
            lines.append(text.rstrip(' \t') + suffix + ending)
        source = ''.join(lines)
    if options.get('save_final_newline') and source and not source.endswith('\n'):
        source += '\n'
    if source == job['source']:
        return []

    def lines(text):
        parts = text.split('\n')
        return [line + '\n' for line in parts[:-1]] + parts[-1:]
    before, after = lines(job['source']), lines(source)
    return [dict(range=dict(start=dict(line=i1, character=0), end=dict(line=i2, character=0)),
                 newText=''.join(after[j1:j2]))
            for kind, i1, i2, j1, j2 in difflib.SequenceMatcher(None, before, after).get_opcodes() if kind != 'equal']


def validate_document(job):
    from atelier.languages.validation import validate
    return validate(job['source'], job['language'], job['filename'])


def main():
    try:
        job = json.load(sys.stdin)
        result = {'search': search, 'replace': replace, 'symbols': symbols,
                  'save': save, 'validate': validate_document}[job['operation']](job)
        print(json.dumps(dict(result=result), ensure_ascii=True))
    except Exception as error:
        print(json.dumps(dict(error=str(error)), ensure_ascii=True))


if __name__ == '__main__':
    main()
