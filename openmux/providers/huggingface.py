"""
HuggingFace Inference API provider implementation.
"""

import os
from typing import Optional, Dict, Any, List
import aiohttp

from .base import BaseProvider
from ..classifier.task_types import TaskType
from ..utils.logging import setup_logger
from ..utils.exceptions import APIError


logger = setup_logger(__name__)


class HuggingFaceProvider(BaseProvider):
    """Provider for HuggingFace Inference API."""
    
    def __init__(
        self,
        api_token: Optional[str] = None,
        model_id: Optional[str] = None
    ):
        """Initialize HuggingFace provider.
        
        Args:
            api_token: HuggingFace API token (or use HF_TOKEN env var)
            model_id: Default model ID to use
        """
        super().__init__(name="HuggingFace")
        
        self.api_token = api_token or os.getenv("HF_TOKEN")
        self.base_url = "https://api-inference.huggingface.co/models/"
        
        # Default models for different task types
        self.default_models = {
            TaskType.CHAT: "meta-llama/Llama-2-7b-chat-hf",
            TaskType.CODE: "bigcode/starcoder",
            TaskType.EMBEDDINGS: "sentence-transformers/all-MiniLM-L6-v2"
        }
        
        self.model_id = model_id
        self._session: Optional[aiohttp.ClientSession] = None
    
    def is_available(self) -> bool:
        """Check if HuggingFace API is available.
        
        Returns:
            True if API token is configured
        """
        return self.api_token is not None
    
    def supports_task(self, task_type: TaskType) -> bool:
        """Check if provider supports the task type.
        
        Args:
            task_type: Task type to check
            
        Returns:
            True if supported
        """
        return task_type in self.default_models
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session.
        
        Returns:
            Client session
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json"
                }
            )
        return self._session
    
    async def generate(
        self,
        query: str,
        task_type: Optional[TaskType] = None,
        **kwargs
    ) -> str:
        """Generate response using HuggingFace Inference API.
        
        Args:
            query: Input query
            task_type: Task type (uses default model if not specified)
            **kwargs: Additional parameters
            
        Returns:
            Generated response
        """
        if not self.is_available():
            raise Exception("HuggingFace provider not available: API token not configured")
        
        # Select model
        if task_type and task_type in self.default_models:
            model = self.default_models[task_type]
        elif self.model_id:
            model = self.model_id
        else:
            model = self.default_models[TaskType.CHAT]
        
        logger.info(f"Using HuggingFace model: {model}")
        
        # Build request
        url = f"{self.base_url}{model}"
        
        # Prepare payload based on task type
        if task_type == TaskType.EMBEDDINGS:
            payload = {
                "inputs": query
            }
        else:
            payload = {
                "inputs": query,
                "parameters": {
                    "max_new_tokens": kwargs.get("max_tokens", 512),
                    "temperature": kwargs.get("temperature", 0.7),
                    "top_p": kwargs.get("top_p", 0.9)
                }
            }
        
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as response:
                # Handle non-200 responses explicitly so we can provide
                # better guidance (including Retry-After when present).
                if response.status != 200:
                    # Try to include helpful information from the response
                    try:
                        text = await response.text()
                    except Exception:
                        text = None

                    # Parse Retry-After header into an integer number of seconds
                    parsed_retry_after = None
                    retry_after_hdr = None
                    try:
                        retry_after_hdr = response.headers.get("Retry-After") if response.headers else None
                    except Exception:
                        retry_after_hdr = None

                    if retry_after_hdr:
                        # Try integer seconds first
                        try:
                            parsed_retry_after = int(retry_after_hdr)
                        except Exception:
                            # Try to parse HTTP-date format
                            try:
                                from email.utils import parsedate_to_datetime
                                import datetime as _dt

                                dt = parsedate_to_datetime(retry_after_hdr)
                                now = _dt.datetime.now(dt.tzinfo) if dt.tzinfo else _dt.datetime.utcnow()
                                parsed_retry_after = max(0, int((dt - now).total_seconds()))
                            except Exception:
                                parsed_retry_after = None

                    raise APIError("HuggingFace", status_code=response.status, response_text=text, parsed_retry_after=parsed_retry_after)

                result = await response.json()

                # Parse response based on task type
                if task_type == TaskType.EMBEDDINGS:
                    # Return embeddings as string representation
                    return str(result)
                elif isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], dict) and "generated_text" in result[0]:
                        return result[0]["generated_text"]
                    return str(result[0])

                return str(result)

        except APIError:
            # APIError already contains structured information - re-raise
            logger.error("HuggingFace API returned an error response")
            raise
        except aiohttp.ClientError as e:
            logger.error(f"HuggingFace client error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating with HuggingFace: {e}")
            raise
    
    async def close(self):
        """Close the provider session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
