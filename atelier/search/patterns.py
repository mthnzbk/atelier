import fnmatch
import re


def pattern(query, regex=False, whole=False, case=False):
    source = query if regex else re.escape(query)
    if whole:
        source = r'(?<!\w)(?:' + source + r')(?!\w)'
    return re.compile(source, re.MULTILINE | (0 if case else re.IGNORECASE))


def allowed_file(path, globs):
    patterns = [part.strip() for part in globs.split(',') if part.strip()]
    return not patterns or any(fnmatch.fnmatch(path.name, item)
                               or fnmatch.fnmatch(path.as_posix(), item) for item in patterns)


def fuzzy_score(query, name):
    query, name = query.casefold().replace(' ', ''), name.casefold()
    if not query:
        return 0
    if query in name:
        return 1000 - name.index(query) - len(name) * 0.01
    position, score = -1, 0
    for char in query:
        next_position = name.find(char, position + 1)
        if next_position < 0:
            return None
        score += 10 if next_position == position + 1 else 1
        position = next_position
    return score - len(name) * 0.01
