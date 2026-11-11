"""Application lifecycle and composition of window features."""
import os
import sys
from pathlib import Path
from PySide6.QtCore import QEvent, QTimer, QSettings, QProcess, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from atelier.debugger.client import Debugger
from atelier.ui.theme import PALETTES
from atelier.storage.monitor import FileMonitor
from atelier.storage.sessions import SessionStore
from atelier.runtime.paths import asset_path
from atelier.projects.settings import ProjectSettings
from atelier.projects.recent import RecentProjects
from atelier.version import APP_VERSION
from atelier.storage.history import FileHistory
from atelier.editor.document import Document


from atelier.app.features.presentation import PresentationFeatures
from atelier.app.features.language import LanguageFeatures
from atelier.app.features.files import FilesFeatures
from atelier.app.features.projects import ProjectsFeatures
from atelier.app.features.search import SearchFeatures
from atelier.app.features.execution import ExecutionFeatures
from atelier.app.features.debugging import DebuggingFeatures
from atelier.app.features.git import GitFeatures
from atelier.app.features.navigation import NavigationFeatures
from atelier.app.features.tree import TreeFeatures
from atelier.app.features.session import SessionFeatures


class Window(PresentationFeatures, LanguageFeatures, FilesFeatures, ProjectsFeatures, SearchFeatures,
             ExecutionFeatures, DebuggingFeatures, GitFeatures, NavigationFeatures, TreeFeatures, SessionFeatures, QMainWindow):
    python_status_changed = Signal()

    def __init__(self, root=None, settings=None):
        super().__init__()
        self.settings = settings or QSettings('Atelier', 'PythonEditor')
        self.project_profiles = ProjectSettings(self.settings)
        self.recent_projects = RecentProjects(self.settings)
        self.project_loaded = False
        self.project_trusted = False
        self.root = Path(root or self.settings.value('project', str(Path.cwd()))).resolve()
        if not self.root.is_dir():
            self.root = Path.cwd()
        self.interpreter = self.python_preference = ''
        self.theme = self.settings.value('theme', 'Gece')
        if self.theme not in PALETTES:
            self.theme = 'Gece'
        self.font_size = int(self.settings.value('font_size', 12))
        self.font_family = self.settings.value('font_family', 'Consolas')
        self.format_on_save = self.settings.value('format_on_save', False, type=bool)
        self.format_web_on_save = False
        self.save_imports = self.save_trim = self.save_final_newline = False
        self.tab_width = int(self.settings.value('tab_width', 4))
        self.completion_delay = int(self.settings.value('completion_delay', 160))
        self.auto_complete = self.settings.value('auto_complete', True, type=bool)
        self.active_guide = self.settings.value('active_guide', True, type=bool)
        self.git_enabled = self.settings.value('git_enabled', True, type=bool)
        self.git_executable = self.settings.value('git_executable', '')
        self.git_interval = int(self.settings.value('git_interval', 5))
        self.coverage_enabled = self.settings.value('coverage_enabled', False, type=bool)
        self.refresh_idle_terminal = self.settings.value('refresh_idle_terminal', True, type=bool)
        self.coverage_data = {}
        self.minimap_visible = self.settings.value('minimap', True, type=bool)
        self.restore_enabled = self.settings.value('restore_session', True, type=bool)
        self.autorecovery_enabled = self.settings.value('autorecovery', True, type=bool)
        self.session_store = SessionStore(self.settings)
        self.closed_breakpoints = {}
        self.file_history = FileHistory(self.session_store.path.parent)
        self.restoring = True
        self.watch_expressions = []
        self.documents = []
        self.closed_tabs = []
        self.lsp = None
        self.workers = []
        self.save_workers = []
        self.validation_workers = []
        self.validation_pending = set()
        self.save_queue = {}
        self.search_generation = 0
        self.processes = []
        self.git_reads = set()
        self.git_refresh_timer = QTimer(self, singleShot=True, interval=140)
        self.git_refresh_timer.timeout.connect(self.refresh_git)
        self.git_generation = 0
        self.closing = False
        self.update_worker = None
        self.pending_update = None
        self.run_args = ''
        self.test_args = ''
        self.navigation_history = []
        self.navigation_index = -1
        self.file_monitor = FileMonitor(self)
        self.file_monitor.changed.connect(self.external_changed)
        self.setWindowTitle('Atelier · Python Studio ' + APP_VERSION)
        logo = asset_path('atelier-logo.png')
        if logo.exists():
            self.setWindowIcon(QIcon(str(logo)))
            QApplication.instance().setWindowIcon(self.windowIcon())
        self.resize(1440, 940)
        self.setMinimumSize(900, 620)
        self.build_ui()
        self.build_actions()
        self.runner = QProcess(self)
        self.runner.readyReadStandardOutput.connect(
            lambda: self.append_output(
                bytes(
                    self.runner.readAllStandardOutput()).decode(
                    'utf-8', 'replace')))
        self.runner.readyReadStandardError.connect(
            lambda: self.append_output(
                bytes(
                    self.runner.readAllStandardError()).decode(
                    'utf-8', 'replace')))
        self.runner.finished.connect(
            lambda code, _: self.append_output(
                f'\n[Çıkış kodu: {code}]\n'))
        self.runner.errorOccurred.connect(
            lambda _: self.append_output(
                self.runner.errorString() + '\n'))
        self.debugger = Debugger(self)
        self.debugger.output.connect(self.append_output)
        self.debugger.paused.connect(self.debug_paused)
        self.debugger.variables.connect(self.show_variables)
        self.debugger.state.connect(self.debug_state)
        self.apply_theme()
        self.set_project(self.root, restart=False)
        self.start_lsp()
        self.restore_session()
        if not self.documents:
            self.new()
        self.restore_layout()
        self.restoring = False
        self.recovery_timer = QTimer(self, interval=2000)
        self.recovery_timer.timeout.connect(self.checkpoint)
        self.recovery_timer.start()
        self.git_timer = QTimer(self, interval=self.git_interval * 1000)
        self.git_timer.timeout.connect(self.refresh_git)
        self.git_timer.start()

    @property
    def terminal(self):
        return self.terminal_tabs.active

    @property
    def current(self):
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, Document) else None

    @property
    def editor(self):
        return self.current.editor if self.current else None

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            for doc in self.documents:
                if watched in doc.editors:
                    doc.active_editor = watched
                    self.update_position()
                    break
        return super().eventFilter(watched, event)

    def track_worker(self, worker, pool):
        pool.append(worker)

        def finished():
            if worker in pool:
                pool.remove(worker)
            worker.deleteLater()
        worker.finished.connect(finished)

    def message(self, text):
        QMessageBox.information(self, 'Atelier', text)

    def closeEvent(self, event):
        # Confirm first, then persist only the state the user chose to keep.
        for doc in list(self.documents):
            if not self.confirm_saved(doc):
                event.ignore()
                return
        self.checkpoint(clean=True)
        self.save_layout()
        self.closing = True
        self.save_queue.clear()
        self.git_refresh_timer.stop()
        self.search_generation += 1
        if hasattr(self, 'breakpoint_panel'):
            self.breakpoint_panel.close()
        self.recovery_timer.stop()
        self.git_timer.stop()
        self.file_monitor.shutdown()
        self.terminal_tabs.shutdown()
        self.test_panel.shutdown()
        if self.update_worker and self.update_worker.isRunning():
            self.update_worker.requestInterruption()
            self.update_worker.wait(5000)
        for worker in [*self.workers, *self.save_workers, *self.validation_workers]:
            worker.requestInterruption()
            worker.wait(3000)
        for process in list(self.processes):
            process.kill()
            process.waitForFinished(500)
        self.runner.kill()
        self.runner.waitForFinished(1000)
        self.debugger.shutdown()
        for doc in self.documents:
            doc.timer.stop()
            doc.completion_timer.stop()
            doc.markdown_timer.stop()
            doc.diagnostics_timer.stop()
            doc.validation_timer.stop()
            for editor in doc.editors:
                editor.signature_timer.stop()
                editor.hover_timer.stop()
        self.lsp.stop()
        if self.pending_update:
            from atelier.runtime.updates import launch_windows_update
            payload, installation = self.pending_update
            try:
                launch_windows_update(payload, installation, os.getpid())
            except (OSError, ValueError) as error:
                self.message('Güncelleme başlatılamadı: ' + str(error))
        event.accept()


def run():
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Atelier.PythonStudio')
    app = QApplication(sys.argv)
    app.setOrganizationName('Atelier')
    app.setApplicationName('AtelierPythonStudio')
    app.setStyle('Fusion')
    settings_file = os.environ.get('ATELIER_SETTINGS_FILE')
    settings = QSettings(settings_file, QSettings.Format.IniFormat) if settings_file else None
    window = Window(settings=settings)
    window.show()
    sys.exit(app.exec())
