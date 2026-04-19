"""
OpenCascade - Main orchestration engine for free GenAI model selection and routing.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, AsyncIterator

from pydantic import BaseModel

from ..classifier.task_types import TaskType
from ..providers.base import BaseProvider
from ..providers.registry import ProviderRegistry
from ..utils.config import Config
from ..utils.logging import setup_logger
from ..utils.exceptions import NoProvidersAvailableError
from ..utils.response_cache import ResponseCache
from .selector import ModelSelector
from .router import Router
from .combiner import Combiner
from .fallback import FallbackHandler


logger = setup_logger(__name__)


class ProcessConfig(BaseModel):
    """Configuration for processing requests."""
    task_type: Optional[TaskType] = None
    provider_preference: Optional[List[str]] = None
    timeout: float = 30.0
    max_retries: int = 3
    fallback_enabled: bool = True


class Orchestrator:
    """Main orchestration engine for OpenCascade."""
    
    def __init__(self, config_path: Optional[str] = None, classifier: Optional[Any] = None):
        """Initialize the orchestrator with configuration.
        
        Args:
            config_path: Optional path to configuration file
            classifier: Optional classifier instance to use for inferring task types.
                If not provided, a default TaskClassifier will be lazily constructed
                when classification is first needed.
        """
        self.config = Config(config_path) if config_path else Config()
        self.logger = logger
        
        # Initialize components
        self.registry = ProviderRegistry()
        self.selector: Optional[ModelSelector] = None
        self.router = Router()
        self.combiner = Combiner()
        self.fallback: Optional[FallbackHandler] = None
        # Allow injecting a custom classifier for testing or customization.
        # Lazily import the default TaskClassifier only when needed to avoid
        # importing classifier-related modules at package import time.
        self.classifier = classifier
        # Initialize response cache according to config
        cache_cfg = self.config.load().get("cache", {})
        try:
            if cache_cfg.get("enabled"):
                backend = cache_cfg.get("backend", "memory")
                ttl = cache_cfg.get("ttl", 3600)
                path = cache_cfg.get("path")
                self.response_cache = ResponseCache(ttl=ttl, backend=backend, path=path)
            else:
                self.response_cache = None
        except Exception:
            # Never fail orchestrator initialization due to cache issues
            self.response_cache = None
        
        logger.info("Orchestrator initialized")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        self.cleanup()
        return False
    
    def cleanup(self):
        """Cleanup resources (close provider sessions)."""
        # Close all provider sessions
        for provider in self.registry.get_all_available():
            if hasattr(provider, '_session') and provider._session:
                try:
                    asyncio.run(provider._session.close())
                except Exception as e:
                    logger.warning(f"Error closing provider session: {e}")
    
    def _initialize_selector(self):
        """Initialize model selector with available providers."""
        if self.selector is None:
            providers = self.registry.get_all_available()
            self.selector = ModelSelector(providers)
    
    def _initialize_fallback(self):
        """Initialize fallback handler if Ollama is available."""
        if self.fallback is None:
            ollama = self.registry.get("ollama")
            self.fallback = FallbackHandler(ollama)
    
    def process(
        self,
        query: str,
        task_type: Optional[TaskType] = None,
        **kwargs
    ) -> str:
        """Process a query using the most suitable model.
        
        Args:
            query: The input query to process
            task_type: Optional task type override
            **kwargs: Additional configuration options
        
        Returns:
            str: The processed response
        """
        return asyncio.run(self._process_async(query, task_type, **kwargs))

    def process_stream(self, query: str, task_type: Optional[TaskType] = None, **kwargs) -> AsyncIterator[str]:
        """Synchronous-facing wrapper that returns an async iterator for streaming.

        This is a convenience for higher-level CLI code that wants to consume
        streaming output from providers. It runs the async streaming pipeline
        in an event loop and yields chunks as they arrive.
        """
        # Lazily import to avoid circular imports at module load time
        import asyncio as _asyncio

        async def _gen():
            # Initialize selector/fallback like normal
            await self._process_async("", None)  # ensure selector/fallback inited
            # For streaming we delegate to the first selected provider's
            # generate_stream implementation. Keep behavior simple: pick the
            # single best provider via selector.select_single
            if task_type is None:
                try:
                    inferred_type, _ = self.classifier.classify(query)
                    _task_type = inferred_type
                except Exception:
                    _task_type = TaskType.CHAT
            else:
                _task_type = task_type

            self._initialize_selector()
            provider = self.selector.select_single(_task_type)
            if provider is None:
                raise NoProvidersAvailableError(task_type=str(_task_type), available_providers=[p.name for p in self.registry.get_all_available()])

            # Stream from provider
            async for chunk in provider.generate_stream(query, task_type=_task_type, **kwargs):
                yield chunk

        # Return an async iterator to the caller (they can run it in their loop)
        return _gen()
    
    async def _process_async(
        self,
        query: str,
        task_type: Optional[TaskType] = None,
        **kwargs
    ) -> str:
        """Internal async processing implementation.
        
        Args:
            query: Input query
            task_type: Optional task type
            **kwargs: Additional parameters
            
        Returns:
            Processed response
        """
        self._initialize_selector()
        self._initialize_fallback()

        # Attempt cache lookup if enabled. We use a simple key composed of
        # the query and task_type so different task types don't collide.
        cache_key = None
        if self.response_cache is not None:
            try:
                key_payload = {"q": query, "task": str(task_type)}
                cache_key = self.response_cache.make_key(key_payload)
                cached = await self.response_cache.get(cache_key)
                if cached is not None:
                    logger.info("Cache hit - returning cached response")
                    return cached
            except Exception:
                # Treat cache errors as misses
                cache_key = None
        
        # Use provided task type or infer using the TaskClassifier. Lazily
        # initialize the default TaskClassifier if none was injected.
        if task_type is None:
            try:
                if self.classifier is None:
                    # Import locally to avoid top-level dependency during import
                    from ..classifier.classifier import TaskClassifier

                    self.classifier = TaskClassifier()

                inferred_type, confidence = self.classifier.classify(query)
                logger.info(
                    f"No task type specified - classifier inferred {inferred_type} (confidence={confidence})"
                )
                task_type = inferred_type
            except Exception as e:
                # Fallback to CHAT if classifier fails for any reason
                logger.warning(f"Classifier failed to infer task type: {e}. Defaulting to CHAT")
                task_type = TaskType.CHAT
        
        try:
            # Check if failover is enabled (default: True)
            enable_failover = kwargs.get('enable_failover', True)
            
            if enable_failover:
                # Get primary + fallback providers
                providers = self.selector.select_with_fallbacks(
                    task_type,
                    max_fallbacks=kwargs.get('max_fallbacks', 2),
                    preferences=kwargs.get('provider_preference')
                )
                
                if not providers:
                    available = [p.name for p in self.registry.get_all_available()]
                    raise NoProvidersAvailableError(
                        task_type=str(task_type),
                        available_providers=available
                    )
                
                # Try providers with automatic failover
                response, provider_name = await self.router.route_with_failover(
                    providers, query, **kwargs
                )
                # Save response to cache (best-effort)
                if self.response_cache is not None and cache_key is not None:
                    try:
                        await self.response_cache.set(cache_key, response)
                    except Exception:
                        pass
                logger.info(f"Query processed successfully by {provider_name}")
                return response
            else:
                # Original single-provider logic
                provider = self.selector.select_single(task_type)
                
                if provider is None:
                    available = [p.name for p in self.registry.get_all_available()]
                    raise NoProvidersAvailableError(
                        task_type=str(task_type),
                        available_providers=available
                    )
                
                # Route query to provider
                response = await self.router.route_single(provider, query, **kwargs)

                # Save response to cache (best-effort)
                if self.response_cache is not None and cache_key is not None:
                    try:
                        await self.response_cache.set(cache_key, response)
                    except Exception:
                        pass

                return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            
            # Try fallback if enabled
            if kwargs.get('fallback_enabled', True) and self.fallback.has_fallback():
                logger.info("Attempting fallback")
                try:
                    return await self.fallback.fallback(query, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"Fallback failed: {fallback_error}")
            
            raise
    
    def process_multi(
        self,
        query: str,
        num_models: int = 2,
        combination_method: str = "merge",
        task_type: Optional[TaskType] = None,
        **kwargs
    ) -> str:
        """Process a query using multiple models and combine their responses.
        
        Args:
            query: The input query to process
            num_models: Number of models to use
            combination_method: Method to combine responses ("merge" or "summarize")
            task_type: Optional task type override
            **kwargs: Additional configuration options
        
        Returns:
            str: The combined response
        """
        return asyncio.run(
            self._process_multi_async(
                query,
                num_models,
                combination_method,
                task_type,
                **kwargs
            )
        )
    
    async def _process_multi_async(
        self,
        query: str,
        num_models: int,
        combination_method: str,
        task_type: Optional[TaskType] = None,
        **kwargs
    ) -> str:
        """Internal async multi-processing implementation.
        
        Args:
            query: Input query
            num_models: Number of models
            combination_method: Combination method
            task_type: Optional task type
            **kwargs: Additional parameters
            
        Returns:
            Combined response
        """
        self._initialize_selector()
        
        # Use provided task type or infer using the TaskClassifier. Lazily
        # initialize classifier if necessary.
        if task_type is None:
            try:
                if self.classifier is None:
                    from ..classifier.classifier import TaskClassifier

                    self.classifier = TaskClassifier()

                inferred_type, confidence = self.classifier.classify(query)
                logger.info(
                    f"No task type specified - classifier inferred {inferred_type} (confidence={confidence})"
                )
                task_type = inferred_type
            except Exception:
                task_type = TaskType.CHAT
        
        # Select a larger candidate pool: request up to num_models * 2 providers
        # so we have alternatives if some fail quickly. This keeps the call
        # site simple while letting the router return the first N successes.
        candidate_count = max(num_models * 2, num_models)
        providers = self.selector.select_multiple(task_type, candidate_count)
        
        if not providers:
            available = [p.name for p in self.registry.get_all_available()]
            raise NoProvidersAvailableError(
                task_type=str(task_type),
                available_providers=available
            )
        
        # Route to multiple providers and return the first `num_models` successful
        # responses. This prevents waiting for slower providers once we have
        # enough good answers.
        responses = await self.router.route_multiple(providers, query, return_first_n=num_models, **kwargs)
        
        if not responses:
            raise NoProvidersAvailableError(
                task_type=str(task_type),
                available_providers=[p.name for p in providers]
            )
        
        # Combine responses
        if combination_method == "summarize":
            return self.combiner.summarize(responses)
        else:
            return self.combiner.merge(responses)
