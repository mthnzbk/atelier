"""Construct an index-only patch for selected working-tree lines."""
import difflib
import json


def selected_patch(base, working, relative_path, first_line, last_line):
    old = base.splitlines(keepends=True)
    new = working.splitlines(keepends=True)
    selected = []
    for tag, a, b, c, d in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if tag == 'equal':
            selected.extend(old[a:b])
            continue
        hits = max(c, first_line) < min(d, last_line + 1)
        if tag == 'delete':
            hits = first_line <= c <= last_line + 1
        if not hits:
            selected.extend(old[a:b])
        elif tag == 'insert':
            selected.extend(new[max(c, first_line):min(d, last_line + 1)])
        elif tag == 'replace' and b - a == d - c:
            selected.extend(new[c + i] if first_line <= c + i <=
                            last_line else old[a + i] for i in range(b - a))
        else:
            # Unequal replacements/deletions are one inseparable change group.
            selected.extend(new[c:d])
    if selected == old:
        return ''
    # Git accepts quoted UTF-8 pathnames in unified diff headers.
    before = json.dumps('a/' + relative_path, ensure_ascii=False)
    after = json.dumps('b/' + relative_path, ensure_ascii=False)
    lines = list(difflib.unified_diff(old, selected, fromfile=before, tofile=after, n=3))
    output = []
    for line in lines:
        if line.endswith('\n'):
            output.append(line)
        else:
            output.extend([line + '\n', '\\ No newline at end of file\n'])
    return ''.join(output)
