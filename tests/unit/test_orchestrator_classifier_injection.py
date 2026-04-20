"""Test that Orchestrator uses an injected classifier instance."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openmux.core.orchestrator import Orchestrator
from openmux.classifier.task_types import TaskType


class FakeClassifier:
    def __init__(self):
        self.called = False

    def classify(self, query: str):
        self.called = True
        return TaskType.CODE, 0.95


@pytest.mark.asyncio
async def test_injected_classifier_used():
    fake = FakeClassifier()
    orchestrator = Orchestrator(classifier=fake)

    # Prevent selector/fallback initialization from touching real providers
    with patch.object(orchestrator, '_initialize_selector'):
        orchestrator.selector = MagicMock()
        mock_provider = MagicMock()
        mock_provider.name = "MockProvider"
        mock_provider.generate = AsyncMock(return_value="OK")
        orchestrator.selector.select_with_fallbacks.return_value = [mock_provider]

        with patch.object(orchestrator, '_initialize_fallback'):
            # Mock router to short-circuit provider calls
            with patch.object(orchestrator.router, 'route_with_failover', new=AsyncMock(return_value=("OK", "MockProvider"))):
                result = await orchestrator._process_async("Write some code")

                assert result == "OK"
                assert fake.called is True
