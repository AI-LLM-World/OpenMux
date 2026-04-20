"""
Provider registry for managing available GenAI providers.
"""

import logging
from typing import Dict, List, Optional, Any

from .base import BaseProvider
from ..utils.logging import setup_logger

# Entry point discovery - importlib.metadata on stdlib or backport
try:
    import importlib.metadata as _importlib_metadata  # type: ignore
except Exception:  # pragma: no cover - backport import on very old Pythons
    try:
        import importlib_metadata as _importlib_metadata  # type: ignore
    except Exception:
        _importlib_metadata = None  # type: ignore


logger = setup_logger(__name__)


class ProviderRegistry:
    """Registry for managing and accessing GenAI providers."""
    
    def __init__(self):
        """Initialize the provider registry."""
        self._providers: Dict[str, BaseProvider] = {}
        # Initialize providers: discover plugins via entry points first,
        # then fall back to built-in providers.
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available providers."""
        # 1) Discover providers exposed via Python entry points. This allows
        # external packages to register providers under the "openmux.providers"
        # group without modifying this codebase.
        try:
            self._discover_entry_point_providers()
        except Exception as e:
            # Don't fail initialization if plugin discovery fails - log and
            # continue to register built-in providers.
            logger.warning(f"Provider entry point discovery failed: {e}")
        # Built-in providers (only register if a plugin hasn't already provided
        # the same provider name). These remain as a fallback for users who
        # install OpenMux without external provider plugins.
        # OpenRouter
        try:
            if "openrouter" not in self._providers:
                # Import provider here to avoid importing optional deps at module import time
                from .openrouter import OpenRouterProvider

                openrouter = OpenRouterProvider()
                if openrouter.is_available():
                    self._providers["openrouter"] = openrouter
                    logger.info("OpenRouter provider registered")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenRouter: {e}")
        
        # HuggingFace
        try:
            if "huggingface" not in self._providers:
                from .huggingface import HuggingFaceProvider

                huggingface = HuggingFaceProvider()
                if huggingface.is_available():
                    self._providers["huggingface"] = huggingface
                    logger.info("HuggingFace provider registered")
        except Exception as e:
            logger.warning(f"Failed to initialize HuggingFace: {e}")
        
        # Ollama
        try:
            if "ollama" not in self._providers:
                from .ollama import OllamaProvider

                ollama = OllamaProvider()
                if ollama.is_available():
                    self._providers["ollama"] = ollama
                    logger.info("Ollama provider registered")
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama: {e}")
        
        # Mistral
        try:
            if "mistral" not in self._providers:
                from .mistral import MistralProvider

                mistral = MistralProvider()
                if mistral.is_available():
                    self._providers["mistral"] = mistral
                    logger.info("Mistral provider registered")
        except Exception as e:
            logger.warning(f"Failed to initialize Mistral: {e}")

        # Together AI
        try:
            if "together" not in self._providers:
                from .together import TogetherProvider

                together = TogetherProvider()
                if together.is_available():
                    self._providers["together"] = together
                    logger.info("Together provider registered")
        except Exception as e:
            logger.warning(f"Failed to initialize Together: {e}")

    def register(self, provider: BaseProvider) -> None:
        """Register a provider instance programmatically.

        This allows callers (or tests) to add providers at runtime.
        If a provider with the same lower-cased name already exists it will be
        overwritten by the new instance.
        """
        if not provider or not isinstance(provider, BaseProvider):
            raise TypeError("provider must be an instance of BaseProvider")

        key = provider.name.lower()
        self._providers[key] = provider
        logger.info(f"Provider registered programmatically: {provider.name}")

    def _discover_entry_point_providers(self) -> None:
        """Discover providers via Python entry points.

        Entry points should be registered under the group 'openmux.providers'.
        Each entry point can expose either:
        - a BaseProvider subclass (will be instantiated with no args),
        - a callable that returns a BaseProvider instance, or
        - an already-instantiated BaseProvider object.
        """
        if _importlib_metadata is None:
            logger.debug("importlib.metadata not available; skipping entry point discovery")
            return

        try:
            eps = _importlib_metadata.entry_points()
            # support both new and old APIs
            if hasattr(eps, "select"):
                entries = eps.select(group="openmux.providers")
            else:
                entries = eps.get("openmux.providers", [])
        except Exception as e:
            logger.warning(f"Error fetching entry points: {e}")
            return

        for ep in entries:
            try:
                obj = ep.load()
                provider: Optional[BaseProvider] = None

                # If it's already an instance
                if isinstance(obj, BaseProvider):
                    provider = obj

                # If it's a class (subclass of BaseProvider), try instantiate
                elif isinstance(obj, type) and issubclass(obj, BaseProvider):
                    try:
                        provider = obj()
                    except Exception as e:
                        logger.warning(f"Failed to instantiate provider class from entry point {ep.name}: {e}")
                        provider = None

                # If it's a callable factory, call it and expect a provider
                elif callable(obj):
                    try:
                        inst = obj()
                        if isinstance(inst, BaseProvider):
                            provider = inst
                        else:
                            logger.warning(f"Entry point {ep.name} callable did not return a BaseProvider instance")
                    except TypeError:
                        # No-arg call failed; skip
                        logger.warning(f"Entry point {ep.name} callable could not be called without args")
                    except Exception as e:
                        logger.warning(f"Error calling entry point {ep.name}: {e}")

                if provider:
                    name_key = provider.name.lower()
                    # Plugins should be allowed to override built-ins; replace any
                    # existing registration for the same name.
                    self._providers[name_key] = provider
                    logger.info(f"Registered provider from entry point: {provider.name}")

            except Exception as e:
                logger.warning(f"Failed to load provider entry point {getattr(ep, 'name', repr(ep))}: {e}")
    
    def get(self, name: str) -> Optional[BaseProvider]:
        """Get a provider by name.
        
        Args:
            name: Provider name (e.g., "openrouter", "huggingface", "ollama")
            
        Returns:
            Provider instance or None if not found
        """
        return self._providers.get(name.lower())
    
    def get_all(self) -> Dict[str, BaseProvider]:
        """Get all registered providers.
        
        Returns:
            Dictionary of provider name -> provider instance
        """
        return self._providers.copy()
    
    def get_all_available(self) -> List[BaseProvider]:
        """Get all available providers as a list.
        
        Returns:
            List of provider instances
        """
        return list(self._providers.values())
    
    def is_available(self, name: str) -> bool:
        """Check if a provider is available.
        
        Args:
            name: Provider name
            
        Returns:
            True if provider is registered and available
        """
        provider = self.get(name)
        return provider is not None and provider.is_available()
