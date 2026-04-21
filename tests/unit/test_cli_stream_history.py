"""Unit tests for CLI streaming history attribution."""
from typer.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import importlib
cli_main = importlib.import_module('openmux.cli.main')
from openmux.cli.main import app


def test_cli_stream_history_tmp(tmp_path, monkeypatch):
    runner = CliRunner()

    # Monkeypatch home dir so history goes to tmp_path/.openmux
    # On Windows Path.home() reads USERPROFILE; set both for portability
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))

    # Ensure CLI writes history under the temp HOME we're setting
    cli_main._HISTORY_DIR = Path(tmp_path) / ".openmux"
    cli_main._HISTORY_FILE = cli_main._HISTORY_DIR / "history.jsonl"

    # Create a mock orchestrator with process_stream yielding chunks
    mock_orch = MagicMock()

    async def _gen():
        yield "a"
        yield "b"

    mock_orch.process_stream.return_value = _gen()
    mock_orch.__enter__.return_value = mock_orch
    mock_orch.__exit__.return_value = False
    mock_orch._last_stream_provider = "mocked"

    with patch('openmux.cli.main.Orchestrator', return_value=mock_orch):
        result = runner.invoke(app, ["chat", "Hello", "--stream"])

    assert result.exit_code == 0

    # Ensure history file created and contains provider attribution
    history_file = Path(tmp_path) / ".openmux" / "history.jsonl"
    assert history_file.exists()
    content = history_file.read_text()
    assert "mocked" in content
