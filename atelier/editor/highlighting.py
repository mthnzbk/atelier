"""Incremental, block-local Pygments highlighting with multiline state."""
import re
from bisect import bisect_right
from pygments import lex
from pygments.lexers import PythonLexer, MarkdownLexer, get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.token import String
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QTimer


FILE_LANGUAGES = {
    '.py': 'python', '.pyw': 'python', '.md': 'markdown', '.markdown': 'markdown',
    '.mdown': 'markdown', '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
    '.html': 'html', '.htm': 'html', '.css': 'css', '.js': 'javascript',
    '.mjs': 'javascript', '.cjs': 'javascript', '.toml': 'toml', '.sql': 'sql',
}
DOCUMENT_LEXERS = {'json', 'yaml', 'html', 'css', 'javascript', 'toml', 'sql'}


class Highlighter(QSyntaxHighlighter):
    scanner = re.compile(
        r'''(?P<triple>\"\"\"|\x27\x27\x27)|(?P<short>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(?P<comment>\#.*)''')

    def __init__(self, document):
        super().__init__(document)
        self.language = 'python'
        self.style = get_style_by_name('monokai')
        self.formats = {}
        self.style_identity = None
        self.python = PythonLexer(ensurenl=False, stripnl=False)
        self.markdown = MarkdownLexer(ensurenl=False, stripnl=False)
        self.highlighted_blocks = 0
        self.document_lexer = None
        self.document_tokens = []
        self.refresh_timer = QTimer(self, singleShot=True, interval=150)
        self.refresh_timer.timeout.connect(self.refresh_document_tokens)
        document.contentsChange.connect(self.schedule_document_tokens)

    def set_language(self, language):
        self.language = language
        self.refresh_timer.stop()
        self.document_tokens = []
        self.document_lexer = get_lexer_by_name(language) if language in DOCUMENT_LEXERS else None
        if self.document_lexer:
            self.refresh_document_tokens()
        else:
            self.rehighlight()

    def schedule_document_tokens(self, position, removed, added):
        if self.document_lexer and (removed or added):
            self.refresh_timer.start()

    def refresh_document_tokens(self):
        document = self.document()
        if not self.document_lexer or document is None:
            return
        source = document.toPlainText()
        lines = source.split('\n')
        starts = [0]
        for line in lines[:-1]:
            starts.append(starts[-1] + len(line) + 1)
        self.document_tokens = [(line, []) for line in lines]
        if len(source) <= 1_000_000 and len(lines) <= 20000:
            for offset, token, value in self.document_lexer.get_tokens_unprocessed(source):
                line_index = bisect_right(starts, offset) - 1
                column = offset - starts[line_index]
                for part in value.split('\n'):
                    if part and line_index < len(lines) and len(lines[line_index]) <= 20000:
                        start = len(lines[line_index][:column].encode('utf-16-le')) // 2
                        length = len(part.encode('utf-16-le')) // 2
                        self.document_tokens[line_index][1].append((start, length, token))
                    line_index += 1
                    column = 0
        self.rehighlight()

    def fmt(self, token):
        if self.style_identity is not self.style:
            self.style_identity = self.style
            self.formats.clear()
        if token not in self.formats:
            styled_token = token
            while not self.style.styles_token(styled_token):
                styled_token = styled_token.parent
            style = self.style.style_for_token(styled_token)
            fmt = QTextCharFormat()
            if style['color']:
                fmt.setForeground(QColor('#' + style['color']))
            if style['bold']:
                fmt.setFontWeight(QFont.Weight.Bold)
            fmt.setFontItalic(style['italic'])
            self.formats[token] = fmt
        return self.formats[token]

    def paint_tokens(self, text, offset=0, lexer=None):
        position = len(text[:offset].encode('utf-16-le')) // 2
        for token, value in lex(text[offset:], lexer or self.python):
            length = len(value.encode('utf-16-le')) // 2
            self.setFormat(position, length, self.fmt(token))
            position += length

    @staticmethod
    def closing(text, delimiter, start):
        while True:
            position = text.find(delimiter, start)
            if position < 0:
                return -1
            backslashes = len(text[:position]) - len(text[:position].rstrip('\\'))
            if backslashes % 2 == 0:
                return position
            start = position + 1

    def highlightBlock(self, text):
        self.highlighted_blocks += 1
        self.setCurrentBlockState(0)
        state = self.previousBlockState()
        if self.language == 'text' or len(text) > 20000 or self.document().blockCount() > 20000:
            return
        if self.document_lexer:
            index = self.currentBlock().blockNumber()
            if index < len(self.document_tokens):
                cached_text, tokens = self.document_tokens[index]
                if cached_text == text:
                    for start, length, token in tokens:
                        self.setFormat(start, length, self.fmt(token))
            return
        if self.language == 'markdown':
            match = re.match(r'^\s*(`{3,}|~{3,})', text)
            if state in (3, 4):
                if not match or (match[1][0] == '`') != (state == 3):
                    self.paint_tokens(text)
                    self.setCurrentBlockState(state)
                    return
            elif match:
                self.setCurrentBlockState(3 if match[1][0] == '`' else 4)
            self.paint_tokens(text, lexer=self.markdown)
            return
        start = 0
        if state in (1, 2):
            delimiter = "'''" if state == 1 else '"""'
            end = self.closing(text, delimiter, 0)
            if end < 0:
                self.setFormat(0, len(text.encode('utf-16-le')) // 2, self.fmt(String))
                self.setCurrentBlockState(state)
                return
            start = end + 3
            self.setFormat(0, len(text[:start].encode('utf-16-le')) // 2, self.fmt(String))
        while start < len(text):
            opener = None
            for match in self.scanner.finditer(text, start):
                if match.lastgroup == 'comment':
                    break
                if match.lastgroup == 'triple':
                    opener = match
                    break
            if opener is None:
                self.paint_tokens(text, start)
                break
            if opener.start() > start:
                segment = text[start:opener.start()]
                position = len(text[:start].encode('utf-16-le')) // 2
                for token, value in lex(segment, self.python):
                    length = len(value.encode('utf-16-le')) // 2
                    self.setFormat(position, length, self.fmt(token))
                    position += length
            end = self.closing(text, opener[0], opener.end())
            stop = len(text) if end < 0 else end + 3
            self.setFormat(len(text[:opener.start()].encode('utf-16-le')) // 2,
                           len(text[opener.start():stop].encode('utf-16-le')) // 2, self.fmt(String))
            if end < 0:
                self.setCurrentBlockState(1 if opener[0] == "'''" else 2)
                return
            start = stop
