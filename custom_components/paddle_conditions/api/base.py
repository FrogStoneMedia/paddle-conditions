"""Base API client with retry, backoff, and timeout."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

_LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 1
RETRY_BACKOFF_SECONDS = 2


class APIError(Exception):
    """Raised when an API call fails after retries."""


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

    async def _request(self, url: str, params: dict[str, Any] | None, response_method: str) -> Any:
        """Make a GET request with retry on 5xx, reading the body inside the timeout."""
        last_err: Exception | None = None
        for attempt in range(1 + self._retries):
            try:
                async with asyncio.timeout(self._timeout):
                    async with self._session.get(url, params=params) as resp:
                        resp.raise_for_status()
                        return await getattr(resp, response_method)()
            except TimeoutError as err:
                raise APIError(f"Timeout fetching {url}") from err
            except ClientResponseError as err:
                if err.status >= 500 and attempt < self._retries:
                    last_err = err
                    await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
                raise APIError(f"Error fetching {url}: {err}") from err
            except ClientError as err:
                raise APIError(f"Error fetching {url}: {err}") from err
        raise APIError(f"Error fetching {url}: {last_err}")

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request and return parsed JSON."""
        return await self._request(url, params, "json")

    async def _get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        """Make a GET request and return raw text."""
        result: str = await self._request(url, params, "text")
        return result
