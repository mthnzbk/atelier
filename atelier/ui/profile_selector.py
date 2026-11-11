"""Toolbar selection shared by Run and Debug."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QToolButton

from atelier.projects.run_profiles import load_profiles, profile_python


class ProfileSelector(QToolButton):
    default_label = 'Etkin dosya'

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setAccessibleName('Çalıştırma profili')
        self.setText(self.default_label)
        self.profile_menu = QMenu(self)
        self.profile_menu.aboutToShow.connect(self.populate)
        self.setMenu(self.profile_menu)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def refresh(self):
        window = self.window
        try:
            profiles, active = load_profiles(window)
        except ValueError as error:
            self.setText('Profil hatası')
            self.setToolTip(str(error))
            return {}, ''
        if active not in profiles:
            active = ''
        profile = profiles.get(active, {})
        file = profile.get('file') or (window.current.path if window.current else None)
        path = str(window.root / Path(file)) if file else 'Kaydedilmiş etkin dosya gerekli'
        python = profile_python(window, profile) or 'Python bulunamadı'
        self.setText(active or self.default_label)
        self.setToolTip(f'Giriş dosyası\n{path}\n\nPython\n{python}')
        return profiles, active

    def populate(self):
        profiles, active = self.refresh()
        self.profile_menu.clear()
        for key, text in [('', self.default_label), *((name, name) for name in profiles)]:
            action = self.profile_menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(key == active)
            action.triggered.connect(lambda checked=False, name=key: self.select(name))
        self.profile_menu.addSeparator()
        self.profile_menu.addAction('Profilleri düzenle…', self.window.run_profiles_dialog)

    def select(self, name):
        window = self.window
        key = window.project_profiles.key(window.root) + 'active_profile'
        window.settings.setValue(key, name)
        self.refresh()
