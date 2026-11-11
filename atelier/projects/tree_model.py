from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileSystemModel


class ProjectModel(QFileSystemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.git_states = {}

    def set_git_states(self, states):
        previous = set(self.git_states)
        self.git_states = {str(Path(path).resolve()): state for path, state in states.items()}
        for path in previous | set(self.git_states):
            index = self.index(path)
            if index.isValid():
                self.dataChanged.emit(
                    index, index, [
                        Qt.ItemDataRole.ForegroundRole, Qt.ItemDataRole.ToolTipRole])

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and index.column() == 0:
            state = self.git_states.get(str(Path(self.filePath(index)).resolve()))
            if state and role == Qt.ItemDataRole.ForegroundRole:
                if 'U' in state or state in ('AA', 'DD'):
                    return QColor('#fb7185')
                if state == '??':
                    return QColor('#94a3b8')
                if state[1] != ' ':
                    return QColor('#fbbf24')
                return QColor('#34d399')
            if state and role == Qt.ItemDataRole.ToolTipRole:
                label = ('İzlenmeyen dosya' if state == '??' else
                         'Hazırlanmış ve hazırlanmamış değişiklikler birlikte' if state[0] != ' ' and state[1] != ' ' else
                         'Hazırlanmamış değişiklik' if state[1] != ' ' else 'Hazırlanmış, commit bekliyor')
                return self.filePath(index) + '\n' + label + ' [' + state + ']'
        return super().data(index, role)
