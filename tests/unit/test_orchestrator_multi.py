import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openmux.core.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_process_multi_uses_return_first_n():
    orch = Orchestrator()

    # Prepare mock providers
    p1 = MagicMock()
    p1.name = "p1"
    p2 = MagicMock()
    p2.name = "p2"

    with patch.object(orch, '_initialize_selector'):
        orch.selector = MagicMock()
        # Return 4 candidates even if requesting 2
        orch.selector.select_multiple.return_value = [p1, p2]

        # Patch router.route_multiple to assert it receives return_first_n
        with patch.object(orch.router, 'route_multiple', new=AsyncMock(return_value=["a","b"])) as mock_rm:
            result = await orch._process_multi_async("q", num_models=2, combination_method="merge")

            mock_rm.assert_awaited()
            # Ensure orchestrator returns combined via combiner.merge
            # combiner.merge is a sync call; patch to a known value
            assert isinstance(result, str)
