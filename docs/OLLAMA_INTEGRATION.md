OLLAMA Integration & QA Checklist
================================

Purpose
-------
This document explains how to validate the Ollama provider integration locally and how to run the gated live tests added in this branch.

Prerequisites
-------------
- A running Ollama server (local machine). Download & install: https://ollama.ai
- Python dev environment with project deps installed (see project pyproject.toml). Ensure you have pytest, pytest-asyncio, and aiohttp available.

Environment variables
---------------------
- OLLAMA_URL - Base URL of the Ollama API (default: http://localhost:11434)
- OLLAMA_MODEL - Optional default model name to prefer (e.g., "llama2")
- OLLAMA_E2E - Set to true to enable gated live tests (any truthy env value).

Run the gated live tests
------------------------
Unix / macOS (recommended):

```bash
OLLAMA_E2E=true OLLAMA_URL=http://localhost:11434 pytest tests/integration/test_ollama_live.py -q
```

PowerShell (Windows):

```powershell
$env:OLLAMA_E2E = 'true'
$env:OLLAMA_URL = 'http://localhost:11434'
pytest tests/integration/test_ollama_live.py -q
```

Manual smoke tests (Python)
--------------------------
Run a quick interactive check to confirm model discovery and generation through the provider:

```bash
python - <<'PY'
import asyncio
from openmux.providers.ollama import OllamaProvider

async def run():
    provider = OllamaProvider()
    print('Base URL:', provider.base_url)
    try:
        models = await provider.list_models()
        print('Discovered models:', models)
    except Exception as e:
        print('Model discovery failed:', e)

    try:
        resp = await provider.generate('Hello from OpenMux QA', max_tokens=8)
        print('Generate response:', resp)
    except Exception as e:
        print('Generate failed:', e)

asyncio.run(run())
PY
```

QA Checklist / Acceptance Criteria
---------------------------------
1. Model Discovery
   - list_models() succeeds and returns a list (or list-like mapping) of available models or tags.
   - If no models are present, the call should fail with an APIError (investigate server logs).

2. Basic Generate
   - provider.generate("Hello...") returns a string without raising an unexpected exception.
   - For short prompts, response should be reasonable (< 2048 chars) and non-empty.

3. Integration Tests
   - The gated test tests/integration/test_ollama_live.py should pass with OLLAMA_E2E=true.
   - Unit-level tests for the Ollama provider should pass locally (tests/unit/test_ollama.py).

4. Error Behavior
   - If the server is down, list_models() and generate() raise ProviderUnavailableError.
   - If the server returns non-200 HTTP statuses, APIError should be raised, including response_text when available.

Troubleshooting
---------------
- Connection refused / timeout: verify Ollama server is running and OLLAMA_URL is correct.
- Unexpected JSON shapes: inspect the raw response using curl or the Python smoke test above to see returned payload.
- If tests time out in CI: ensure CI runner has network access or gate live tests (we gate by OLLAMA_E2E).

Notes
-----
- The live tests are deliberately gated to avoid running against external services in normal CI.
- This doc is intentionally minimal and focused on QA steps; if you want this added to a README or a QA runbook, I can expand it and add links to Ollama docs.
