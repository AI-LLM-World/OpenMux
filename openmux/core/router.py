"""Query router for sending requests to providers."""

import asyncio
import logging
from typing import List, Optional, Tuple

from ..providers.base import BaseProvider
from ..utils.exceptions import ProviderError, FailoverError, TimeoutError as OpenMuxTimeoutError, APIError
from ..utils.metrics import metrics


logger = logging.getLogger(__name__)


class Router:
    """Routes queries to providers with retry and timeout handling."""
    
    def __init__(self, timeout: float = 30.0, max_retries: int = 3):
        """Initialize the router.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        logger.info(f"Router initialized (timeout={timeout}s, retries={max_retries})")
    
    async def route_single(
        self,
        provider: BaseProvider,
        query: str,
        **kwargs
    ) -> str:
        """Route a query to a single provider.
        
        Args:
            provider: Provider to use
            query: Query string
            **kwargs: Additional parameters for the provider
            
        Returns:
            Response from the provider
            
        Raises:
            Exception: If all retry attempts fail
        """
        logger.debug(f"Routing query to {provider.name}")
        
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    provider.generate(query, **kwargs),
                    timeout=self.timeout
                )
                logger.info(f"Successfully received response from {provider.name}")
                return response
                
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{self.max_retries} "
                    f"for provider {provider.name}"
                )
                if attempt == self.max_retries - 1:
                    raise OpenMuxTimeoutError(
                        f"Request to {provider.name}",
                        self.timeout
                    )
                    
            except Exception as e:
                # Capture the exception in a persistent variable because the
                # exception variable is cleared at the end of the except block
                # in Python 3 to avoid reference cycles.
                last_exception = e

                logger.error(
                    f"Error on attempt {attempt + 1}/{self.max_retries} "
                    f"for provider {provider.name}: {e}"
                )
                # Debug: surface parsed_retry_after if present
                try:
                    parsed_debug = getattr(last_exception, 'parsed_retry_after', None)
                    logger.error(f"Exception parsed_retry_after attribute: {parsed_debug}")
                except Exception:
                    pass
                if attempt == self.max_retries - 1:
                    if isinstance(last_exception, ProviderError):
                        raise
                    raise ProviderError(provider.name, str(last_exception))
                    
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                # Default exponential backoff
                default_wait = 2 ** attempt

                # If we received a rate-limit APIError (429), try to respect any
                # provider-provided Retry-After hint encoded in the APIError.
                wait_time = default_wait
                try:
                    # Prefer an explicitly parsed retry-after value if present on the exception
                    parsed_val = getattr(last_exception, 'parsed_retry_after', None)
                    # Debug log the values we will use for the decision
                    logger.error(f"Backoff decision: default_wait={default_wait}, parsed_val={parsed_val}")
                    if parsed_val is not None:
                        parsed = int(parsed_val)
                        wait_time = max(default_wait, parsed)
                        logger.error(f"Using parsed_retry_after={parsed}s from exception; wait_time={wait_time}s")
                    else:
                        # Fall back to checking status_code + response_text for a Retry-After fragment
                        if getattr(last_exception, 'status_code', None) == 429 and getattr(last_exception, 'response_text', None):
                            text = str(last_exception.response_text)
                            marker = "Retry-After:"
                            if marker in text:
                                try:
                                    token = text.split(marker, 1)[1].strip().split()[0]
                                    parsed = int(token)
                                    wait_time = max(default_wait, parsed)
                                    logger.debug(f"Parsed Retry-After={parsed}s from exception.response_text; using wait_time={wait_time}s")
                                except Exception:
                                    logger.debug("Failed to parse Retry-After value from exception.response_text; using default backoff")
                except Exception:
                    # Be conservative: fall back to default backoff
                    wait_time = default_wait

                logger.error(f"Waiting {wait_time}s before retry")
                await asyncio.sleep(wait_time)
        
        # Should never reach here, but just in case
        raise ProviderError(provider.name, "All retry attempts exhausted")
    
    async def route_multiple(
        self,
        providers: List[BaseProvider],
        query: str,
        return_first_n: Optional[int] = None,
        **kwargs
    ) -> List[str]:
        """Route a query to multiple providers in parallel.
        
        Args:
            providers: List of providers to use
            query: Query string
            **kwargs: Additional parameters for providers
            
        Returns:
            List of responses from providers
        """
        logger.debug(f"Routing query to {len(providers)} providers")
        
        # Create a task for each provider so they all run in parallel
        tasks = [asyncio.create_task(self.route_single(provider, query, **kwargs)) for provider in providers]

        # If caller wants all responses, behave like before
        if return_first_n is None:
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and log them
            valid_responses = []
            for provider, response in zip(providers, responses):
                if isinstance(response, Exception):
                    logger.error(f"Error from {provider.name}: {response}")
                else:
                    valid_responses.append(response)

            logger.info(
                f"Received {len(valid_responses)}/{len(providers)} valid responses"
            )

            return valid_responses

        # Otherwise, return the first N successful responses and cancel the rest
        success_responses: List[str] = []
        pending = set(tasks)

        try:
            while pending and len(success_responses) < return_first_n:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

                for finished in done:
                    try:
                        result = finished.result()
                        # If provider returned an async-stream marker (tuple), handle
                        # it here. We treat streaming providers as having already
                        # produced the final string by route_single, so nothing to do
                        # special in the router. (Providers implement streaming at
                        # the CLI layer by calling generate_stream directly.)
                    except asyncio.CancelledError:
                        logger.debug("A pending provider task was cancelled")
                        continue
                    except Exception as e:
                        # Find provider name for better logging (best-effort)
                        idx = tasks.index(finished) if finished in tasks else None
                        pname = providers[idx].name if idx is not None else "unknown"
                        logger.error(f"Error from {pname}: {e}")
                        continue

                    # Successful response
                    success_responses.append(result)

            # Record metrics: how many successful responses we are returning
            try:
                metrics.incr(f"multi.responses.returned", len(success_responses))
            except Exception:
                pass

            # Cancel any remaining tasks since we have enough responses (or ran out)
            for t in pending:
                t.cancel()
                try:
                    metrics.incr("multi.tasks.cancelled")
                except Exception:
                    pass

            # Ensure cancellations are awaited to suppress warnings
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            logger.info(
                f"Returning {len(success_responses)}/{len(providers)} successful responses (requested {return_first_n})"
            )

            return success_responses

        finally:
            # As a safety net, ensure no leftover tasks remain running
            for t in tasks:
                if not t.done():
                    t.cancel()
            # Await to silence any warnings
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def route_with_failover(
        self,
        providers: List[BaseProvider],
        query: str,
        **kwargs
    ) -> Tuple[str, str]:
        """Route query to providers with automatic failover.
        
        Tries providers in sequence until one succeeds. Uses exponential
        backoff between provider switches.
        
        Args:
            providers: List of providers to try (in order)
            query: Query string
            **kwargs: Additional parameters for providers
            
        Returns:
            Tuple of (response, provider_name) on success
            
        Raises:
            Exception: If all providers fail
        """
        logger.info(f"Attempting failover across {len(providers)} providers")
        
        last_error = None
        
        for idx, provider in enumerate(providers):
            try:
                logger.info(f"Trying provider {idx + 1}/{len(providers)}: {provider.name}")
                
                # Try this provider with retries
                response = await self.route_single(provider, query, **kwargs)
                
                logger.info(f"✓ Success with provider: {provider.name}")
                return response, provider.name
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"✗ Provider {provider.name} failed: {str(e)[:100]}"
                )
                
                # Wait before trying next provider (exponential backoff)
                if idx < len(providers) - 1:
                    wait_time = 2 ** idx
                    logger.debug(f"Waiting {wait_time}s before trying next provider")
                    await asyncio.sleep(wait_time)
        
        # All providers failed
        provider_names = [p.name for p in providers]
        logger.error(f"All {len(providers)} providers failed")
        raise FailoverError(provider_names, last_error)
