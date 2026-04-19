import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
import email.utils

from openmux.providers.huggingface import HuggingFaceProvider
from openmux.utils.exceptions import APIError


@pytest.mark.asyncio
async def test_huggingface_parses_numeric_retry_after():
    provider = HuggingFaceProvider(api_token="hf_test")

    # Mock a 429 response with numeric Retry-After header
    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.text = AsyncMock(return_value="Rate limit")
    mock_response.headers = {"Retry-After": "5"}

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_cm)

    with patch.object(provider, '_get_session', return_value=mock_session):
        with pytest.raises(APIError) as excinfo:
            await provider.generate("Test")

        assert excinfo.value.status_code == 429
        assert excinfo.value.parsed_retry_after == 5


@pytest.mark.asyncio
async def test_huggingface_parses_httpdate_retry_after():
    provider = HuggingFaceProvider(api_token="hf_test")

    # Create a Retry-After HTTP-date ~10 seconds in the future
    future_dt = datetime.now(timezone.utc) + timedelta(seconds=10)
    header_date = email.utils.format_datetime(future_dt)

    mock_response = AsyncMock()
    mock_response.status = 429
    mock_response.text = AsyncMock(return_value="Rate limit")
    mock_response.headers = {"Retry-After": header_date}

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_cm)

    with patch.object(provider, '_get_session', return_value=mock_session):
        with pytest.raises(APIError) as excinfo:
            await provider.generate("Test")

        assert excinfo.value.status_code == 429
        # parsed_retry_after should be approximately 10 seconds (allow 1s tolerance)
        parsed = excinfo.value.parsed_retry_after
        assert parsed is not None
        assert abs(parsed - 10) <= 1
