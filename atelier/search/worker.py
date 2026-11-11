"""Cancellable process-based project search."""
from atelier.runtime.tasks import TaskWorker


class SearchWorker(TaskWorker):
    def __init__(self, root, query, case_sensitive=False,
                 parent=None, regex=False, whole=False, globs=''):
        super().__init__('search', dict(root=str(root), query=query, case=case_sensitive,
                                        regex=regex, whole=whole, globs=globs), parent)
