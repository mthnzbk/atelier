"""Markdown rendering with source HTML and project-local image resolution."""
from pathlib import Path
import markdown
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTextBrowser, QPlainTextEdit


class MarkdownPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.open_link)
        self.html_source = QPlainTextEdit(readOnly=True)
        self.html_source.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.tabs.addTab(self.browser, 'Önizleme')
        self.tabs.addTab(self.html_source, 'HTML kaynağı')
        layout.addWidget(self.tabs)
        self.rendered_html = ''

    def open_link(self, url):
        if url.toString().startswith('#'):
            self.browser.scrollToAnchor(url.fragment())
        elif url.scheme() in ('http', 'https', 'mailto'):
            QDesktopServices.openUrl(url)

    def render(self, text, directory, theme='Gece'):
        body = markdown.markdown(text, extensions=['fenced_code', 'tables', 'sane_lists', 'toc'])
        dark = theme == 'Gece'
        fg, bg, code = (
            '#dce5f5', '#111722', '#202c40') if dark else (
            '#243047', '#ffffff', '#eef2f8')
        self.rendered_html = f'''<!doctype html><html><head><meta charset="utf-8">
<style>body {{color:{fg}; background:{bg}; font-family:'Segoe UI',sans-serif; padding:20px; line-height:1.6;}}
pre,code {{background:{code}; font-family:Consolas,monospace;}} pre {{padding:12px;}}
a {{color:#7c9cff;}} th,td {{padding:7px; border:1px solid #64748b;}}
blockquote {{border-left:3px solid #7c9cff; margin-left:0; padding-left:12px;}}</style></head><body>{body}</body></html>'''
        scrollbar = self.browser.verticalScrollBar().value()
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(Path(directory).resolve()) + '/'))
        self.browser.setHtml(self.rendered_html)
        self.browser.verticalScrollBar().setValue(scrollbar)
        self.html_source.setPlainText(self.rendered_html)
