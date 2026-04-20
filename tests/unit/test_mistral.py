"""
Unit tests for Mistral provider.
"""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from openmux.providers.mistral import MistralProvider
from openmux.classifier.task_types import TaskType
from openmux.utils.exceptions import APIError


@pytest.fixture
def mistral_provider():
    with patch.dict(os.environ, {"MISTRAL_API_KEY": "mistral_test_key"}):
        provider = MistralProvider()
        yield provider


@pytest.fixture
def mistral_provider_no_key():
    with patch.dict(os.environ, {}, clear=True):
        if "MISTRAL_API_KEY" in os.environ:
            del os.environ["MISTRAL_API_KEY"]
        provider = MistralProvider()
        yield provider


def test_init_and_defaults(mistral_provider):
    assert mistral_provider.api_key == "mistral_test_key"
    assert mistral_provider.name == "Mistral"
    assert TaskType.CHAT in mistral_provider.default_models


def test_is_available_checks(mistral_provider, mistral_provider_no_key):
    assert mistral_provider.is_available() is True
    assert mistral_provider_no_key.is_available() is False


@pytest.mark.asyncio
async def test_session_and_generate(mistral_provider):
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=[{"generated_text": "Hi from Mistral"}])

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_cm)

    with patch.object(mistral_provider, '_get_session', return_value=mock_session):
        resp = await mistral_provider.generate("Hello", task_type=TaskType.CHAT)
        assert "Hi from Mistral" in resp
        mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_generate_without_key_raises(mistral_provider_no_key):
    with pytest.raises(Exception, match="API key not configured"):
        await mistral_provider_no_key.generate("Test")


@pytest.mark.asyncio
async def test_close_context_manager():
    with patch.dict(os.environ, {"MISTRAL_API_KEY": "mistral_test_key"}):
        async with MistralProvider() as provider:
            assert provider.is_available()
            session = await provider._get_session()
            assert isinstance(session, aiohttp.ClientSession)
        assert session.closed


@pytest.mark.asyncio
async def test_generate_with_http_error(mistral_provider):
    """Test that non-200 responses raise APIError and status_code is propagated."""
    mock_response = MagicMock()
    mock_response.status = 429
    mock_response.text = AsyncMock(return_value="Rate limit exceeded")

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_cm)

    with patch.object(mistral_provider, '_get_session', return_value=mock_session):
        with pytest.raises(APIError) as excinfo:
            await mistral_provider.generate("test query", TaskType.CHAT)

        assert excinfo.value.status_code == 429


@pytest.mark.asyncio
async def test_generate_with_malformed_response(mistral_provider):
    """Test handling of malformed API response (return string)."""
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"unexpected": "format"})

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_cm)

    with patch.object(mistral_provider, '_get_session', return_value=mock_session):
        response = await mistral_provider.generate("Test", task_type=TaskType.CHAT)
        assert isinstance(response, str)
