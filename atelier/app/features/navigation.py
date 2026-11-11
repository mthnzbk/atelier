"""Main-window navigation actions."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem
from atelier.ui.icons import icon
from atelier.languages.locations import uri_path


class NavigationFeatures:
    def goto(self, doc, position, record=True):
        if record:
            self.remember_location()
        self.tabs.setCurrentWidget(doc)
        cursor = doc.editor.textCursor()
        doc.editor.reveal_line(position['line'])
        cursor.setPosition(doc.editor.offset(position))
        doc.editor.setTextCursor(cursor)
        doc.editor.centerCursor()
        doc.editor.setFocus()
        if record:
            self.remember_location()

    def toggle_split(self):
        doc = self.current
        if not doc:
            return
        if len(doc.editors) == 1:
            doc.add_view()
            doc.splitter.setSizes([500, 500])
            doc.paint_diagnostics()
        else:
            extra = doc.editors.pop()
            doc.active_editor = doc.editors[0]
            extra.setParent(None)
            extra.deleteLater()
            doc.editor.setFocus()

    def toggle_fold(self):
        if self.editor:
            line = self.editor.textCursor().blockNumber()
            structure = self.editor.structure
            if line not in structure.regions:
                enclosing = [start for start, end in structure.regions.items() if start <=
                             line <= end]
                if enclosing:
                    line = max(enclosing)
            structure.toggle(line)

    def unfold_all(self):
        if self.editor:
            self.editor.structure.folded.clear()
            self.editor.structure.apply()

    def toggle_minimap(self):
        enabled = not self.minimap_visible
        self.minimap_visible = enabled
        self.settings.setValue('minimap', enabled)
        for doc in self.documents:
            for editor in doc.editors:
                editor.minimap_enabled = enabled and not doc.large_file
                editor.minimap.setVisible(editor.minimap_enabled)
                editor.update_gutter_margin()

    def quick_open(self):
        from atelier.ui.quick_open import QuickOpen
        QuickOpen(self).exec()

    def remember_location(self):
        if not self.current:
            return
        cursor = self.editor.textCursor()
        location = (self.current.uri, cursor.blockNumber(), cursor.positionInBlock())
        if 0 <= self.navigation_index < len(
                self.navigation_history) and self.navigation_history[self.navigation_index] == location:
            return
        self.navigation_history = self.navigation_history[:self.navigation_index + 1] + [location]
        self.navigation_history = self.navigation_history[-200:]
        self.navigation_index = len(self.navigation_history) - 1

    def navigate_history(self, delta):
        if not self.navigation_history:
            return
        target = self.navigation_index + delta
        if not 0 <= target < len(self.navigation_history):
            return
        uri, line, column = self.navigation_history[target]
        doc = next(
            (d for d in self.documents if d.uri == uri),
            None) or self.open_path(
            uri_path(uri))
        if doc:
            self.navigation_index = target
            self.goto(doc, {'line': line, 'character': column}, record=False)

    def show_locations(self, title, locations):
        self.navigation_results.clear()
        self.navigation_filter.clear()
        for label, uri, position in locations:
            item = QListWidgetItem(label)
            item.setIcon(icon('definition'))
            item.setData(Qt.ItemDataRole.UserRole, (uri, position))
            self.navigation_results.addItem(item)
        self.bottom.setTabText(self.bottom.indexOf(self.navigation_panel),
                               title + ' · ' + str(len(locations)))
        self.bottom.show()
        self.bottom.setCurrentWidget(self.navigation_panel)

    def open_navigation_result(self, item):
        uri, position = item.data(Qt.ItemDataRole.UserRole)
        self.remember_location()
        doc = next(
            (d for d in self.documents if d.uri == uri),
            None) or self.open_path(
            uri_path(uri))
        if doc:
            self.goto(doc, position, record=False)
            self.remember_location()

    def references(self):
        doc = self.current
        if not doc or not self.lsp.initialized or doc.language != 'python':
            return
        self.sync_document(doc)
        cursor = doc.editor.textCursor()

        def receive(result):
            rows = []
            for location in result or []:
                position = location['range']['start']
                path = uri_path(location['uri'])
                rows.append((f'{path.name}:{position["line"] +
                                            1}:{position["character"] +
                                                1}    {path.parent}', location['uri'], position))
            self.show_locations('Kullanımlar', rows)
        self.lsp.request('textDocument/references', {'textDocument': {'uri': doc.uri},
                                                     'position': {'line': cursor.blockNumber(), 'character': cursor.positionInBlock()},
                                                     'context': {'includeDeclaration': True}}, receive)

    def document_symbols(self):
        doc = self.current
        if not doc or doc.large_file or not self.lsp.initialized or doc.language != 'python':
            return
        self.sync_document(doc)

        def receive(result):
            rows = []

            def flatten(symbols, depth=0):
                for symbol in symbols or []:
                    location = symbol.get('location')
                    uri = location['uri'] if location else doc.uri
                    region = location['range'] if location else symbol.get(
                        'selectionRange', symbol['range'])
                    rows.append(('    ' *
                                 depth +
                                 symbol['name'] +
                                 '    · ' +
                                 str(region['start']['line'] +
                                     1), uri, region['start']))
                    flatten(symbol.get('children', []), depth + 1)
            flatten(result)
            self.show_locations('Semboller', rows)
        self.lsp.request('textDocument/documentSymbol', {'textDocument': {'uri': doc.uri}}, receive)

    def project_symbols(self):
        from atelier.ui.symbol_search import SymbolSearch
        dialog = SymbolSearch(self)
        dialog.exec()
        dialog.deleteLater()
