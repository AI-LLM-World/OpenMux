"""Integration test for Ollama auto-select (live).

Gated by both OLLAMA_E2E=true and OLLAMA_AUTO_SELECT=true to avoid running in
standard CI. This test verifies list_models() and the auto-select heuristics
work end-to-end on a local Ollama server.
"""

import os
import pytest

from openmux.providers.ollama import OllamaProvider
from openmux.classifier.task_types import TaskType


OLLAMA_E2E = os.environ.get("OLLAMA_E2E", "false").lower() in ("1", "true", "yes")
OLLAMA_AUTO = os.environ.get("OLLAMA_AUTO_SELECT", "false").lower() in (
    "1",
    "true",
    "yes",
)


@pytest.mark.skipif(not (OLLAMA_E2E and OLLAMA_AUTO), reason="Live auto-select test disabled")
def test_ollama_auto_select_chat_and_code():
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    provider = OllamaProvider(base_url=url, auto_select=True)

    # Synchronous availability check
    assert provider.is_available(), "Ollama server must be running for live test"

    import asyncio

    async def run():
        models = await provider.list_models()
        assert models, "No models discovered from Ollama"

        sel_chat = await provider._select_model(TaskType.CHAT, {})
        sel_code = await provider._select_model(TaskType.CODE, {})

        def sel_in_models(sel, models_list):
            if isinstance(models_list, dict):
                models_list = [models_list]
            for m in models_list:
                if isinstance(m, dict):
                    if sel == m.get("id") or sel == m.get("name"):
                        return True
                else:
                    if sel == m:
                        return True
            return False

        assert sel_in_models(sel_chat, models) or sel_chat == provider.model
        assert sel_in_models(sel_code, models) or sel_code == provider.model

        # Attempt generation using auto-selected models
        resp_chat = await provider.generate(
            "Hello from auto-select test", task_type=TaskType.CHAT, max_tokens=8
        )
        resp_code = await provider.generate(
            "Write a hello function in python", task_type=TaskType.CODE, max_tokens=8
        )

        assert isinstance(resp_chat, str)
        assert isinstance(resp_code, str)

    asyncio.run(run())
