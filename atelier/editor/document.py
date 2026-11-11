"""Shared document state and editor views."""
import uuid
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QTextCursor, QTextCharFormat
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QComboBox, QTextEdit, QSizePolicy
from atelier.editor.widget import Editor
from atelier.ui.markdown import MarkdownPreview
from atelier.languages.validation import LANGUAGES as VALIDATED_LANGUAGES
from atelier.storage.text_format import TextFormat


class Document(QWidget):
    def __init__(self, window, path=None, text='', text_format=None):
        super().__init__()
        self.window = window
        self.path = Path(path).resolve() if path else None
        self.text_format = text_format or TextFormat()
        self.large_file = len(text) > 1_000_000 or text.count(
            '\n') >= 20000 or any(len(line) > 20000 for line in text.split('\n'))
        self.save_worker = None
        self.uri = (self.path or window.root / f'__untitled_{uuid.uuid4().hex}.py').as_uri()
        self.version = 0
        self.synced = None
        self.diagnostics = []
        self.breakpoints = set()
        self.breakpoint_cursors = {}
        self.breakpoint_conditions = {}
        self.editors = []
        self.active_editor = None
        self.loading = True
        self.external_pending = False
        self.saved_text = text
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.breadcrumb = QLabel()
        self.breadcrumb.setObjectName('breadcrumb')
        self.breadcrumb.setTextFormat(Qt.TextFormat.PlainText)
        self.breadcrumb.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.breadcrumb.setFixedHeight(27)
        layout.addWidget(self.breadcrumb)
        self.external_bar = QWidget()
        external_layout = QHBoxLayout(self.external_bar)
        self.external_label = QLabel('Dosya dışarıda değişti.')
        external_layout.addWidget(self.external_label, 1)
        window.button(external_layout, 'Yeniden yükle', lambda: window.reload_document(self))
        window.button(external_layout, 'Karşılaştır', lambda: window.compare_external(self))
        window.button(external_layout, 'Yerel içeriği tut', self.keep_external_local)
        layout.addWidget(self.external_bar)
        self.external_bar.hide()
        self.markdown_bar = QWidget()
        markdown_layout = QHBoxLayout(self.markdown_bar)
        markdown_layout.setContentsMargins(8, 3, 8, 3)
        markdown_layout.addWidget(QLabel('MARKDOWN'))
        self.markdown_mode = QComboBox()
        self.markdown_mode.addItems(['Kaynak', 'Kaynak + Önizleme', 'Önizleme', 'HTML kaynağı'])
        self.markdown_mode.setCurrentIndex(1)
        markdown_layout.addWidget(self.markdown_mode)
        markdown_layout.addStretch()
        window.button(markdown_layout, 'HTML dışa aktar', lambda: window.export_markdown(self))
        layout.addWidget(self.markdown_bar)
        self.content_split = QSplitter()
        self.splitter = QSplitter()
        self.content_split.addWidget(self.splitter)
        self.preview = MarkdownPreview()
        self.content_split.addWidget(self.preview)
        self.content_split.setSizes([650, 500])
        layout.addWidget(self.content_split, 1)
        self.markdown_timer = QTimer(self, interval=220, singleShot=True)
        self.markdown_timer.timeout.connect(self.render_markdown)
        self.markdown_mode.currentIndexChanged.connect(self.update_markdown_mode)
        self.timer = QTimer(self, singleShot=True, interval=250)
        self.timer.timeout.connect(lambda: window.sync_document(self))
        self.completion_timer = QTimer(self, singleShot=True, interval=window.completion_delay)
        self.completion_timer.timeout.connect(lambda: window.complete(self))
        # Qt can still be updating text layout when it emits cursor and content signals.
        self.diagnostics_timer = QTimer(self, singleShot=True)
        self.diagnostics_timer.timeout.connect(self.paint_diagnostics)
        self.validation_worker = None
        self.edit_generation = 0
        self.validation_timer = QTimer(self, singleShot=True, interval=300)
        self.validation_timer.timeout.connect(lambda: window.queue_validation(self))
        editor = self.add_view()
        editor.setPlainText(text)
        editor.document().setModified(False)
        editor.document().contentsChange.connect(self.changed)
        editor.document().modificationChanged.connect(lambda _: window.refresh_tabs())
        self.loading = False
        self.update_breadcrumb()
        self.update_language()

    def update_breadcrumb(self):
        path = self.path
        if path and path.is_relative_to(self.window.root):
            text = '  /  '.join(path.relative_to(self.window.root).parts)
        else:
            text = str(path or 'Adsız Python dosyası')
        self.breadcrumb.setText(text)
        self.breadcrumb.setToolTip(str(path or ''))

    def update_language(self):
        from atelier.editor.highlighting import FILE_LANGUAGES
        suffix = self.path.suffix.lower() if self.path else '.py'
        self.language = FILE_LANGUAGES.get(suffix, 'text')
        if self.language != 'python':
            self.diagnostics = []
        for editor in self.editors:
            editor.language = self.language
            self.window.set_editor_indentation(editor)
            editor.snippet_session.cancel()
            editor.structure.language = self.language
            editor.structure.source = None
            editor.structure.rebuild()
        self.editor.highlighter.set_language(self.language)
        self.validation_timer.stop()
        if self.language in VALIDATED_LANGUAGES and not self.large_file:
            self.validation_timer.start()
        self.markdown_bar.setVisible(self.language == 'markdown' and not self.large_file)
        self.update_markdown_mode()
        self.paint_diagnostics()

    def keep_external_local(self):
        self.external_bar.hide()
        # Explicitly keeping an older local copy must also protect it on close.
        self.editor.document().setModified(True)

    def render_markdown(self):
        if self.language == 'markdown' and not self.large_file:
            self.preview.render(
                self.editor.toPlainText(),
                self.path.parent if self.path else self.window.root,
                self.window.theme)

    def update_markdown_mode(self, *_):
        markdown = getattr(self, 'language', '') == 'markdown' and not self.large_file
        index = self.markdown_mode.currentIndex()
        self.preview.setVisible(markdown and index != 0)
        self.splitter.setVisible(not markdown or index in (0, 1))
        self.preview.tabs.setCurrentIndex(1 if index == 3 else 0)
        if markdown:
            self.render_markdown()

    @property
    def editor(self):
        return self.active_editor or self.editors[0]

    def add_view(self):
        editor = Editor()
        if self.editors:
            editor.highlighter.setDocument(None)
            editor.setDocument(self.editors[0].document())
            editor.highlighter = self.editors[0].highlighter
            editor.configure_navigation()
        editor.breakpoints = self.breakpoints
        editor.complete.connect(self.completion_timer.start)
        editor.signature_timer = QTimer(editor, interval=180, singleShot=True)
        editor.signature_requested.connect(editor.signature_timer.start)
        editor.signature_timer.timeout.connect(lambda: self.window.signature(self, editor))
        editor.hover_requested.connect(lambda pos: self.window.hover(self, editor, pos))
        editor.breakpoint_toggled.connect(lambda line: self.window.toggle_breakpoint(self, line))
        editor.cursorPositionChanged.connect(lambda: self.cursor_changed(editor))
        editor.installEventFilter(self.window)
        self.editors.append(editor)
        self.splitter.addWidget(editor)
        editor.large_file = self.large_file
        editor.structure.enabled = not self.large_file
        if self.large_file:
            editor.highlighter.setDocument(None)
        editor.language = getattr(self, 'language', 'python')
        self.window.style_editor(editor)
        return editor

    def cursor_changed(self, editor):
        if editor.hasFocus():
            self.active_editor = editor
        editor.popup.hide()
        if editor.signature_popup.isVisible():
            editor.signature_timer.start()
        self.window.update_position()
        self.diagnostics_timer.start()

    def changed(self, position=0, removed=0, added=0):
        if self.loading or (removed == 0 and added == 0):
            return
        self.edit_generation += 1
        self.window.notes_panel.source_changed(self)
        if not self.large_file and (self.editor.document().characterCount() > 1_000_000 or self.editor.blockCount(
        ) > 20000 or self.editor.document().findBlock(position).length() > 20001):
            self.enter_large_mode()
        if self.breakpoint_cursors:
            conditions = {cursor.blockNumber() + 1: self.breakpoint_conditions[line]
                          for line, cursor in self.breakpoint_cursors.items() if line in self.breakpoint_conditions}
            anchors = {
                cursor.blockNumber() +
                1: cursor for cursor in self.breakpoint_cursors.values()}
            self.breakpoint_cursors = anchors
            self.breakpoint_conditions = conditions
            self.breakpoints.clear()
            self.breakpoints.update(anchors)
        self.diagnostics = []
        for editor in self.editors:
            editor.popup.hide()
            if editor.signature_popup.isVisible():
                editor.signature_timer.start()
        if not self.large_file:
            self.timer.start()
            self.markdown_timer.start()
            if self.language in VALIDATED_LANGUAGES:
                self.validation_timer.start()
        self.diagnostics_timer.start()
        self.window.refresh_problems()

    def enter_large_mode(self):
        self.large_file = True
        self.timer.stop()
        self.completion_timer.stop()
        self.markdown_timer.stop()
        self.validation_timer.stop()
        if self.synced is not None and self.window.lsp and self.window.lsp.initialized:
            self.window.lsp.notify('textDocument/didClose', {'textDocument': {'uri': self.uri}})
        self.synced = None
        self.diagnostics = []
        for editor in self.editors:
            editor.large_file = True
            editor.highlighter.setDocument(None)
            editor.structure.enabled = False
            editor.structure.rebuild()
            editor.minimap_enabled = False
            editor.minimap.hide()
            editor.update_gutter_margin()
            editor.signature_timer.stop()
            editor.hover_timer.stop()
            editor.popup.hide()
            editor.signature_popup.hide()
        self.markdown_bar.hide()
        self.update_markdown_mode()
        self.window.update_position()

    def paint_diagnostics(self):
        for editor in self.editors:
            if not editor.isVisible():
                continue
            selections = []
            current = QTextEdit.ExtraSelection()
            current.cursor = editor.textCursor()
            current.cursor.clearSelection()
            current.format.setBackground(
                QColor('#1c273a' if self.window.theme == 'Gece' else '#edf3ff'))
            current.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
            selections.append(current)
            editor.diagnostic_lines.clear()
            for diagnostic in self.diagnostics:
                region = diagnostic['range']
                line = region['start']['line']
                severity = diagnostic.get('severity', 1)
                editor.diagnostic_lines[line] = min(severity, editor.diagnostic_lines.get(line, 4))
                start, end = editor.offset(region['start']), editor.offset(region['end'])
                if start == end:
                    if start < editor.document().characterCount() - 1:
                        end += 1
                    elif start:
                        start -= 1
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(editor.document())
                selection.cursor.setPosition(start)
                selection.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                selection.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                selection.format.setUnderlineColor(
                    QColor('#fb7185' if severity == 1 else '#fbbf24'))
                selection.format.setToolTip(diagnostic['message'])
                selections.append(selection)
            if editor.execution_line:
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(
                    editor.document().findBlockByNumber(
                        editor.execution_line - 1))
                selection.format.setBackground(
                    QColor('#53431e' if self.window.theme == 'Gece' else '#ffecad'))
                selection.format.setForeground(
                    QColor('#fff4c2' if self.window.theme == 'Gece' else '#493400'))
                selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
                selections.append(selection)
            editor.setExtraSelections(selections)
            editor.gutter.update()
