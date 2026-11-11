"""Offline Material Design Icons, bundled by QtAwesome."""
import os
os.environ.setdefault('QT_API', 'pyside6')
import qtawesome as qta

NAMES = {
    'merge_conflicts':'source-merge', 'project_symbols':'code-tags', 'breakpoints':'debug-step-over',
    'packages':'package-variant-closed',
    'history':'history','profiles':'play-circle-outline','imports':'import','missing_import':'import',
    'extract_method':'code-braces','extract_variable':'code-braces','signature':'information-outline',
    'new': 'file-plus-outline', 'open': 'file-document-outline', 'project': 'folder-open-outline',
    'save': 'content-save-outline', 'save_as': 'content-save-edit-outline', 'save_all': 'content-save-all-outline',
    'close': 'close', 'undo': 'undo', 'redo': 'redo', 'comment': 'comment-text-outline',
    'find': 'magnify', 'replace': 'find-replace', 'search': 'folder-search-outline',
    'complete': 'code-braces', 'definition': 'code-tags', 'rename': 'rename-box',
    'format': 'format-align-left', 'format_save': 'content-save-cog-outline',
    'python': 'language-python', 'run': 'play', 'debug': 'bug-outline', 'continue': 'play-circle-outline',
    'next': 'debug-step-over', 'step': 'debug-step-into', 'out': 'debug-step-out', 'pause': 'pause',
    'stop': 'stop', 'breakpoint': 'circle-outline', 'condition': 'debug-step-over',
    'split': 'view-split-vertical', 'sidebar': 'dock-left', 'bottom': 'dock-bottom',
    'settings': 'cog-outline', 'git': 'git', 'git_init': 'source-repository',
    'terminal': 'console', 'tests': 'test-tube', 'palette': 'keyboard-outline',
    'recovery': 'backup-restore', 'fold': 'unfold-less-horizontal', 'unfold': 'unfold-more-horizontal',
    'minimap': 'map-outline', 'refs': 'file-search-outline', 'symbols': 'format-list-bulleted',
    'back': 'arrow-left', 'forward': 'arrow-right', 'project_settings': 'folder-cog-outline',
    'update': 'update', 'trash': 'delete-outline', 'folder_new': 'folder-plus-outline',
    'stage_lines': 'source-commit',
}


def icon(key, color='#9cb5e8'):
    name = NAMES.get(key, 'dots-horizontal')
    try:
        return qta.icon('mdi6.' + name, color=color)
    except Exception:
        return qta.icon('mdi6.dots-horizontal', color=color)


def for_text(text, color='#9cb5e8'):
    text = text.casefold()
    for needle, key in [('kaydet', 'save'), ('temizle', 'trash'), ('yenile', 'git'), ('hazırla', 'git'),
        ('çalıştır', 'run'), ('durdur', 'stop'), ('terminal', 'terminal'), ('commit', 'git'),
        ('git', 'git'), ('keşfet', 'search'), ('kaldır', 'trash'), ('önizle', 'open'), ('aktar', 'save_as'),
        ('yükle', 'open'), ('karşılaştır', 'refs'), ('koşul', 'condition'), ('izle', 'debug')]:
        if needle in text:
            return icon(key, color)
    return icon('complete', color)
