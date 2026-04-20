import sys
import types
import importlib


def _make_fake_orchestrator(return_value: str = "fake response"):
    mod = types.ModuleType("openmux.core.orchestrator")
    from typing import Optional

    class FakeOrchestrator:
        def __init__(self, *args, **kwargs):
            self._last = {}

        def process(self, query, task_type=None, **kwargs):
            # Record inputs for assertions and return a canned response
            self._last["query"] = query
            self._last["task_type"] = task_type
            self._last["kwargs"] = kwargs
            return return_value
        
        async def _process_async(self, query, task_type=None, **kwargs):
            # Async variant used by acreate
            self._last["query"] = query
            self._last["task_type"] = task_type
            self._last["kwargs"] = kwargs
            return return_value

    # Also supply a fake exceptions module so the mapper import works in tests
    exc_mod = types.ModuleType("openmux.utils.exceptions")
    class FakeAPIError(Exception):
        def __init__(self, provider_name: str, status_code: Optional[int] = None, message: Optional[str] = None, response_text: Optional[str] = None):
            self.status_code = status_code
            super().__init__(message or "api error")

    setattr(exc_mod, "APIError", FakeAPIError)
    setattr(exc_mod, "ProviderUnavailableError", Exception)
    setattr(exc_mod, "NoProvidersAvailableError", Exception)
    setattr(exc_mod, "FailoverError", Exception)
    setattr(exc_mod, "TimeoutError", Exception)
    setattr(exc_mod, "ModelNotFoundError", Exception)
    setattr(exc_mod, "ProviderError", Exception)
    setattr(exc_mod, "ConfigurationError", Exception)

    # Attach to the fake module
    setattr(mod, "Orchestrator", FakeOrchestrator)
    # Minimal TaskType enum substitute
    tt_mod = types.ModuleType("openmux.classifier.task_types")
    class TaskType:
        CHAT = "chat"
        EMBEDDINGS = "embeddings"

    setattr(tt_mod, "TaskType", TaskType)

    return mod, tt_mod, exc_mod


def test_chat_completion_create():
    fake_orch_mod, fake_tt_mod, fake_exc_mod = _make_fake_orchestrator("hello from fake orch")

    # Inject fake modules before importing the compatibility shim so its
    # lazy imports pick up the fakes.
    sys.modules["openmux.core.orchestrator"] = fake_orch_mod
    sys.modules["openmux.classifier.task_types"] = fake_tt_mod
    sys.modules["openmux.utils.exceptions"] = fake_exc_mod

    try:
        import importlib
        # Ensure we import a fresh copy
        if "openmux.openai_compat" in sys.modules:
            del sys.modules["openmux.openai_compat"]
        openai_compat = importlib.import_module("openmux.openai_compat")

        res = openai_compat.ChatCompletion.create(messages=[{"role": "user", "content": "Hi"}])

        assert isinstance(res, dict)
        assert "choices" in res
        assert res["choices"][0]["message"]["content"] == "hello from fake orch"
    finally:
        for k in ("openmux.core.orchestrator", "openmux.classifier.task_types", "openmux.openai_compat"):
            if k in sys.modules:
                del sys.modules[k]


def test_embeddings_create_parses_vector():
    # Make orchestrator return a JSON array string
    fake_orch_mod, fake_tt_mod, fake_exc_mod = _make_fake_orchestrator("[0.1, 0.2, 0.3]")
    sys.modules["openmux.core.orchestrator"] = fake_orch_mod
    sys.modules["openmux.classifier.task_types"] = fake_tt_mod
    sys.modules["openmux.utils.exceptions"] = fake_exc_mod

    try:
        import importlib
        if "openmux.openai_compat" in sys.modules:
            del sys.modules["openmux.openai_compat"]
        openai_compat = importlib.import_module("openmux.openai_compat")

        res = openai_compat.Embeddings.create(input="unused text")

        assert isinstance(res, dict)
        assert "data" in res
        assert isinstance(res["data"][0]["embedding"], list)
        assert res["data"][0]["embedding"] == [0.1, 0.2, 0.3]
    finally:
        for k in ("openmux.core.orchestrator", "openmux.classifier.task_types", "openmux.openai_compat"):
            if k in sys.modules:
                del sys.modules[k]


def test_chat_create_stream_and_async():
    # orchestrator to return a simple string
    fake_orch_mod, fake_tt_mod, fake_exc_mod = _make_fake_orchestrator("streamable response")
    sys.modules["openmux.core.orchestrator"] = fake_orch_mod
    sys.modules["openmux.classifier.task_types"] = fake_tt_mod
    sys.modules["openmux.utils.exceptions"] = fake_exc_mod

    try:
        import importlib, asyncio
        if "openmux.openai_compat" in sys.modules:
            del sys.modules["openmux.openai_compat"]
        openai_compat = importlib.import_module("openmux.openai_compat")

        # synchronous streaming generator
        gen = openai_compat.ChatCompletion.create(messages=[{"role": "user", "content": "Hi"}], stream=True)
        # gen should be an iterator
        chunks = list(gen)
        assert len(chunks) == 2
        assert "delta" in chunks[0]["choices"][0]

        # test async creation
        async def run_async():
            res = await openai_compat.ChatCompletion.acreate(messages=[{"role": "user", "content": "Hi"}])
            assert isinstance(res, dict)
            assert res["choices"][0]["message"]["content"] == "streamable response"

        asyncio.get_event_loop().run_until_complete(run_async())

    finally:
        for k in ("openmux.core.orchestrator", "openmux.classifier.task_types", "openmux.openai_compat"):
            if k in sys.modules:
                del sys.modules[k]
