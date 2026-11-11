"""Persist project paths and pins in the editor's local settings."""

import json
import os
from pathlib import Path


class RecentProjects:
    settings_key = "projects/recent"
    limit = 15

    def __init__(self, settings):
        self.settings = settings

    def entries(self):
        try:
            records = json.loads(self.settings.value(self.settings_key, "[]"))
        except (TypeError, ValueError):
            return []
        if not isinstance(records, list):
            return []
        return [
            record
            for record in records
            if isinstance(record, dict) and isinstance(record.get("path"), str)
            and isinstance(record.get("pinned"), bool) and Path(record["path"]).is_absolute()
        ]

    def _save(self, records):
        pinned = [record for record in records if record["pinned"]]
        unpinned = [record for record in records if not record["pinned"]]
        self.settings.setValue(self.settings_key, json.dumps(
            pinned + unpinned[:self.limit], ensure_ascii=False))

    def touch(self, path):
        path = str(path.resolve())
        records = self.entries()
        same = os.path.normcase(path)
        pinned = any(record["pinned"]
                     for record in records if os.path.normcase(record["path"]) == same)
        records = [record for record in records if os.path.normcase(record["path"]) != same]
        self._save([{"path": path, "pinned": pinned}, *records])

    def toggle_pin(self, path):
        records = self.entries()
        for record in records:
            if record["path"] == path:
                record["pinned"] = not record["pinned"]
                self._save(records)
                return

    def forget(self, path):
        self._save([record for record in self.entries() if record["path"] != path])
