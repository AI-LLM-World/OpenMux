"""OpenAI-style exception types and mapping from OpenMux exceptions.

This module provides a small set of exceptions that mirror the OpenAI
Python client's error types and a helper to map OpenMux internal exceptions
into these types so the compatibility shim can raise familiar errors.
"""
from typing import Optional

class OpenAIError(Exception):
    """Base OpenAI-like error."""
    pass


class InvalidRequestError(OpenAIError):
    pass


class AuthenticationError(OpenAIError):
    pass


class RateLimitError(OpenAIError):
    pass


class OpenAIAPIError(OpenAIError):
    pass


class ServiceUnavailableError(OpenAIAPIError):
    pass


class Timeout(OpenAIError):
    pass


class NotFoundError(OpenAIError):
    pass


class PermissionError(OpenAIError):
    pass


def map_openmux_exception(exc: Exception) -> OpenAIError:
    """Map an OpenMux exception to an OpenAI-style exception instance.

    This is a best-effort mapping used by the compatibility shim.
    """
    # Import here to avoid top-level import cycles during tests
    try:
        from .utils.exceptions import (
            APIError as OpenMuxAPIError,
            ProviderUnavailableError,
            NoProvidersAvailableError,
            FailoverError,
            TimeoutError as OpenMuxTimeoutError,
            ModelNotFoundError,
            ProviderError,
            ConfigurationError,
        )
    except Exception:
        # If import fails (test scaffolding) fall back to a conservative mapping
        return OpenAIAPIError(str(exc))

    # Exact-type mappings
    if isinstance(exc, OpenMuxAPIError):
        code = getattr(exc, "status_code", None)
        if code == 401:
            return AuthenticationError(str(exc))
        if code == 429:
            return RateLimitError(str(exc))
        if code is not None and code >= 500:
            return ServiceUnavailableError(str(exc))
        return OpenAIAPIError(str(exc))

    if isinstance(exc, ProviderUnavailableError):
        return ServiceUnavailableError(str(exc))

    if isinstance(exc, NoProvidersAvailableError):
        return InvalidRequestError(str(exc))

    if isinstance(exc, FailoverError):
        return OpenAIAPIError(str(exc))

    if isinstance(exc, OpenMuxTimeoutError):
        return Timeout(str(exc))

    if isinstance(exc, ModelNotFoundError):
        return NotFoundError(str(exc))

    if isinstance(exc, ProviderError):
        return OpenAIAPIError(str(exc))

    if isinstance(exc, ConfigurationError):
        return PermissionError(str(exc))

    # Default fallback
    return OpenAIAPIError(str(exc))
