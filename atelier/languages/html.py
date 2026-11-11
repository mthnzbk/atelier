"""Local HTML tag, attribute and snippet suggestions."""
import re
from atelier.editor.snippets import HTML_TEMPLATES, utf16


VOID = set('area base br col embed hr img input link meta param source track wbr'.split())
TAGS = VOID | set('''
    a abbr address article aside audio b blockquote body button canvas caption cite code
    colgroup data datalist dd del details dfn dialog div dl dt em fieldset figcaption figure
    footer form h1 h2 h3 h4 h5 h6 head header hgroup html i iframe ins kbd label legend
    li main map mark menu meter nav noscript ol optgroup option output p picture pre
    progress q rp rt ruby s samp script search section select slot small span strong
    style sub summary sup table tbody td template textarea tfoot th thead time title
    tr u ul var video
'''.split())
GLOBAL_ATTRIBUTES = 'class id style title lang dir hidden tabindex role aria-label'.split()
ATTRIBUTES = {
    'a': 'href target rel download', 'img': 'src alt width height loading srcset sizes',
    'input': 'type name value placeholder required disabled checked min max step',
    'form': 'action method enctype autocomplete', 'button': 'type name value disabled',
    'script': 'src type defer async', 'link': 'href rel media type', 'label': 'for',
    'meta': 'name content charset http-equiv', 'textarea': 'name rows cols placeholder required',
}
BOOLEAN = set('hidden disabled checked required multiple readonly autofocus defer async download'.split())


def completion_context(cursor):
    block = cursor.block()
    line = block.text().encode('utf-16-le')
    position = cursor.positionInBlock() * 2
    prefix = [line[:position].decode('utf-16-le', 'ignore')]
    for _ in range(20):
        block = block.previous()
        if not block.isValid() or len(block.text()) > 20000:
            break
        prefix.append(block.text())
    return '\n'.join(reversed(prefix)), line[position:].decode('utf-16-le', 'ignore')


def suggestions(before, after):
    if before.rfind('<!--') > before.rfind('-->'):
        return
    tag = re.search(r'<(/?)([\w:-]*)$', before)
    if tag:
        closing, prefix = tag.groups()
        for name in sorted(TAGS - VOID if closing else TAGS):
            if not name.startswith(prefix.lower()):
                continue
            suffix = re.match(r'[\w:-]*', after)[0]
            remaining = after[len(suffix):]
            consume = utf16(suffix)
            if re.match(r'^(?:\s+[^<>]*|/?)>', remaining):
                template = f'<{closing}{name}'
            elif closing:
                template = f'</{name}>'
            elif name in VOID or re.match(r'</' + re.escape(name) + r'\s*>', remaining, re.I):
                template = f'<{name}>'
            else:
                template = f'<{name}>' + '${0:}' + f'</{name}>'
            yield name, template, tag[0], consume
        return
    attribute = re.search(r'<([a-z][\w:-]*)\s+([^<>]*)$', before, re.I)
    if attribute:
        name, body = attribute.groups()
        complete_values = re.sub(r"""(?:"[^"]*"|'[^']*')""", '', body)
        if '"' in complete_values or "'" in complete_values:
            return
        match = re.search(r'(?:^|\s)([\w:-]*)$', body)
        if not match:
            return
        prefix = match[1]
        used = set(re.findall(r'\b([\w:-]+)\s*=', complete_values.lower()))
        for key in sorted(set(GLOBAL_ATTRIBUTES + ATTRIBUTES.get(name.lower(), '').split()) - used):
            if key.startswith(prefix.lower()):
                template = key if key in BOOLEAN or after.lstrip().startswith('=') else key + \
                    '="${0:}"'
                yield key, template, prefix, 0
        return
    prefix = re.search(r'\w*$', before).group()
    for key, template in HTML_TEMPLATES.items():
        if key.startswith(prefix.lower()):
            yield key + ' · şablon', template, prefix, 0
