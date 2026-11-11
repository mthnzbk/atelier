"""Small editable templates with numbered Tab stops."""
import re
from PySide6.QtGui import QTextCursor

TEMPLATES = {
    'def': 'def ${1:function_name}(${2:parameters}):\n    ${0:pass}',
    'class': 'class ${1:ClassName}:\n    def __init__(self${2:, parameters}):\n        ${0:pass}',
    'for': 'for ${1:item} in ${2:items}:\n    ${0:pass}',
    'if': 'if ${1:condition}:\n    ${0:pass}',
    'while': 'while ${1:condition}:\n    ${0:pass}',
    'try': 'try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:error}:\n    ${0:pass}',
    'with': 'with ${1:open("file.txt")} as ${2:file}:\n    ${0:pass}',
    'main': 'if __name__ == "__main__":\n    ${0:pass}',
    'test': 'def test_${1:behavior}():\n    assert ${0:True}',
    'mdlink': '[${1:label}](${0:https://example.com})',
}

HTML_TEMPLATES = {
    'html5': ('<!doctype html>\n<html lang="${1:tr}">\n'
              '  <head>\n    <meta charset="utf-8">\n'
              '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
              '    <title>${2:Başlık}</title>\n  </head>\n'
              '  <body>\n    ${0:}\n  </body>\n</html>'),
    'a': '<a href="${1:#}">${0:Bağlantı}</a>',
    'img': '<img src="${1:image.png}" alt="${0:Açıklama}">',
    'link': '<link rel="stylesheet" href="${0:style.css}">',
    'form': '<form action="${1:/}" method="${2:post}">\n  ${0:}\n</form>',
    'input': '<input type="${1:text}" name="${0:field}">',
    'table': '<table>\n  <thead><tr><th>${1:Başlık}</th></tr></thead>\n  <tbody><tr><td>${0:Değer}</td></tr></tbody>\n</table>',
    'script': '<script src="${0:app.js}"></script>',
}


def templates_for(language):
    if language == 'html':
        return HTML_TEMPLATES
    if language == 'python':
        return {key: value for key, value in TEMPLATES.items() if key != 'mdlink'}
    if language == 'markdown':
        return {'mdlink': TEMPLATES['mdlink']}
    return {}


def utf16(text):
    return len(text.encode('utf-16-le')) // 2


class SnippetSession:
    def __init__(self, editor):
        self.editor = editor
        self.stops = []
        self.index = -1

    def expand(self, key=None):
        cursor = self.editor.textCursor()
        before = cursor.block().text().encode(
            'utf-16-le')[:cursor.positionInBlock() * 2].decode('utf-16-le', 'ignore')
        prefix = re.search(r'\w*$', before).group()
        key = key or prefix
        template = templates_for(self.editor.language).get(key)
        if template is None or (self.editor.language == 'html' and before.endswith('<' + prefix)):
            return False
        return self.insert(template, prefix)

    def insert(self, template, prefix, consume=0):
        cursor = self.editor.textCursor()
        before = cursor.block().text().encode(
            'utf-16-le')[:cursor.positionInBlock() * 2].decode('utf-16-le', 'ignore')
        indent = re.match(r'[ \t]*', before).group()
        template = template.replace('\n', '\n' + indent)
        pieces, fields = [], []
        offset = 0
        for match in re.finditer(r'\$\{(\d+):([^}]*)\}', template):
            pieces.append(template[offset:match.start()])
            start = utf16(''.join(pieces))
            pieces.append(match[2])
            fields.append((int(match[1]), start, utf16(''.join(pieces))))
            offset = match.end()
        pieces.append(template[offset:])
        end = cursor.position() + consume
        cursor.setPosition(cursor.position() - utf16(prefix))
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        base = cursor.selectionStart()
        cursor.beginEditBlock()
        cursor.insertText(''.join(pieces))
        cursor.endEditBlock()
        self.stops = []
        for number, start, end in sorted(fields, key=lambda field: (field[0] == 0, field[0])):
            a, b = QTextCursor(self.editor.document()), QTextCursor(self.editor.document())
            a.setPosition(base + start)
            a.setKeepPositionOnInsert(True)
            b.setPosition(base + end)
            self.stops.append((number, a, b))
        self.index = -1
        self.advance()
        return True

    def advance(self, backwards=False):
        if not self.stops:
            return False
        self.index = max(0, self.index - 1) if backwards else self.index + 1
        if self.index >= len(self.stops):
            self.cancel()
            return False
        number, a, b = self.stops[self.index]
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(a.position())
        cursor.setPosition(b.position(), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        if number == 0:
            self.cancel()
        return True

    def cancel(self):
        self.stops = []
        self.index = -1
