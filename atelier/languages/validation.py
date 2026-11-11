"""Validate structured documents without executing YAML tags."""
import json
import re

from atelier.projects.config import ConfigError, FILENAME, tomllib, validate_project_config


LANGUAGES = {'json', 'yaml', 'toml'}


def config_location(lines, field):
    section = ''
    fallback = (0, 0)
    depth = 0
    for index, line in enumerate(lines):
        header = re.match(r'^\s*\[([^\]]+)\]', line)
        if header:
            section = re.sub(r'\s*\.\s*', '.', header[1]).replace('"', '').replace("'", '')
            if (field == section or field.startswith(section + '.')) and len(section) > depth:
                fallback, depth = (index, header.start(1)), len(section)
            continue
        key = re.match(r"""^\s*(?:['"]([^'"]+)['"]|([\w.-]+))\s*=""", line)
        if key:
            group = 1 if key[1] is not None else 2
            name = '.'.join(filter(None, (section, key[group])))
            if field == name or field.startswith(name + '.'):
                return index, key.start(group)
    return fallback


def validate(source, language, filename):
    lines = source.split('\n')
    try:
        if language == 'json':
            def reject_constant(value):
                tokens = re.finditer(r'"(?:\\.|[^"\\])*"|(-?Infinity|NaN)', source)
                position = next((token.start() for token in tokens if token[1] == value), 0)
                raise json.JSONDecodeError(
                    f'{value} geçerli bir JSON değeri değil', source, position)
            json.loads(source, parse_constant=reject_constant)
        elif language == 'yaml':
            import yaml
            try:
                for _ in yaml.compose_all(source, Loader=yaml.SafeLoader):
                    pass
            except yaml.YAMLError as error:
                mark = getattr(error, 'problem_mark', None)
                return diagnostic(lines, mark.line if mark else 0, mark.column if mark else 0,
                                  getattr(error, 'problem', None) or str(error))
        elif language == 'toml':
            data = tomllib.loads(source)
            if filename.casefold() == FILENAME:
                validate_project_config(data)
    except json.JSONDecodeError as error:
        return diagnostic(lines, error.lineno - 1, error.colno - 1, error.msg)
    except tomllib.TOMLDecodeError as error:
        location = re.search(r'\(at line (\d+), column (\d+)\)$', str(error))
        line = getattr(error, 'lineno', None) or (int(location[1]) if location else len(lines))
        column = getattr(error, 'colno', None) or (
            int(location[2]) if location else len(lines[-1]) + 1)
        return diagnostic(lines, line - 1, column - 1, getattr(error, 'msg', str(error)))
    except ConfigError as error:
        line, column = config_location(lines, error.field)
        return diagnostic(lines, line, column, str(error))
    except RecursionError:
        return diagnostic(lines, 0, 0, 'İç içe yapı doğrulama sınırını aşıyor.')
    return []


def diagnostic(lines, line, column, message):
    line = max(0, min(line, len(lines) - 1))
    text = lines[line]
    column = min(max(column, 0), len(text))
    start = len(text[:column].encode('utf-16-le')) // 2
    end = len(text[:column + 1].encode('utf-16-le')) // 2
    return [{'severity': 1, 'message': message, 'range': {
        'start': {'line': line, 'character': start}, 'end': {'line': line, 'character': end}}}]
