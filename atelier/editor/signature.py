import html
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class SignaturePopup(QFrame):
    def __init__(self, editor):
        super().__init__(editor, Qt.WindowType.ToolTip)
        self.setObjectName('signatureHelp')
        self.editor = editor
        self.result = {}
        self.index = 0
        self.setMaximumWidth(700)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.counter = QLabel()
        row.addWidget(self.counter, 1)
        for label, delta in [('‹', -1), ('›', 1)]:
            button = QPushButton(label)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setFixedWidth(32)
            button.clicked.connect(lambda checked=False, d=delta: self.cycle(d))
            row.addWidget(button)
        layout.addLayout(row)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.label)
        self.documentation = QLabel()
        self.documentation.setWordWrap(True)
        layout.addWidget(self.documentation)
        self.documentation.setTextFormat(Qt.TextFormat.PlainText)
        self.hide()

    def update_help(self, result):
        if not result or not result.get('signatures'):
            self.hide()
            return
        same = [
            signature['label'] for signature in self.result.get(
                'signatures', [])] == [
            signature['label'] for signature in result['signatures']]
        self.result = result
        self.index = min(
            self.index if same and self.isVisible() else (
                result.get('activeSignature') or 0), len(
                result['signatures']) - 1)
        self.render()

    def cycle(self, delta):
        if self.result.get('signatures'):
            self.index = (self.index + delta) % len(self.result['signatures'])
            self.render()

    def render(self):
        signature = self.result['signatures'][self.index]
        text = signature['label']
        parameter = signature.get('activeParameter', self.result.get('activeParameter', 0)) or 0
        parameters = signature.get('parameters', [])
        start = end = 0
        if 0 <= parameter < len(parameters):
            label = parameters[parameter]['label']
            if isinstance(label, list):
                start = len(text.encode('utf-16-le')[:label[0] * 2].decode('utf-16-le'))
                end = len(text.encode('utf-16-le')[:label[1] * 2].decode('utf-16-le'))
            else:
                start = text.find(label, text.find('(') + 1)
                end = start + len(label)
        rendered = html.escape(text)
        if start >= 0 and end > start:
            rendered = html.escape(text[:start]) + '<b style="color:#7c9cff">' + \
                html.escape(text[start:end]) + '</b>' + html.escape(text[end:])
        self.label.setText('<code>' + rendered + '</code>')
        self.counter.setText(
            f"İmza {self.index + 1}/{len(self.result['signatures'])} · parametre {parameter + 1}")
        documentation = parameters[parameter].get(
            'documentation',
            signature.get(
                'documentation',
                '')) if 0 <= parameter < len(parameters) else signature.get(
            'documentation',
            '')
        self.documentation.setText(
            (documentation.get(
                'value',
                '') if isinstance(
                documentation,
                dict) else str(documentation))[
                :1200])
        self.adjustSize()
        self.move(self.editor.viewport().mapToGlobal(self.editor.cursorRect().bottomLeft()))
        self.show()
