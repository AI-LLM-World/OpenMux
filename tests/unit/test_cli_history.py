import json
import pytest

from pathlib import Path

import importlib
cli_main = importlib.import_module("openmux.cli.main")


pytestmark = pytest.mark.skipif(
    not getattr(cli_main, "RICH_AVAILABLE", False),
    reason="Requires CLI dependencies (typer, rich)"
)


def test_append_history_entry_writes_jsonl(tmp_path, monkeypatch):
    """_append_history_entry should write a JSONL entry to the configured file."""
    hist_file = tmp_path / "history.jsonl"
    monkeypatch.setattr(cli_main, "_HISTORY_DIR", tmp_path)
    monkeypatch.setattr(cli_main, "_HISTORY_FILE", hist_file)

    # Call the helper
    cli_main._append_history_entry("Hello world", "AI response", provider="openrouter")

    assert hist_file.exists()
    lines = hist_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["query"] == "Hello world"
    assert entry["response"] == "AI response"
    assert entry["provider"] == "openrouter"
    assert "timestamp" in entry


def test_history_export_copies_file(tmp_path, monkeypatch):
    """The history export path should be written with the same contents as the source."""
    hist_file = tmp_path / "history.jsonl"
    entry = {"timestamp": "2020-01-01T00:00:00Z", "query": "Q", "response": "R", "provider": "P"}
    hist_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    monkeypatch.setattr(cli_main, "_HISTORY_FILE", hist_file)

    export_path = tmp_path / "export.jsonl"

    # Call the CLI function directly; it may raise typer.Exit which we ignore
    try:
        cli_main.history(show=False, export=export_path, limit=10)
    except Exception:
        # history() raises typer.Exit on success; ignore for test
        pass

    assert export_path.exists()
    assert export_path.read_text(encoding="utf-8") == hist_file.read_text(encoding="utf-8")
