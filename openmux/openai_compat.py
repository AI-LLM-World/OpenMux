"""
OpenAI-compatible shim for OpenMux.

This module provides a minimal compatibility surface so code written
against the OpenAI Python client can call into OpenMux with minimal
changes. The goal is a small, pragmatic adapter that translates a
subset of the OpenAI API (chat completions and embeddings) into
Orchestrator calls.

This is intentionally small — it implements the synchronous, non-streaming
paths and returns OpenAI-like response shapes. Future work can expand
support for async calls, streaming, usage fields, and richer error mapping.
"""
from __future__ import annotations

import uuid
import time
import json
import ast
import re
from typing import Any, Dict, List, Optional, Sequence, Union

# Import heavy dependencies lazily inside functions to avoid pulling in
# provider implementations (which require aiohttp) on module import.


_KNOWN_PROVIDERS = ["openrouter", "huggingface", "ollama", "mistral", "together"]


def _detect_provider_from_model(model: Optional[str]) -> Optional[List[str]]:
    """Try to infer a provider preference from an OpenAI-style model string.

    This is a best-effort helper: if the model string contains a known
    provider name we return that as the preferred provider to Orchestrator.
    """
    if not model:
        return None
    ml = model.lower()
    found = [p for p in _KNOWN_PROVIDERS if p in ml]
    return found or None


def _messages_to_prompt(messages: Sequence[Dict[str, Any]]) -> str:
    """Convert OpenAI-style messages -> single prompt string for Orchestrator.

    We keep the conversion simple and human-readable. This is not a perfect
    semantic mapping but is sufficient to let chat-style conversations be
    forwarded to providers expecting a prompt string.
    """
    parts: List[str] = []
    for m in messages:
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if role == "system":
            parts.append(f"[SYSTEM] {content}")
        elif role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(content)
    return "\n".join(parts)


class ChatCompletion:
    """Minimal ChatCompletion compatibility.

    Usage:
        from openmux.openai_compat import ChatCompletion
        ChatCompletion.create(messages=[{"role":"user","content":"Hi"}])
    """

    @staticmethod
    def create(*, model: Optional[str] = None, messages: Optional[List[Dict[str, Any]]] = None,
               prompt: Optional[str] = None, temperature: Optional[float] = None,
               max_tokens: Optional[int] = None, n: int = 1, stream: bool = False, **kwargs) -> Union[Dict[str, Any], Sequence[Dict[str, Any]]]:
        if messages is not None:
            prompt_text = _messages_to_prompt(messages)
        elif prompt is not None:
            prompt_text = prompt
        else:
            raise ValueError("Either 'messages' or 'prompt' must be provided")

        provider_pref = _detect_provider_from_model(model)

        # Lazy import to avoid importing provider modules at import-time
        from .core.orchestrator import Orchestrator
        from .classifier.task_types import TaskType

        orch = Orchestrator()
        orch_kwargs: Dict[str, Any] = {}
        if provider_pref:
            orch_kwargs["provider_preference"] = provider_pref
        if temperature is not None:
            orch_kwargs["temperature"] = temperature
        if max_tokens is not None:
            orch_kwargs["max_tokens"] = max_tokens

        # Orchestrator.process is synchronous (it runs the async internals),
        # so this shim remains synchronous like the OpenAI client.
        result_text = orch.process(prompt_text, task_type=TaskType.CHAT, **orch_kwargs)

        # If streaming requested, return a simple synchronous generator that
        # yields a minimal stream-compatible sequence. Providers may offer
        # better streaming; this fallback yields the final text as one chunk
        # then a finish message to remain compatible with typical consumers.
        if stream:
            def _gen():
                # Chunk with delta
                yield {
                    "id": f"openmux-{uuid.uuid4().hex}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model or "",
                    "choices": [
                        {"index": 0, "delta": {"content": result_text}, "finish_reason": None}
                    ],
                }
                # Final chunk
                yield {
                    "id": None,
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }

            return _gen()

        return {
            "id": f"openmux-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model or "",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
        }

    @staticmethod
    async def acreate(*, model: Optional[str] = None, messages: Optional[List[Dict[str, Any]]] = None,
                       prompt: Optional[str] = None, temperature: Optional[float] = None,
                       max_tokens: Optional[int] = None, n: int = 1, stream: bool = False, **kwargs) -> Union[Dict[str, Any], Any]:
        """Asynchronous variant of create.

        This uses Orchestrator._process_async to avoid blocking the event loop.
        If stream=True an async generator is returned with the same minimal
        streaming shape as the synchronous create(stream=True) fallback.
        """
        if messages is not None:
            prompt_text = _messages_to_prompt(messages)
        elif prompt is not None:
            prompt_text = prompt
        else:
            raise ValueError("Either 'messages' or 'prompt' must be provided")

        provider_pref = _detect_provider_from_model(model)

        from .core.orchestrator import Orchestrator
        from .classifier.task_types import TaskType

        orch = Orchestrator()
        orch_kwargs: Dict[str, Any] = {}
        if provider_pref:
            orch_kwargs["provider_preference"] = provider_pref
        if temperature is not None:
            orch_kwargs["temperature"] = temperature
        if max_tokens is not None:
            orch_kwargs["max_tokens"] = max_tokens

        result_text = await orch._process_async(prompt_text, task_type=TaskType.CHAT, **orch_kwargs)

        if stream:
            async def _agen():
                yield {
                    "id": f"openmux-{uuid.uuid4().hex}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model or "",
                    "choices": [
                        {"index": 0, "delta": {"content": result_text}, "finish_reason": None}
                    ],
                }
                yield {
                    "id": None,
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }

            return _agen()

        return {
            "id": f"openmux-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model or "",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
        }


class Embeddings:
    """Minimal Embeddings compatibility.

    Returns a dict similar to OpenAI's Embeddings.create. This implementation
    accepts a single input (or a list - only the first element is processed
    in this minimal shim) and attempts to parse provider responses that are
    either JSON arrays or Python list literals.
    """

    @staticmethod
    def create(*, input: Union[str, Sequence[str]], model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        if isinstance(input, (list, tuple)):
            if len(input) == 0:
                raise ValueError("input list must not be empty")
            query = input[0]
        else:
            query = input

        provider_pref = _detect_provider_from_model(model)
        # Lazy imports to avoid requiring aiohttp for simple imports/tests
        from .core.orchestrator import Orchestrator
        from .classifier.task_types import TaskType

        orch = Orchestrator()
        orch_kwargs: Dict[str, Any] = {}
        if provider_pref:
            orch_kwargs["provider_preference"] = provider_pref

        raw = orch.process(query, task_type=TaskType.EMBEDDINGS, **orch_kwargs)

        emb = None
        # Try JSON first
        try:
            emb = json.loads(raw)
        except Exception:
            try:
                emb = ast.literal_eval(raw)
            except Exception:
                # Try extracting floating point numbers as a last resort
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(raw))
                if nums:
                    emb = [float(x) for x in nums]

        if not isinstance(emb, list) or not all(isinstance(x, (int, float)) for x in emb):
            raise ValueError("Failed to parse embedding vector from provider response")

        embedding = [float(x) for x in emb]

        return {
            "object": "list",
            "data": [{"object": "embedding", "embedding": embedding, "index": 0}],
            "model": model or "",
            "usage": {},
        }


__all__ = ["ChatCompletion", "Embeddings"]
