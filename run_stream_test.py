import asyncio, os
from unittest.mock import AsyncMock, MagicMock, patch
from openmux.providers.ollama import OllamaProvider

async def run_test():
    with patch.dict(os.environ, {"OLLAMA_URL": "http://localhost:11434", "OLLAMA_MODEL": "llama2"}):
        provider = OllamaProvider()

        # Create a mock response with content.iter_chunked that yields utf-8 chunks
        mock_response = MagicMock()
        mock_response.status = 200

        chunks = [b'data: Hello\\n', b'data: world\\n', b'data: [DONE]\\n']

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

        with patch.object(provider, '_get_session', return_value=mock_session):
            collected = []
            async for part in provider.generate_stream("Say hi"):
                collected.append(part)

            print('collected=', collected)
            assert collected == ["Hello", "world"]

asyncio.run(run_test())
