from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from pathlib import Path
import os

from openmux.cli import main as cli_main
from openmux.cli.main import app


def run():
    tmp_path = Path.cwd() / "tmp_test_home"
    if tmp_path.exists():
        for p in tmp_path.rglob('*'):
            try:
                if p.is_file():
                    p.unlink()
            except Exception:
                pass
    else:
        tmp_path.mkdir(parents=True)

    os.environ['HOME'] = str(tmp_path)
    os.environ['USERPROFILE'] = str(tmp_path)

    # Ensure CLI writes history under the temp HOME we're setting
    cli_main._HISTORY_DIR = Path(tmp_path) / ".openmux"
    cli_main._HISTORY_FILE = cli_main._HISTORY_DIR / "history.jsonl"

    mock_orch = MagicMock()

    async def _gen():
        yield "a"
        yield "b"

    mock_orch.process_stream.return_value = _gen()
    mock_orch.__enter__.return_value = mock_orch
    mock_orch.__exit__.return_value = False
    mock_orch._last_stream_provider = "mocked"

    with patch('openmux.cli.main.Orchestrator', return_value=mock_orch):
        runner = CliRunner()
        result = runner.invoke(app, ["chat", "Hello", "--stream"])
        print('exit_code=', result.exit_code)
        print('output=')
        print(result.output)

    print('history exists=', cli_main._HISTORY_FILE.exists())
    if cli_main._HISTORY_FILE.exists():
        print(cli_main._HISTORY_FILE.read_text())


if __name__ == '__main__':
    run()
