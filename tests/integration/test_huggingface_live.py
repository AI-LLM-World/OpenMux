"""
Live API integration tests for HuggingFace provider.

These tests require HF_TOKEN in environment. They make actual API calls
to the HuggingFace Inference API and are skipped when HF_TOKEN is not set.
"""
import pytest
import os
from openmux import Orchestrator, TaskType


# Skip tests if HF_TOKEN is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("HF_TOKEN"),
    reason="HF_TOKEN not set - skipping live HuggingFace tests"
)


class TestLiveHuggingFaceBasics:
    """Basic integration tests against HuggingFace Inference API."""

    def test_simple_chat_query(self):
        orchestrator = Orchestrator()
        response = orchestrator.process(
            "Say 'Hello from HuggingFace' and nothing else",
            task_type=TaskType.CHAT
        )

        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0

    def test_embeddings_call(self):
        orchestrator = Orchestrator()
        response = orchestrator.process(
            "Test embeddings",
            task_type=TaskType.EMBEDDINGS
        )

        # Embeddings are returned as a string representation
        assert response is not None
        assert isinstance(response, str)
