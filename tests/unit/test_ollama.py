"""
Unit tests for Ollama provider.
"""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from openmux.providers.ollama import OllamaProvider
from openmux.classifier.task_types import TaskType


@pytest.fixture
def ollama_provider():
    """Create Ollama provider with default env values."""
    with patch.dict(os.environ, {"OLLAMA_URL": "http://localhost:11434", "OLLAMA_MODEL": "llama2"}):
        provider = OllamaProvider()
        yield provider


@pytest.fixture
def ollama_provider_no_env():
    """Create Ollama provider without environment variables."""
    with patch.dict(os.environ, {}, clear=True):
        if "OLLAMA_URL" in os.environ:
            del os.environ["OLLAMA_URL"]
        if "OLLAMA_MODEL" in os.environ:
            del os.environ["OLLAMA_MODEL"]
        provider = OllamaProvider()
        yield provider


class TestOllamaProviderInitialization:
    """Test Ollama provider initialization."""

    def test_init_defaults(self):
        with patch.dict(os.environ, {"OLLAMA_URL": "http://127.0.0.1:11434", "OLLAMA_MODEL": "llama2"}):
            provider = OllamaProvider()
            assert provider.base_url == "http://127.0.0.1:11434"
            assert provider.model == "llama2"
            assert provider.name == "Ollama"

    def test_init_with_explicit_args(self):
        provider = OllamaProvider(base_url="http://custom:1234", model="custom-model")
        assert provider.base_url == "http://custom:1234"
        assert provider.model == "custom-model"


class TestOllamaProviderAvailability:
    """Test availability checks (sync and async)."""

    def test_is_available_true(self, ollama_provider):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp

            assert ollama_provider.is_available() is True

    def test_is_available_false(self, ollama_provider):
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("connection error")
            assert ollama_provider.is_available() is False

    @pytest.mark.asyncio
    async def test_async_check_availability_true(self, ollama_provider):
        mock_response = AsyncMock()
        mock_response.status = 200

        # async context manager
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(ollama_provider, '_get_session', return_value=mock_session):
            result = await ollama_provider._check_availability()
            assert result is True

    @pytest.mark.asyncio
    async def test_async_check_availability_false(self, ollama_provider):
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=Exception("failed"))

        with patch.object(ollama_provider, '_get_session', return_value=mock_session):
            result = await ollama_provider._check_availability()
            assert result is False


class TestOllamaProviderCapabilities:
    """Task support and session management."""

    def test_supports_chat_and_code(self, ollama_provider):
        assert ollama_provider.supports_task(TaskType.CHAT) is True
        assert ollama_provider.supports_task(TaskType.CODE) is True

    @pytest.mark.asyncio
    async def test_session_creation_and_reuse(self, ollama_provider):
        session1 = await ollama_provider._get_session()
        assert session1 is not None
        assert isinstance(session1, aiohttp.ClientSession)

        session2 = await ollama_provider._get_session()
        assert session1 is session2

        # Cleanup
        await session1.close()


class TestOllamaProviderGenerate:
    """Tests for generating responses via Ollama API."""

    @pytest.mark.asyncio
    async def test_generate_success(self, ollama_provider):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value={"response": "Hello from Ollama"})

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(ollama_provider, '_get_session', return_value=mock_session):
            resp = await ollama_provider.generate("Say hi")
            assert "Hello from Ollama" in resp
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_stream_yields_chunks(self, ollama_provider):
        # Simulate streaming response by creating an async iterator over chunks
        class MockStream:
            def __init__(self, chunks):
                self._chunks = chunks

            async def __aiter__(self):
                for c in self._chunks:
                    yield c

        # Create a mock response with content.iter_chunked that yields utf-8 chunks
        mock_response = MagicMock()
        mock_response.status = 200
        # Create raw bytes that include newline-delimited pieces
        chunks = [b'data: Hello\n', b'data: world\n', b'data: [DONE]\n']

        async def iter_chunked(n):
            for c in chunks:
                yield c

        mock_response.content = MagicMock()
        mock_response.content.iter_chunked = iter_chunked

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(ollama_provider, '_get_session', return_value=mock_session):
            collected = []
            async for part in ollama_provider.generate_stream("Say hi"):
                collected.append(part)

            assert collected == ["Hello", "world"]

    @pytest.mark.asyncio
    async def test_generate_with_custom_parameters(self, ollama_provider):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value={"response": "ok"})

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(ollama_provider, '_get_session', return_value=mock_session):
            await ollama_provider.generate(
                "Test",
                max_tokens=50,
                temperature=0.4,
                top_p=0.8,
                model="custom-model"
            )

            call_args = mock_session.post.call_args
            payload = call_args[1]['json']
            assert payload['model'] == 'custom-model'
            assert payload['options']['num_predict'] == 50
            assert payload['options']['temperature'] == 0.4
            assert payload['options']['top_p'] == 0.8

    @pytest.mark.asyncio
    async def test_generate_http_error_raises(self, ollama_provider):
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("Server error"))

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(ollama_provider, '_get_session', return_value=mock_session):
            from openmux.utils.exceptions import APIError

            with pytest.raises(APIError):
                await ollama_provider.generate("fail")

    @pytest.mark.asyncio
    async def test_generate_malformed_response_returns_str(self, ollama_provider):
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = AsyncMock()
        mock_response.json = AsyncMock(return_value={"unexpected": "format"})

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(ollama_provider, '_get_session', return_value=mock_session):
            resp = await ollama_provider.generate("Test")
            assert isinstance(resp, str)


class TestOllamaProviderCleanup:
    """Cleanup and context manager tests."""

    @pytest.mark.asyncio
    async def test_close_closes_session(self, ollama_provider):
        session = await ollama_provider._get_session()
        assert not session.closed

        await ollama_provider.close()
        assert session.closed

    @pytest.mark.asyncio
    async def test_context_manager(self):
        with patch.dict(os.environ, {"OLLAMA_URL": "http://localhost:11434", "OLLAMA_MODEL": "llama2"}):
            async with OllamaProvider() as provider:
                # We won't actually call the network here; just ensure provider is usable
                assert provider.name == "Ollama"
