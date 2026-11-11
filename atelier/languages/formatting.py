"""Format source with Python libraries, leaving file writes to the editor."""
import re

from atelier.languages.validation import validate


LANGUAGES = {'html', 'css', 'javascript', 'json'}


def format_json(source):
    if problems := validate(source, 'json', ''):
        error = problems[0]
        line = error['range']['start']['line'] + 1
        raise ValueError(f'JSON, satır {line}: {error["message"]}')
    # Whitespace-only rewrite preserves duplicate keys and exact number literals.
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[{}\[\],:]|[^\s{}\[\],:"]+', source)
    result = []
    depth = 0
    for index, token in enumerate(tokens):
        if token in ('{', '['):
            result.append(token)
            depth += 1
            if tokens[index + 1] not in ('}', ']'):
                result.append('\n' + '  ' * depth)
        elif token in ('}', ']'):
            depth -= 1
            if tokens[index - 1] not in ('{', '['):
                result.append('\n' + '  ' * depth)
            result.append(token)
        elif token == ',':
            result.append(',\n' + '  ' * depth)
        elif token == ':':
            result.append(': ')
        else:
            result.append(token)
    return ''.join(result) + '\n'


def format_web(source, language):
    if language == 'json':
        return format_json(source)
    try:
        if language == 'html':
            from djhtml.modes import DjHTML
            return DjHTML(source).indent(2)
        if language == 'css':
            import cssbeautifier as beautifier
        elif language == 'javascript':
            import jsbeautifier as beautifier
        else:
            raise ValueError(f'Desteklenmeyen biçimlendirme dili: {language}')
    except ModuleNotFoundError as error:
        raise ValueError(
            'Biçimlendiricileri kurmak için python -m pip install -r requirements.txt çalıştırın.') from error
    options = beautifier.default_options()
    options.indent_size = 2
    options.end_with_newline = True
    return beautifier.beautify(source, options)
