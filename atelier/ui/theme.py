from atelier.runtime.paths import asset_path

PALETTES = {
    'Gece': dict(bg='#101319', panel='#191d25', editor='#13171e', border='#303743',
                 text='#e0e7f1', muted='#a3aec0', accent='#91aaff', selection='#293e63'),
    'Açık': dict(bg='#eef1f6', panel='#f7f9fc', editor='#ffffff', border='#d6dde9',
                 text='#202a3a', muted='#52617a', accent='#3d57bc', selection='#dce6ff'),
}


def stylesheet(name):
    p = dict(PALETTES[name])
    p['assets'] = asset_path('').as_posix()
    return '''
    QWidget {{ background: {bg}; color: {text}; font-family: 'Segoe UI'; font-size: 12px; }}
    QMainWindow, QDialog {{ background: {bg}; }}
    QFrame#signatureHelp, QFrame#definitionPreview {{ background:{panel}; border:1px solid {border}; border-radius:6px; }}
    QFrame#signatureHelp QLabel {{ background:transparent; border:0; }}
    QMenuBar, QMenu, QToolBar {{ background: {panel}; }}
    QMenuBar::item {{ padding: 7px 12px; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {selection}; }}
    QMenu::item {{ padding: 7px 28px; }}
    QToolBar {{ border: 0; border-bottom: 1px solid {border}; spacing: 4px; padding: 5px 8px; }}
    QToolBar QToolButton {{ border-color:transparent; padding:5px 8px; }}
    QToolBar QToolButton:hover {{ border-color:{border}; background:{selection}; }}
    QToolButton, QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 6px; padding: 7px 11px; }}
    QToolButton:hover, QPushButton:hover {{ border-color: {accent}; background: {selection}; }}
    QToolButton:checked, QPushButton:checked {{ background: {selection}; color: {accent}; }}
    QToolButton:disabled, QPushButton:disabled {{ color: {muted}; }}
    QPlainTextEdit {{ background: {editor}; color: {text}; border: 0; selection-background-color: {selection}; font-family: Consolas; font-size: 14px; }}
    QLineEdit, QComboBox, QSpinBox {{ background: {editor}; border: 1px solid {border}; border-radius: 5px; padding: 6px; selection-background-color: {selection}; }}
    QLineEdit:focus {{ border-color: {accent}; }}
    QTextEdit, QTextBrowser {{ background:{editor}; color:{text}; border:1px solid {border}; selection-background-color:{selection}; }}
    QKeySequenceEdit {{ background:{editor}; border:1px solid {border}; border-radius:5px; min-height:34px; }}
    QKeySequenceEdit QLineEdit {{ border:0; background:transparent; min-height:26px; }}
    QAbstractSpinBox {{ min-height:26px; padding-right:20px; }}
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ background:{panel}; border-left:1px solid {border}; width:18px; }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image:url("{assets}/ui-up.svg"); width:10px; height:7px; }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image:url("{assets}/ui-down.svg"); width:10px; height:7px; }}
    QComboBox::drop-down {{ border-left:1px solid {border}; width:22px; }}
    QComboBox::down-arrow {{ image:url("{assets}/ui-down.svg"); width:12px; height:8px; }}
    QComboBox QAbstractItemView {{ background:{panel}; color:{text}; selection-background-color:{selection}; border:1px solid {border}; padding:4px; }}
    QCheckBox, QRadioButton {{ spacing:8px; padding:4px; }}
    QCheckBox::indicator, QRadioButton::indicator {{ width:16px; height:16px; border:1px solid {muted}; background:{editor}; }}
    QCheckBox::indicator {{ border-radius:3px; }}
    QRadioButton::indicator {{ border-radius:8px; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ background:{accent}; border:2px solid {selection}; }}
    QCheckBox::indicator:checked {{ image:url("{assets}/ui-check.svg"); }}
    QGroupBox {{ border:1px solid {border}; border-radius:6px; margin-top:14px; padding-top:12px; }}
    QGroupBox::title {{ subcontrol-origin:margin; left:12px; color:{muted}; padding:0 5px; }}
    QScrollArea {{ border:0; background:{bg}; }}
    QProgressBar {{ background:{editor}; border:1px solid {border}; border-radius:4px; text-align:center; min-height:18px; }}
    QProgressBar::chunk {{ background:{accent}; border-radius:3px; }}
    QSlider::groove:horizontal {{ height:4px; background:{border}; }}
    QSlider::handle:horizontal {{ width:14px; margin:-5px 0; background:{accent}; border-radius:7px; }}
    QMenu {{ border:1px solid {border}; padding:4px; }}
    QMenu::separator {{ height:1px; background:{border}; margin:5px 10px; }}
    QMenu::item:disabled {{ color:{muted}; }}
    QToolButton:focus, QPushButton:focus {{ border-color:{accent}; }}
    QTabWidget::pane {{ border: 0; }}
    QTabBar {{ background: {bg}; }}
    QTabBar::tab {{ background: {bg}; color: {muted}; padding: 7px 12px; border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ background: {editor}; color: {text}; border-bottom: 2px solid {accent}; }}
    QTabBar::tab:hover {{ background: {panel}; }}
    QTreeView, QListWidget, QTreeWidget {{ background: {panel}; border: 0; outline: 0; alternate-background-color: {bg}; }}
    QTableView {{ background:{panel}; color:{text}; gridline-color:{border}; selection-background-color:{selection}; }}
    QAbstractItemView::item:focus {{ outline:0; }}
    QToolBar::separator {{ background:{border}; width:1px; margin:5px; }}
    QDockWidget {{ titlebar-close-icon:none; color:{text}; }}
    QDockWidget::title {{ background:{panel}; padding:7px; }}
    QDialogButtonBox {{ background:transparent; }}
    QDialog QDialogButtonBox QPushButton {{ min-width:72px; }}
    QDialog QPushButton:default {{ border-color:{accent}; background:{selection}; }}
    QDialog QLabel, QDialog QCheckBox {{ font-size:13px; }}
    QDialog QLabel {{ background:transparent; }}
    QDialog QListWidget::item {{ padding:6px 8px; }}
    QDialog QGroupBox {{ border:1px solid {border}; border-radius:6px; margin-top:12px; padding:10px; }}
    QDialog QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; color:{muted}; }}
    QDialog QTreeWidget, QDialog QListWidget, QDialog QPlainTextEdit {{ border:1px solid {border}; border-radius:5px; }}
    QDialog QLineEdit, QDialog QComboBox {{ min-height:20px; }}
    QTreeView::item, QListWidget::item, QTreeWidget::item {{ padding: 5px 3px; }}
    QTreeView::item:selected, QListWidget::item:selected, QTreeWidget::item:selected {{ background: {selection}; color: {text}; }}
    QHeaderView::section {{ background: {panel}; color: {muted}; border: 0; padding: 7px; }}
    QSplitter::handle {{ background: {border}; width: 1px; height: 1px; }}
    QStatusBar {{ background: {panel}; border-top: 1px solid {border}; color: {muted}; }}
    QStatusBar::item {{ border: 0; }}
    QStatusBar QLabel {{ background:transparent; color:{muted}; padding:1px 7px; }}
    QStatusBar QPushButton, QStatusBar QToolButton {{ background:transparent; border:1px solid transparent; padding:3px 7px; }}
    QStatusBar QPushButton:hover, QStatusBar QToolButton:hover {{ background:{selection}; border-color:{border}; }}
    QScrollBar:vertical {{ width: 11px; background: {editor}; }}
    QScrollBar:horizontal {{ height: 11px; background: {editor}; }}
    QScrollBar::handle {{ background: {border}; border-radius: 4px; min-height: 25px; min-width: 25px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
    QAbstractScrollArea::corner {{ background:{panel}; border:0; }}
    QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{ color:{muted}; background:{panel}; }}
    QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; padding: 8px; }}
    QLabel#eyebrow {{ background:{panel}; color:{text}; font-weight:600; padding:8px 12px; border-bottom:1px solid {border}; }}
    QLabel#breadcrumb {{ background:{editor}; color:{muted}; padding:3px 12px; border-bottom:1px solid {border}; }}
    '''.format(**p)
