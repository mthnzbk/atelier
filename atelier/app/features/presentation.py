"""Main-window presentation actions."""
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget, QTreeView, QTreeWidget, QPlainTextEdit, QLineEdit, QPushButton, QLabel, QToolBar, QListWidget, QCheckBox, QDialog, QDialogButtonBox, QAbstractItemView
from atelier.ui.theme import stylesheet, PALETTES
from atelier.projects.tree_model import ProjectModel
from atelier.ui.palette import CommandPalette
from atelier.languages.validation import LANGUAGES as VALIDATED_LANGUAGES
from atelier.languages.formatting import LANGUAGES as WEB_FORMAT_LANGUAGES
from atelier.ui.icons import icon, for_text


class PresentationFeatures:
    def build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.main_split = QSplitter()
        self.build_sidebar()
        self.main_split.addWidget(self.sidebar)
        self.right_split = QSplitter(Qt.Orientation.Vertical)
        self.build_editor_area()
        self.build_bottom_panel()
        self.right_split.addWidget(self.bottom)
        self.right_split.setSizes([650, 210])
        self.main_split.addWidget(self.right_split)
        self.main_split.setSizes([260, 1180])
        layout.addWidget(self.main_split)
        self.setCentralWidget(central)
        self.lsp_label = QLabel('● LSP başlatılıyor')
        self.position_label = QLabel('Satır 1, Sütun 1')
        self.python_label = QPushButton()
        self.python_label.setFlat(True)
        self.python_label.clicked.connect(self.show_python_status)
        self.trust_button = QPushButton()
        self.trust_button.setFlat(True)
        self.trust_button.clicked.connect(self.show_project_trust)
        self.statusBar().addWidget(self.lsp_label)
        self.statusBar().addPermanentWidget(self.python_label)
        self.statusBar().addPermanentWidget(self.trust_button)
        self.statusBar().addPermanentWidget(self.position_label)

    def build_sidebar(self):
        self.sidebar = QTabWidget()
        self.sidebar.setMinimumWidth(200)
        self.build_explorer_tab()
        self.build_search_tab()
        self.build_git_tab()

    def build_explorer_tab(self):
        explorer = QWidget()
        box = QVBoxLayout(explorer)
        box.setContentsMargins(0, 0, 0, 0)
        brand = QLabel('ATELIER')
        brand.setObjectName('brand')
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(12, 0, 0, 0)
        logo_label = QLabel()
        logo_label.setPixmap(self.windowIcon().pixmap(32, 32))
        brand_row.addWidget(logo_label)
        brand_row.addWidget(brand, 1)
        box.addLayout(brand_row)
        self.project_label = QLabel()
        self.project_label.setObjectName('eyebrow')
        box.addWidget(self.project_label)
        self.fs = ProjectModel(self)
        self.tree = QTreeView()
        self.tree.setModel(self.fs)
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.tree_menu)
        for i in range(1, 4):
            self.tree.hideColumn(i)
        self.tree.doubleClicked.connect(lambda index: self.open_path(
            self.fs.filePath(index)) if self.fs.isDir(index) is False else None)
        box.addWidget(self.tree)
        self.sidebar.addTab(explorer, 'Dosyalar')

    def build_search_tab(self):
        search = QWidget()
        sb = QVBoxLayout(search)
        self.project_query = QLineEdit(placeholderText='Projede ara…')
        self.project_query.returnPressed.connect(self.search_project)
        self.project_replace = QLineEdit(placeholderText='Yeni metin…')
        self.project_case = QCheckBox('Büyük/küçük harf duyarlı')
        self.project_regex = QCheckBox('Regex')
        self.project_whole = QCheckBox('Tam kelime')
        self.project_globs = QLineEdit(placeholderText='Dosya filtresi: *.py, *.md')
        sb.addWidget(self.project_query)
        sb.addWidget(self.project_replace)
        sb.addWidget(self.project_case)
        sb.addWidget(self.project_regex)
        sb.addWidget(self.project_whole)
        sb.addWidget(self.project_globs)
        row = QHBoxLayout()
        self.button(row, 'Ara', self.search_project)
        self.button(row, 'Durdur', self.cancel_search)
        self.button(row, 'Tümünü değiştir…', self.replace_project)
        sb.addLayout(row)
        self.search_label = QLabel('UTF-8 metin dosyalarında arar')
        sb.addWidget(self.search_label)
        self.search_results = QListWidget()
        self.search_results.itemClicked.connect(self.open_search_result)
        sb.addWidget(self.search_results)
        self.sidebar.addTab(search, 'Arama')

    def build_git_tab(self):
        self.git_list = QListWidget()
        self.git_list.itemClicked.connect(self.open_git_item)
        git_page = QWidget()
        git_layout = QVBoxLayout(git_page)
        git_layout.setContentsMargins(6, 6, 6, 6)
        for entries in [[('Hazırla (+)', self.git_stage), ('Hazırlamayı kaldır', self.git_unstage)],
                        [('Commit…', self.git_commit), ('Geçmiş', self.git_history)],
                        [('Dallar…', self.git_branches), ('Yenile', self.refresh_git)],
                        [('Pull…', lambda: self.git_remote('pull')), ('Push…', lambda: self.git_remote('push'))]]:
            row = QHBoxLayout()
            for label, callback in entries:
                self.button(row, label, callback)
            git_layout.addLayout(row)
        git_layout.addWidget(QLabel('Seçili dosyayı hazırla / hazırlamadan çıkar'))
        self.button(git_layout, 'Depo başlat (git init)', self.git_init)
        self.button(git_layout, 'Çakışmaları çöz…', self.resolve_conflicts)
        legend = QLabel(
            'Gri: izlenmeyen · Sarı: hazırlanmamış\nYeşil: commit bekliyor · Kırmızı: çakışma')
        legend.setWordWrap(True)
        git_layout.addWidget(legend)
        git_layout.addWidget(self.git_list)
        self.sidebar.addTab(git_page, 'Git')

    def build_editor_area(self):
        editor_area = QWidget()
        eb = QVBoxLayout(editor_area)
        eb.setContentsMargins(0, 0, 0, 0)
        eb.setSpacing(0)
        self.find_bar = QWidget()
        fb = QHBoxLayout(self.find_bar)
        fb.setContentsMargins(10, 6, 10, 6)
        self.find_text = QLineEdit(placeholderText='Dosyada ara')
        self.replace_text = QLineEdit(placeholderText='Yeni metin')
        self.find_case = QCheckBox('Aa')
        self.find_regex = QCheckBox('.*')
        self.find_regex.setToolTip('Düzenli ifade')
        self.find_whole = QCheckBox('Kelime')
        fb.addWidget(self.find_text)
        fb.addWidget(self.replace_text)
        fb.addWidget(self.find_case)
        fb.addWidget(self.find_regex)
        fb.addWidget(self.find_whole)
        self.find_text.returnPressed.connect(self.find_next)
        self.button(fb, '↑', lambda: self.find_next(True))
        self.button(fb, '↓', self.find_next)
        self.button(fb, 'Değiştir', self.replace_one)
        self.button(fb, 'Tümü', self.replace_all)
        self.button(fb, '×', self.find_bar.hide)
        self.find_bar.hide()
        eb.addWidget(self.find_bar)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.tab_changed)
        eb.addWidget(self.tabs)
        self.right_split.addWidget(editor_area)

    def build_bottom_panel(self):
        self.bottom = QTabWidget()
        self.problems = QListWidget()
        self.problems.itemClicked.connect(self.goto_problem)
        self.bottom.addTab(self.problems, 'Sorunlar')
        self.build_output_tab()
        self.build_debug_tab()
        self.diff = QPlainTextEdit(readOnly=True)
        self.bottom.addTab(self.diff, 'Git farkı')
        from atelier.terminal.tabs import TerminalTabs
        self.terminal_tabs = TerminalTabs(self)
        self.bottom.addTab(self.terminal_tabs, 'Terminal')
        from atelier.testing.panel import TestPanel
        self.test_panel = TestPanel(self)
        self.test_panel.navigate.connect(self.goto_test)
        self.bottom.addTab(self.test_panel, 'Testler')
        self.build_navigation_tab()

    def build_output_tab(self):
        output_page = QWidget()
        ob = QVBoxLayout(output_page)
        ob.setContentsMargins(0, 0, 0, 0)
        from atelier.ui.output import OutputView
        self.output = OutputView(lambda: Path(getattr(self, 'output_root', self.root)))
        self.output.navigate.connect(self.goto_test)
        self.output.setMaximumBlockCount(20000)
        ob.addWidget(self.output)
        input_row = QHBoxLayout()
        self.stdin = QLineEdit(placeholderText='Çalışan programa girdi gönder (Enter)')
        self.stdin.returnPressed.connect(self.send_stdin)
        input_row.addWidget(self.stdin)
        self.button(input_row, 'Gönder', self.send_stdin)
        self.button(input_row, 'Temizle', self.output.clear)
        ob.addLayout(input_row)
        self.bottom.addTab(output_page, 'Çıktı')

    def build_debug_tab(self):
        debug_container = QWidget()
        debug_layout = QVBoxLayout(debug_container)
        debug_layout.setContentsMargins(0, 0, 0, 0)
        debug_page = QSplitter()
        self.stack_list = QListWidget()
        self.stack_list.itemClicked.connect(self.select_frame)
        self.variables_tree = QTreeWidget()
        self.variables_tree.setHeaderLabels(['Değişken', 'Değer', 'Tür'])
        self.variables_tree.itemExpanded.connect(self.expand_variable)
        self.variables_tree.itemDoubleClicked.connect(self.edit_variable)
        debug_page.addWidget(self.stack_list)
        debug_page.addWidget(self.variables_tree)
        self.watch_tree = QTreeWidget()
        self.watch_tree.setHeaderLabels(['İfade', 'Değer'])
        self.watch_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.watch_tree.customContextMenuRequested.connect(lambda _: self.remove_watch())
        debug_page.addWidget(self.watch_tree)
        debug_layout.addWidget(debug_page)
        watch_row = QHBoxLayout()
        self.watch_input = QLineEdit(placeholderText='İzlenecek ifade (ör. len(items))')
        self.watch_input.returnPressed.connect(self.add_watch)
        watch_row.addWidget(self.watch_input, 1)
        self.button(watch_row, 'İzle', self.add_watch)
        self.button(watch_row, 'Kaldır', self.remove_watch)
        self.button(watch_row, 'Koşullu kesme noktası…', self.edit_breakpoint_condition)
        self.button(watch_row, 'Kesme noktaları…', self.show_breakpoints)
        debug_layout.addLayout(watch_row)
        self.bottom.addTab(debug_container, 'Debugger')

    def build_navigation_tab(self):
        navigation = QWidget()
        navigation_layout = QVBoxLayout(navigation)
        self.navigation_filter = QLineEdit(placeholderText='Sembol veya konum filtrele…')
        self.navigation_results = QListWidget()
        self.navigation_results.itemClicked.connect(self.open_navigation_result)
        self.navigation_filter.textChanged.connect(
            lambda text: [
                self.navigation_results.item(i).setHidden(
                    text.casefold() not in self.navigation_results.item(i).text().casefold()) for i in range(
                    self.navigation_results.count())])
        navigation_layout.addWidget(self.navigation_filter)
        navigation_layout.addWidget(self.navigation_results)
        self.navigation_panel = navigation
        self.bottom.addTab(navigation, 'Kod gezinmesi')

    def button(self, layout, text, callback):
        button = QPushButton(text)
        button.setIcon(for_text(text))
        button.setProperty('materialButton', True)
        button.clicked.connect(lambda checked=False: callback())
        layout.addWidget(button)
        return button

    def build_actions(self):
        menus = {name: self.menuBar().addMenu(name)
                 for name in ['Dosya', 'Düzenle', 'Kod', 'Çalıştır', 'Görünüm']}
        self.actions = {}

        def action(key, label, shortcut, callback, menu, checkable=False):
            a = QAction(label, self)
            a.setIcon(icon(key))
            if shortcut:
                a.setShortcut(shortcut)
            a.setCheckable(checkable)
            a.triggered.connect(lambda checked=False: callback(
                checked) if checkable else callback())
            menus[menu].addAction(a)
            self.actions[key] = a
            return a
        action('new', 'Yeni dosya', 'Ctrl+N', self.new, 'Dosya')
        action('open', 'Dosya aç…', 'Ctrl+O', self.open, 'Dosya')
        action('quick_open', 'Hızlı dosya aç…', 'Ctrl+P', self.quick_open, 'Dosya')
        action('recent_projects', 'Son projeler…', 'Ctrl+Alt+P', self.show_recent_projects, 'Dosya')
        action('python_status', 'Python durumu…', '', self.show_python_status, 'Çalıştır')
        action('reopen_tab', 'Kapatılan sekmeyi aç', 'Ctrl+Shift+T', self.reopen_closed_tab, 'Dosya')
        action('recent_tab', 'Son kullanılan sekmeye geç', 'Ctrl+Tab', self.cycle_recent_tabs, 'Görünüm')
        action('recent_tab_reverse', 'Son kullanılan sekmelerde geri git', 'Ctrl+Shift+Tab',
               lambda: self.cycle_recent_tabs(-1), 'Görünüm')
        action('history', 'Dosya geçmişi…', '', self.show_file_history, 'Dosya')
        action('profiles', 'Çalıştırma profilleri…', '', self.run_profiles_dialog, 'Çalıştır')
        action('project_tasks', 'Proje komutları…', '', self.project_task_picker, 'Çalıştır')
        action(
            'project_config',
            'Paylaşılabilir proje ayarları…',
            '',
            self.open_project_config,
            'Dosya')
        action('imports', 'Importları düzenle…', 'Ctrl+Alt+O',
               lambda: self.python_refactor('imports'), 'Kod')
        action('missing_import', 'Eksik import ekle…', '', self.add_missing_import, 'Kod')
        action('extract_method', 'Seçimi fonksiyona çıkar…', '',
               lambda: self.python_refactor('method'), 'Kod')
        action('extract_variable', 'Seçimi değişkene çıkar…', '',
               lambda: self.python_refactor('variable'), 'Kod')
        action(
            'signature',
            'Parametre bilgisi',
            'Ctrl+Shift+Space',
            lambda: self.signature(
                self.current,
                self.editor) if self.current else None,
            'Kod')
        action('select_next', 'Sonraki eşleşmeye imleç ekle', 'Ctrl+D',
               lambda: self.editor.select_next_occurrence() if self.editor else None, 'Düzenle')
        action('code_actions', 'Hızlı düzeltmeler…', 'Ctrl+.', self.code_actions, 'Kod')
        action('compare', 'Yan yana Git karşılaştırması…', '', self.git_compare, 'Görünüm')
        action('coverage', 'Test kapsamını göster / temizle', '', self.toggle_coverage, 'Çalıştır')
        action('project', 'Proje klasörü aç…', 'Ctrl+Shift+O', self.choose_project, 'Dosya')
        action('save', 'Kaydet', 'Ctrl+S', self.save, 'Dosya')
        action('save_as', 'Farklı kaydet…', 'Ctrl+Shift+S', lambda: self.save(True), 'Dosya')
        action('save_all', 'Tümünü kaydet', 'Ctrl+Alt+S', self.save_all, 'Dosya')
        action(
            'close',
            'Sekmeyi kapat',
            'Ctrl+W',
            lambda: self.close_tab(
                self.tabs.currentIndex()),
            'Dosya')
        for key, label, shortcut, method in [('undo', 'Geri al', 'Ctrl+Z', 'undo'), ('redo', 'Yinele', 'Ctrl+Y', 'redo'),
                                             ('comment', 'Satır yorumunu aç/kapat', 'Ctrl+/', 'toggle_comment')]:
            action(key, label, shortcut, lambda m=method: getattr(
                self.editor, m)() if self.editor else None, 'Düzenle')
        action('find', 'Bul / değiştir', 'Ctrl+F', self.show_find, 'Düzenle')
        action('replace', 'Değiştir', 'Ctrl+H', self.show_find, 'Düzenle')
        action('search', 'Projede ara', 'Ctrl+Shift+F', self.show_project_search, 'Düzenle')
        action('complete', 'Kod tamamla', 'Ctrl+Space', self.complete, 'Kod')
        action('definition', 'Tanıma git', 'F12', self.definition, 'Kod')
        action('rename', 'Sembolü yeniden adlandır…', 'F2', self.rename_symbol, 'Kod')
        action('format', 'Kodu biçimlendir', 'Shift+Alt+F', self.format_document, 'Kod')
        action(
            'format_save',
            'Kaydederken Python biçimlendir',
            '',
            self.set_format_on_save,
            'Kod',
            True).setChecked(
            self.format_on_save)
        action('python', 'Python ortamını seç…', '', self.choose_python, 'Kod')
        action('packages', 'Python ortamları ve paketler…', '', self.manage_python, 'Kod')
        action('run', '▶  Dosyayı çalıştır', 'F5', self.run_file, 'Çalıştır')
        action('args', 'Program argümanları…', '', self.choose_args, 'Çalıştır')
        action('debug', '⬡  Debug başlat', 'Ctrl+F5', self.start_debug, 'Çalıştır')
        action('continue', 'Devam et', 'F6', lambda: self.debugger.action('continue'), 'Çalıştır')
        action('next', 'Satırı geç', 'F10', lambda: self.debugger.action('next'), 'Çalıştır')
        action('step', 'İçine gir', 'F11', lambda: self.debugger.action('stepIn'), 'Çalıştır')
        action(
            'out',
            'Dışına çık',
            'Shift+F11',
            lambda: self.debugger.action('stepOut'),
            'Çalıştır')
        action('pause', 'Duraklat', '', lambda: self.debugger.pause(), 'Çalıştır')
        action('stop', '■  Durdur', 'Shift+F5', self.stop_execution, 'Çalıştır')
        action(
            'breakpoint',
            'Kesme noktası aç/kapat',
            'F9',
            self.toggle_current_breakpoint,
            'Çalıştır')
        action('split', 'Editörü böl / birleştir', 'Ctrl+\\', self.toggle_split, 'Görünüm')
        action(
            'sidebar',
            'Kenar panelini aç/kapat',
            'Ctrl+B',
            lambda: self.sidebar.setVisible(
                not self.sidebar.isVisible()),
            'Görünüm')
        action(
            'bottom',
            'Alt paneli aç/kapat',
            'Ctrl+J',
            lambda: self.bottom.setVisible(
                not self.bottom.isVisible()),
            'Görünüm')
        action('settings', 'Ayarlar…', '', self.preferences, 'Görünüm')
        action('git', 'Git değişikliklerini yenile', '', self.refresh_git, 'Görünüm')
        action('git_init', 'Git deposu başlat…', '', self.git_init, 'Dosya')
        action('refs', 'Sembolün kullanıldığı yerleri bul', 'Shift+F12', self.references, 'Kod')
        action('symbols', 'Dosyadaki fonksiyon ve sınıflar…',
               'Ctrl+Shift+M', self.document_symbols, 'Kod')
        action('project_symbols', 'Projede sembol ara…', 'Ctrl+T', self.project_symbols, 'Kod')
        action('merge_conflicts', 'Git çakışmalarını çöz…', '', self.resolve_conflicts, 'Kod')
        action('breakpoints', 'Kesme noktalarını yönet…', '', self.show_breakpoints, 'Çalıştır')
        action('back', 'Önceki kod konumu', 'Alt+Left', lambda: self.navigate_history(-1), 'Kod')
        action(
            'forward',
            'Sonraki kod konumu',
            'Alt+Right',
            lambda: self.navigate_history(1),
            'Kod')
        action('project_settings', 'Proje ayarları…', '', self.project_preferences, 'Dosya')
        action(
            'stage_lines',
            'Seçili satırları Git için hazırla…',
            '',
            self.stage_selected_lines,
            'Kod')
        action('update', 'Güncelleme paketini uygula…', '', self.install_update, 'Dosya')
        action('palette', 'Komut paleti…', 'Ctrl+Shift+P', self.command_palette, 'Görünüm')
        action('tests', 'Test panelini aç', 'Ctrl+Alt+T', self.show_tests, 'Çalıştır')
        action(
            'condition',
            'Koşullu kesme noktası…',
            'Shift+F9',
            self.edit_breakpoint_condition,
            'Çalıştır')
        action(
            'recovery',
            'Oturumu şimdi yedekle',
            '',
            lambda: self.checkpoint(
                force=True),
            'Dosya')
        action('terminal', 'Terminali aç', 'Ctrl+`', self.show_terminal, 'Görünüm')
        action('new_terminal', 'Yeni terminal sekmesi', '', self.new_terminal, 'Görünüm')
        action('project_trust', 'Proje güveni…', '', self.show_project_trust, 'Dosya')
        action('fold', 'Bloğu katla/aç', 'Ctrl+Shift+[', self.toggle_fold, 'Görünüm')
        action('unfold', 'Tüm blokları aç', 'Ctrl+Shift+]', self.unfold_all, 'Görünüm')
        action('minimap', 'Minimap göster/gizle', '', self.toggle_minimap, 'Görünüm')
        toolbar = QToolBar('Araçlar')
        toolbar.setObjectName('mainToolbar')
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        short_names = {'project': 'Proje', 'open': 'Aç', 'save': 'Kaydet', 'split': 'Böl',
                       'python': 'Python ortamı', 'run': 'Çalıştır', 'debug': 'Debug',
                       'continue': 'Devam', 'next': 'Adım', 'stop': 'Durdur'}

        def toolbar_action(key):
            original = self.actions[key]
            item = QAction(short_names[key], self)
            item.setIcon(original.icon())
            item.setToolTip(original.text() + (' (' + original.shortcut().toString() +
                            ')' if not original.shortcut().isEmpty() else ''))
            item.triggered.connect(original.trigger)
            original.changed.connect(
                lambda item=item,
                original=original: item.setIcon(
                    original.icon()))
            toolbar.addAction(item)
        for key in ['project', 'open', 'save', 'split']:
            toolbar_action(key)
        spacer = QWidget()
        from PySide6.QtWidgets import QSizePolicy
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        from atelier.ui.profile_selector import ProfileSelector
        self.profile_selector = ProfileSelector(self)
        for key in ['python', 'run', 'debug', 'continue', 'next', 'stop']:
            if key == 'run':
                toolbar.addWidget(self.profile_selector)
            toolbar_action(key)
        try:
            mapping = json.loads(self.settings.value('shortcuts', '{}'))
            if 'reopen_tab' not in mapping and mapping.get('tests') == 'Ctrl+Shift+T':
                mapping.pop('tests')
            for key, value in mapping.items():
                if key in self.actions:
                    self.actions[key].setShortcut(value)
        except (ValueError, TypeError):
            pass

    def set_editor_indentation(self, editor):
        language = getattr(editor, 'language', 'python')
        editor.indent_width = 2 if language in (
            WEB_FORMAT_LANGUAGES | VALIDATED_LANGUAGES) else self.tab_width
        editor.setTabStopDistance(editor.fontMetrics().horizontalAdvance(' ') * editor.indent_width)

    def style_editor(self, editor):
        editor.auto_completion = self.auto_complete
        editor.show_active_guide = self.active_guide
        editor.minimap_enabled = self.minimap_visible and not getattr(editor, 'large_file', False)
        editor.minimap.setVisible(editor.minimap_enabled)
        family = self.font_family.replace('"', '').replace(';', '')
        editor.setStyleSheet(
            f'QPlainTextEdit {{ font-family: "{family}"; font-size: {self.font_size}pt; }}')
        editor.setFont(QFont(self.font_family, self.font_size))
        self.set_editor_indentation(editor)
        from pygments.styles import get_style_by_name
        editor.highlighter.style = get_style_by_name(
            'monokai' if self.theme == 'Gece' else 'friendly')
        editor.highlighter.rehighlight()
        editor.update_gutter_margin()

    def apply_theme(self):
        colors = PALETTES[self.theme]
        palette = QPalette()
        for role, key in [(QPalette.ColorRole.Window, 'bg'), (QPalette.ColorRole.WindowText, 'text'), (QPalette.ColorRole.Base, 'editor'),
                          (QPalette.ColorRole.AlternateBase, 'panel'), (QPalette.ColorRole.Text,
                                                                        'text'), (QPalette.ColorRole.Button, 'panel'),
                          (QPalette.ColorRole.ButtonText, 'text'), (QPalette.ColorRole.Highlight,
                                                                    'selection'), (QPalette.ColorRole.HighlightedText, 'text'),
                          (QPalette.ColorRole.ToolTipBase, 'panel'), (QPalette.ColorRole.ToolTipText, 'text'), (QPalette.ColorRole.PlaceholderText, 'muted'), (QPalette.ColorRole.Link, 'accent')]:
            palette.setColor(role, QColor(colors[key]))
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText,
                     QPalette.ColorRole.WindowText):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors['muted']))
        palette.setColor(QPalette.ColorRole.Mid, QColor(colors['border']))
        QApplication.instance().setPalette(palette)
        QApplication.instance().setStyleSheet(stylesheet(self.theme))
        color = '#4969d9' if self.theme == 'Açık' else '#9cb5e8'
        for key, action in self.actions.items():
            action.setIcon(icon(key, color))
        for button in self.findChildren(QPushButton):
            if button.property('materialButton'):
                button.setIcon(for_text(button.text(), color))
        for doc in self.documents:
            self.style_editor(doc.editors[0])
            for editor in doc.editors[1:]:
                self.style_editor(editor)
            doc.paint_diagnostics()
            doc.render_markdown()

    def preferences(self):
        from atelier.ui.settings import SettingsDialog
        SettingsDialog(self).exec()

    def update_position(self):
        if self.editor:
            cursor = self.editor.textCursor()
            kind = self.current.language
            language = {'text': 'Metin', 'javascript': 'JavaScript', 'python': 'Python',
                        'markdown': 'Markdown'}.get(kind, kind.upper())
            mode = ' · Büyük dosya modu' if self.current.large_file else ''
            self.position_label.setText(
                f'Satır {
                    cursor.blockNumber() +
                    1}, Sütun {
                    cursor.positionInBlock() +
                    1}    {language}{mode}')

    def show_text(self, title, text):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(950, 650)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit(readOnly=True)
        view.setPlainText(text)
        view.setStyleSheet('font-family:Consolas; font-size:11pt;')
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def command_palette(self):
        CommandPalette(self).exec()

    def show_tests(self):
        self.bottom.show()
        self.bottom.setCurrentWidget(self.test_panel)

    def goto_test(self, path, line):
        self.remember_location()
        doc = self.open_path(path)
        if doc:
            self.goto(doc, {'line': line, 'character': 0}, record=False)
            self.remember_location()
