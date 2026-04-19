"""
Unit tests for Together provider.
"""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from openmux.providers.together import TogetherProvider
from openmux.classifier.task_types import TaskType


@pytest.fixture
def together_provider():
    with patch.dict(os.environ, {"TOGETHER_API_KEY": "together_test_key"}):
        provider = TogetherProvider()
        yield provider


@pytest.fixture
def together_provider_no_key():
    with patch.dict(os.environ, {}, clear=True):
        if "TOGETHER_API_KEY" in os.environ:
            del os.environ["TOGETHER_API_KEY"]
        provider = TogetherProvider()
        yield provider


def test_init_and_defaults(together_provider):
    assert together_provider.api_key == "together_test_key"
    assert together_provider.name == "Together"
    assert TaskType.CHAT in together_provider.default_models


def test_is_available_checks(together_provider, together_provider_no_key):
    assert together_provider.is_available() is True
    assert together_provider_no_key.is_available() is False


@pytest.mark.asyncio
async def test_session_and_generate(together_provider):
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"generated_text": "Hello from Together"})

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_cm)

    with patch.object(together_provider, '_get_session', return_value=mock_session):
        resp = await together_provider.generate("Hello", task_type=TaskType.CHAT)
        assert "Hello from Together" in resp
        mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_generate_without_key_raises(together_provider_no_key):
    with pytest.raises(Exception, match="API key not configured"):
        await together_provider_no_key.generate("Test")


@pytest.mark.asyncio
async def test_close_context_manager():
    with patch.dict(os.environ, {"TOGETHER_API_KEY": "together_test_key"}):
        async with TogetherProvider() as provider:
            assert provider.is_available()
            session = await provider._get_session()
            assert isinstance(session, aiohttp.ClientSession)
        assert session.closed
