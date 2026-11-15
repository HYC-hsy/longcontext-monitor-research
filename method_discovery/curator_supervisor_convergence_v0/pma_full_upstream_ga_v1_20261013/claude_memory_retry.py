"""One bounded retry owner for profiled Claude memory calls, not whole wakes."""
from __future__ import annotations

import asyncio
from email.utils import parsedate_to_datetime
import math
import time

import httpx
import aiohttp
from litellm.exceptions import APIConnectionError, Timeout, InternalServerError

# Adapted from GenericAgent-main/llmcore.py:_retryable_http_error. Ordinary
# request errors are excluded; no error message, credential or URL is logged.
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504,
                    520, 521, 522, 523, 524, 525, 526, 527, 529}


def status_code(error):
    value = getattr(error, 'status_code', None)
    if value is None:
        value = getattr(getattr(error, 'response', None), 'status_code', None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def is_transient(error):
    # Explicit exclusions also cover vendor exception types without importing
    # a second copy of Harbor in this host-side transport helper.
    names = {cls.__name__ for cls in type(error).__mro__}
    if names & {'ContextLengthExceededError', 'OutputLengthExceededError',
                'ContextWindowExceededError', 'AuthenticationError',
                'PermissionDeniedError', 'BadRequestError', 'UnprocessableEntityError'}:
        return False
    if isinstance(error, (httpx.LocalProtocolError, httpx.UnsupportedProtocol, aiohttp.ClientSSLError)):
        return False
    code = status_code(error)
    if code is not None:
        return code in RETRYABLE_STATUS
    return isinstance(error, (APIConnectionError, Timeout, InternalServerError,
                              aiohttp.ClientConnectionError, aiohttp.ServerTimeoutError, httpx.TransportError,
                              ConnectionError, TimeoutError))


def retry_delay(error, retry_index):
    """GA-like 1.5s exponential backoff, bounded to 30s including Retry-After."""
    headers = getattr(getattr(error, 'response', None), 'headers', None)
    if headers is None:
        headers = getattr(error, 'headers', None)
    value = headers.get('retry-after') if headers else None
    delay = None
    if value is not None:
        try:
            delay = float(value)
        except (TypeError, ValueError):
            try:
                delay = parsedate_to_datetime(str(value)).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                pass
    if delay is None or not math.isfinite(delay):
        delay = 1.5 * (2 ** min(retry_index, 5))
    return max(0.5, min(30.0, delay))


async def call_with_retries(call, *, max_retries, observer=None, **kwargs):
    """Each attempt invokes one unwrapped Harbor call, before any tool execution.

    Requested inner retry controls are zero. A Harbor compatibility fallback or
    provider implementation can still issue extra HTTP requests; never label
    these attempt records as an independently observed HTTP count.
    """
    if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
        raise ValueError('max_retries must be a nonnegative integer (additional attempts)')
    def emit(row):
        if observer is not None:
            observer({'layer': 'pma_claude_call', 'max_retries': max_retries,
                      'inner_retries_requested': 0, 'underlying_http_attempts': 'unknown', **row})
    for index in range(max_retries + 1):
        started = time.time()
        clock = time.monotonic()
        emit({'event': 'attempt_started', 'attempt': index + 1, 'started_epoch': started})
        try:
            result = await call(**kwargs, max_retries=0, num_retries=0)
        except BaseException as error:
            retry = isinstance(error, Exception) and is_transient(error) and index < max_retries
            delay = retry_delay(error, index) if retry else 0.0
            emit({'event': 'attempt_finished', 'attempt': index + 1,
                  'started_epoch': started, 'ended_epoch': time.time(),
                  'duration_seconds': time.monotonic() - clock,
                  'exception_type': type(error).__name__, 'exception_status_code': status_code(error), 'observed_http_status': 'unknown',
                  'retry_delay_seconds': delay,
                  'outcome': 'retry' if retry else 'cancelled' if isinstance(error, asyncio.CancelledError) else 'failed'})
            if not retry:
                raise
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                emit({'event': 'retry_wait_cancelled', 'attempt': index + 1,
                      'ended_epoch': time.time(), 'outcome': 'cancelled'})
                raise
        else:
            emit({'event': 'attempt_finished', 'attempt': index + 1,
                  'started_epoch': started, 'ended_epoch': time.time(),
                  'duration_seconds': time.monotonic() - clock,
                  'exception_type': None, 'exception_status_code': None, 'observed_http_status': 'unknown',
                  'retry_delay_seconds': 0.0, 'outcome': 'success'})
            return result
