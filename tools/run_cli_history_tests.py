import tempfile
import json
from pathlib import Path

import sys
from pathlib import Path as _Path
# Ensure project root is on sys.path so imports work when run from tools/
ROOT = str(_Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib
cli_main = importlib.import_module('openmux.cli.main')


def run():
    tmp = tempfile.mkdtemp()

    # Test append
    hist_file = Path(tmp) / 'history.jsonl'
    setattr(cli_main, '_HISTORY_DIR', Path(tmp))
    setattr(cli_main, '_HISTORY_FILE', hist_file)
    cli_main._append_history_entry('Hello world', 'AI response', provider='openrouter')
    assert hist_file.exists()
    lines = hist_file.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry['query'] == 'Hello world'
    assert entry['response'] == 'AI response'
    assert entry['provider'] == 'openrouter'

    # Test export
    hist_file2 = Path(tmp) / 'history2.jsonl'
    entry = {"timestamp": "2020-01-01T00:00:00Z", "query": "Q", "response": "R", "provider": "P"}
    hist_file2.write_text(json.dumps(entry) + '\n', encoding='utf-8')
    setattr(cli_main, '_HISTORY_FILE', hist_file2)
    export_path = Path(tmp) / 'export.jsonl'
    try:
        cli_main.history(show=False, export=export_path, limit=10)
    except Exception:
        # typer.Exit expected, ignore
        pass
    assert export_path.exists()
    assert export_path.read_text(encoding='utf-8') == hist_file2.read_text(encoding='utf-8')


if __name__ == '__main__':
    run()
    print('tools/run_cli_history_tests: OK')
