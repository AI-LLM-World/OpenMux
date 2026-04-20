"""Integration tests for Ollama provider (live).

These tests are gated by the OLLAMA_E2E environment variable to avoid running
in normal CI. To run locally against a running Ollama server set:

OLLAMA_E2E=true OLLAMA_URL=http://localhost:11434 pytest tests/integration/test_ollama_live.py -q
"""

import os
import pytest

from openmux.providers.ollama import OllamaProvider


OLLAMA_E2E = os.environ.get("OLLAMA_E2E", "false").lower() in ("1", "true", "yes")


@pytest.mark.skipif(not OLLAMA_E2E, reason="Live Ollama tests disabled")
def test_ollama_tags_and_generate():
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    provider = OllamaProvider(base_url=url)

    # Synchronous availability check (uses requests)
    assert provider.is_available(), "Ollama server must be running for live test"

    # Async generate: use asyncio run to call provider.generate
    import asyncio

    async def run():
        # Basic small call to verify generation works
        resp = await provider.generate("Hello from test", max_tokens=8)
        assert isinstance(resp, str)

    asyncio.run(run())
