"""Decode editor files and preserve their on-disk line separators."""
from dataclasses import dataclass
from difflib import SequenceMatcher
from io import BytesIO
import codecs
import re
import tokenize


ENCODINGS = {'UTF-8': 'utf-8', 'UTF-8 BOM': 'utf-8-sig',
             'Windows-1254': 'cp1254', 'Windows-1252': 'cp1252'}
NEWLINES = {'LF': '\n', 'CRLF': '\r\n', 'CR': '\r'}
PYTHON_SUFFIXES = {'.py', '.pyw', '.pyi'}
SEPARATOR = re.compile(r'\r\n|\r|\n')
COOKIE = re.compile(r'^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)', re.ASCII)


@dataclass(frozen=True)
class TextFormat:
    encoding: str = 'utf-8'
    newline: str = '\n'
    mixed: tuple[str, ...] = ()

    @property
    def encoding_label(self):
        return next((label for label, name in ENCODINGS.items() if name == self.encoding),
                    self.encoding.upper())

    @property
    def newline_label(self):
        if self.mixed:
            return 'Karışık'
        return next(label for label, value in NEWLINES.items() if value == self.newline)


def line_format(text, encoding, fallback='\n'):
    crlf = text.count('\r\n')
    counts = {ending: count for ending, count in (
        ('\r\n', crlf), ('\n', text.count('\n') - crlf), ('\r', text.count('\r') - crlf)
    ) if count}
    return TextFormat(encoding, max(counts, key=counts.__getitem__) if counts else fallback,
                      tuple(SEPARATOR.findall(text)) if len(counts) > 1 else ())


def read_text_file(path, encoding=None):
    if path.stat().st_size > 25_000_000:
        raise ValueError('25 MB üzerindeki dosyalar açılamıyor.')
    data = path.read_bytes()
    if encoding is None:
        if path.suffix.lower() in PYTHON_SUFFIXES:
            header = re.match(rb'(?:[^\r\n]*(?:\r\n|\r|\n|$)){1,2}', data).group()
            header = header.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            encoding, _ = tokenize.detect_encoding(BytesIO(header).readline)
        else:
            encoding = 'utf-8-sig' if data.startswith(codecs.BOM_UTF8) else 'utf-8'
    encoding = codecs.lookup(encoding).name
    text = data.decode(encoding)
    return SEPARATOR.sub('\n', text), line_format(text, encoding)


def python_encoding(text, encoding, converting):
    lines = text.split('\n', 2)
    cookie = COOKIE.match(lines[0])
    index = 0
    if not cookie and len(lines) > 1 and (
            not lines[0].strip() or lines[0].lstrip().startswith('#')):
        index = 1
        cookie = COOKIE.match(lines[index])
    if converting:
        if cookie:
            start, end = cookie.span(1)
            name = 'utf-8' if encoding == 'utf-8-sig' else encoding
            lines[index] = lines[index][:start] + name + lines[index][end:]
            text = '\n'.join(lines)
        elif encoding not in ('utf-8', 'utf-8-sig'):
            comment = f'# coding: {encoding}\n'
            if text.startswith('#!') and '\n' in text:
                first, rest = text.split('\n', 1)
                text = first + '\n' + comment + rest
            else:
                text = comment + text
    elif cookie:
        declared = codecs.lookup(cookie.group(1)).name
        if encoding != 'utf-8-sig' or declared != 'utf-8':
            encoding = declared
    return text, encoding


def encode_text_file(path, text, previous, text_format, *, converting=False):
    encoding = text_format.encoding
    if path.suffix.lower() in PYTHON_SUFFIXES:
        text, declared = python_encoding(text, encoding, converting)
        if converting or declared != python_encoding(previous, encoding, False)[1]:
            encoding = declared
    if not text_format.mixed:
        physical = text.replace('\n', text_format.newline)
    else:
        before, after = previous.split('\n'), text.split('\n')
        endings = [text_format.newline] * (len(after) - 1)
        for tag, a, b, c, d in SequenceMatcher(None, before, after).get_opcodes():
            if tag in ('equal', 'replace'):
                for old, new in zip(range(a, b), range(c, d)):
                    if old < len(text_format.mixed) and new < len(endings):
                        endings[new] = text_format.mixed[old]
        physical = ''.join(line + ending for line, ending in zip(after, [*endings, '']))
    return physical.encode(encoding), text, line_format(physical, encoding, text_format.newline)
