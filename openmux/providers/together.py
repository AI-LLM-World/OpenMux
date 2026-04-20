"""
Together AI provider implementation.
"""

import os
from typing import Optional, Dict, Any
import aiohttp

from .base import BaseProvider
from ..classifier.task_types import TaskType
from ..utils.exceptions import ConfigurationError, APIError


class TogetherProvider(BaseProvider):
    """Provider for Together AI hosted models.
    
    This provider provides a similar interface to other providers in the
    project and tries to be tolerant of differing response shapes.
    """

    def __init__(self, api_key: Optional[str] = None, model_id: Optional[str] = None):
        super().__init__(name="Together")

        # Expected environment variable: TOGETHER_API_KEY
        self.api_key = api_key or os.getenv("TOGETHER_API_KEY")
        self.base_url = "https://api.together.ai/v1/models/"

        # Default models
        self.default_models = {
            TaskType.CHAT: "togethercomputer/RedPajama-INCITE-3B-v1",
            TaskType.CODE: "togethercomputer/RedPajama-INCITE-3B-v1",
        }

        self.model_id = model_id
        self._session: Optional[aiohttp.ClientSession] = None

    def is_available(self) -> bool:
        return self.api_key is not None

    def supports_task(self, task_type: TaskType) -> bool:
        return task_type in self.default_models

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else None,
            }
            # Remove None values (aiohttp does not like None header values)
            headers = {k: v for k, v in headers.items() if v is not None}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def generate(self, query: str, task_type: Optional[TaskType] = None, **kwargs) -> str:
        if not self.is_available():
            raise ConfigurationError("Together API key not configured")

        if task_type and task_type in self.default_models:
            model = self.default_models[task_type]
        elif self.model_id:
            model = self.model_id
        else:
            model = self.default_models[TaskType.CHAT]

        url = f"{self.base_url}{model}/generate"

        payload: Dict[str, Any] = {
            "inputs": query,
            "parameters": {
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 512),
            }
        }

        session = await self._get_session()
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                text = None
                try:
                    text = await response.text()
                except Exception:
                    pass
                raise APIError("Together", status_code=response.status, response_text=text)

            result = await response.json()

            # Attempt to parse common response shapes
            if isinstance(result, dict):
                if "generated_text" in result:
                    return result["generated_text"]
                outputs = result.get("outputs")
                if outputs and isinstance(outputs, list) and len(outputs) > 0:
                    first = outputs[0]
                    if isinstance(first, dict) and "content" in first:
                        return first["content"]
                    return str(first)

            if isinstance(result, list) and len(result) > 0:
                first = result[0]
                if isinstance(first, dict) and "generated_text" in first:
                    return first["generated_text"]
                return str(first)

            return str(result)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
