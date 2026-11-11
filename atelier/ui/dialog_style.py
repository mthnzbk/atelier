"""Consistent spacing and captions for Atelier's dialogs."""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QInputDialog, QMessageBox


BUTTONS = {
    QDialogButtonBox.StandardButton.Ok: ('ok', 'Tamam'),
    QDialogButtonBox.StandardButton.Cancel: ('cancel', 'İptal'),
    QDialogButtonBox.StandardButton.Close: ('close', 'Kapat'),
    QDialogButtonBox.StandardButton.Save: ('save', 'Kaydet'),
    QDialogButtonBox.StandardButton.Discard: ('discard', 'Vazgeç'),
    QDialogButtonBox.StandardButton.Yes: ('yes', 'Evet'),
    QDialogButtonBox.StandardButton.No: ('no', 'Hayır'),
    QDialogButtonBox.StandardButton.Apply: ('apply', 'Uygula'),
}


class DialogStyle(QObject):
    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.Show and isinstance(widget, QDialog) and not isinstance(widget, QFileDialog):
            self.apply(widget)
        return False

    @staticmethod
    def apply(dialog):
        if isinstance(dialog, QInputDialog):
            if dialog.okButtonText().replace('&', '').casefold() == 'ok':
                dialog.setOkButtonText('Tamam')
            if dialog.cancelButtonText().replace('&', '').casefold() == 'cancel':
                dialog.setCancelButtonText('İptal')
        elif not isinstance(dialog, QMessageBox):
            if layout := dialog.layout():
                layout.setContentsMargins(16, 16, 16, 14)
                layout.setSpacing(10)
            for form in dialog.findChildren(QFormLayout):
                form.setHorizontalSpacing(14)
                form.setVerticalSpacing(9)
                form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for box in dialog.findChildren(QDialogButtonBox):
            if box.window() is not dialog:
                continue
            for standard, (original, label) in BUTTONS.items():
                button = box.button(standard)
                if button and button.text().replace('&', '').casefold() == original:
                    button.setText(label)


def install_dialog_style():
    app = QApplication.instance()
    if not hasattr(app, '_atelier_dialog_style'):
        app._atelier_dialog_style = DialogStyle(app)
        app.installEventFilter(app._atelier_dialog_style)
