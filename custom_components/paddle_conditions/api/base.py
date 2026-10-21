"""Base API client with retry, backoff, and timeout."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 1
RETRY_BACKOFF_SECONDS = 2


class APIError(Exception):
    """Raised when an API call fails after retries."""


class RateLimitedError(APIError):
    """Raised on HTTP 429. ``retry_after`` is in seconds when the server says."""

    def __init__(self, message: str, retry_after: float | None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def _retry_after(headers: Mapping[str, str] | None) -> float | None:
    """Parse a numeric Retry-After header; HTTP-date values are ignored."""
    raw = (headers or {}).get("Retry-After")
    try:
        seconds = float(raw) if raw is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and seconds >= 0 else None


class BaseAPIClient:
    """Base class for all API clients."""

    def __init__(
        self,
        session: ClientSession,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self._session = session
        self._timeout = timeout
        self._retries = retries

    async def _request(
        self,
        url: str,
        params: dict[str, Any] | None,
        response_method: str,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make a GET request with retry on 5xx, reading the body inside the timeout."""
        attempt = 0
        while True:
            try:
                async with asyncio.timeout(self._timeout):
                    async with self._session.get(url, params=params, headers=headers) as resp:
                        resp.raise_for_status()
                        return await getattr(resp, response_method)()
            except TimeoutError as err:
                raise APIError(f"Timeout fetching {url}") from err
            except ClientResponseError as err:
                if err.status == 429:
                    raise RateLimitedError(f"Rate limited by {url}", _retry_after(err.headers)) from err
                if err.status >= 500 and attempt < self._retries:
                    attempt += 1
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                raise APIError(f"Error fetching {url}: {err}") from err
            except ClientError as err:
                raise APIError(f"Error fetching {url}: {err}") from err

    async def _get_json(
        self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> Any:
        """Make a GET request and return parsed JSON."""
        return await self._request(url, params, "json", headers)

    async def _get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        """Make a GET request and return raw text."""
        result: str = await self._request(url, params, "text")
        return result
