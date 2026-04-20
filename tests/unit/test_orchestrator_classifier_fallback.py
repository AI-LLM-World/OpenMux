"""Test that Orchestrator falls back to CHAT when classifier raises."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openmux.core.orchestrator import Orchestrator
from openmux.classifier.task_types import TaskType


class RaisingClassifier:
    def classify(self, query: str):
        raise RuntimeError("classifier failed")


@pytest.mark.asyncio
async def test_classifier_exception_falls_back_to_chat():
    fake = RaisingClassifier()
    orchestrator = Orchestrator(classifier=fake)

    with patch.object(orchestrator, '_initialize_selector'):
        orchestrator.selector = MagicMock()

        mock_provider = MagicMock()
        mock_provider.name = "MockProvider"
        mock_provider.generate = AsyncMock(return_value="OK")

        # Track the task_type that selector was asked for
        orchestrator.selector.select_with_fallbacks = MagicMock(return_value=[mock_provider])

        with patch.object(orchestrator, '_initialize_fallback'):
            with patch.object(orchestrator.router, 'route_with_failover', new=AsyncMock(return_value=("OK", "MockProvider"))):
                result = await orchestrator._process_async("Some query that triggers classifier error")

                assert result == "OK"

                # Ensure selector was asked to select providers for CHAT after classifier failure
                assert orchestrator.selector.select_with_fallbacks.call_count == 1
                called_args = orchestrator.selector.select_with_fallbacks.call_args[0]
                assert called_args[0] == TaskType.CHAT
