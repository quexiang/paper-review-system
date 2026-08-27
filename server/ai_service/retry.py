"""LLM 调用重试机制 — 指数退避"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0  # seconds
DEFAULT_MAX_DELAY = 30.0


async def retry_with_backoff(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    **kwargs: Any,
) -> Any:
    """带指数退避的重试装饰器式调用

    Args:
        fn: Async callable to retry
        max_retries: Maximum retry attempts (not counting the initial call)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        retryable_exceptions: Tuple of exception types to retry on.
                              None means retry on any Exception.
        *args, **kwargs: Arguments passed to fn
    """
    if retryable_exceptions is None:
        retryable_exceptions = (Exception,)

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable_exceptions as e:
            last_error = e
            if attempt >= max_retries:
                logger.error("[Retry] Exhausted %d retries for %s: %s", max_retries, fn.__name__, e)
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "[Retry] %s attempt %d/%d failed (%s), retrying in %.1fs",
                fn.__name__, attempt + 1, max_retries, e, delay,
            )
            await asyncio.sleep(delay)
    raise last_error  # type: ignore[return-value]
