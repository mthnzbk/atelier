"""pytest process helper; machine events share stdout with normal test output."""
import json
import sys
import os
from pathlib import Path


def emit(**value):
    print('\n@@ATELIER@@' + json.dumps(value, ensure_ascii=True), flush=True)


class Reporter:
    def pytest_collection_finish(self, session):
        emit(collected=[{'id': item.nodeid, 'path': str(item.path),
             'line': item.location[1]} for item in session.items])

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed or report.skipped:
            crash = getattr(report.longrepr, 'reprcrash', None)
            emit(result={'id': report.nodeid, 'outcome': report.outcome,
                         'detail': str(report.longrepr) if report.longrepr else '',
                         'path': str(crash.path) if crash else None, 'line': crash.lineno - 1 if crash else None})


if __name__ == '__main__':
    vendor = Path(__file__).resolve().with_name('vendor')
    if vendor.is_dir():
        sys.path.append(str(vendor))
    try:
        import pytest
    except ImportError:
        emit(error='Seçili Python ortamında pytest yok. Terminalde python -m pip install pytest çalıştırın.')
        sys.exit(1)
    arguments = ['--color=no', '-q', '--tb=short', '-p', 'no:cacheprovider']
    if sys.argv[1] == 'collect':
        arguments += ['--collect-only']
    if len(sys.argv) > 2:
        arguments.extend(sys.argv[2:])
    cov = None
    if os.environ.get('ATELIER_COVERAGE') == '1' and sys.argv[1] != 'collect':
        try:
            import coverage
            cov = coverage.Coverage(
                data_file=None, timid=Path(coverage.__file__).is_relative_to(vendor), source=[
                    os.getcwd()], omit=[
                    '*/test_*.py', '*/tests/*'])
            cov.start()
        except ImportError:
            emit(error='Kapsam için seçili ortamda coverage kurun: python -m pip install coverage')
    code = pytest.main(arguments, plugins=[Reporter()])
    if cov:
        cov.stop()
        rows = []
        for filename in cov.get_data().measured_files():
            try:
                _, statements, _, missing, _ = cov.analysis2(filename)
                rows.append({'path': filename, 'executed': sorted(
                    set(statements) - set(missing)), 'missing': missing})
            except Exception:
                continue
        emit(coverage=rows)
    sys.exit(code)
