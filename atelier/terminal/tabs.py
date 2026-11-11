"""Independent terminal sessions grouped by project."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QStackedWidget, QTabWidget

from atelier.terminal.panel import TerminalPanel


class TerminalTabs(QStackedWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.pages = {}
        self.restricted = QLabel('Terminali kullanmak için projeye güven verin.')
        self.restricted.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addWidget(self.restricted)

    @property
    def active(self):
        if self.window.project_trusted and (tabs := self.pages.get(self.window.root)):
            return tabs.currentWidget()
        return None

    def show_project(self):
        if not self.window.project_trusted:
            self.setCurrentWidget(self.restricted)
            return
        root = self.window.root
        tabs = self.pages.get(root)
        if tabs is None:
            tabs = QTabWidget()
            tabs.setTabsClosable(True)
            tabs.setMovable(True)
            tabs.tabCloseRequested.connect(lambda index: self.close_session(tabs, index))
            plus = QPushButton('+')
            plus.setToolTip('Yeni terminal sekmesi')
            plus.setAccessibleName('Yeni terminal sekmesi')
            plus.clicked.connect(lambda checked=False: self.new_session())
            tabs.setCornerWidget(plus, Qt.Corner.TopRightCorner)
            self.pages[root] = tabs
            self.addWidget(tabs)
            self.setCurrentWidget(tabs)
            self.new_session(focus=False)
        else:
            self.setCurrentWidget(tabs)

    def new_session(self, *, focus=True):
        if not self.window.project_trusted:
            return
        root = self.window.root
        tabs = self.pages[root]
        session = TerminalPanel(lambda: root, lambda: self.window.interpreter)
        existing = {tabs.tabText(index) for index in range(tabs.count())}
        number = 1
        while f'Terminal {number}' in existing:
            number += 1
        tabs.addTab(session, f'Terminal {number}')
        tabs.setCurrentWidget(session)
        session.start()
        if focus:
            session.view.setFocus()
        return session

    def close_session(self, tabs, index, *, confirm=True):
        from PySide6.QtWidgets import QMessageBox
        session = tabs.widget(index)
        if session is None:
            return
        if confirm and session.ready and not session.prompt_idle:
            answer = QMessageBox.question(self, 'Terminali kapat',
                                          'Bu terminal oturumu kapatılsın mı?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                          QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Yes:
                return
        session.shutdown()
        tabs.removeTab(index)
        session.deleteLater()

    def discard_project(self, root):
        tabs = self.pages.pop(root, None)
        if tabs is not None:
            while tabs.count():
                self.close_session(tabs, 0, confirm=False)
            self.removeWidget(tabs)
            tabs.deleteLater()

    def refresh_idle_environment(self):
        if tabs := self.pages.get(self.window.root):
            for index in range(tabs.count()):
                tabs.widget(index).refresh_idle_environment()

    def shutdown(self):
        for root in list(self.pages):
            self.discard_project(root)
