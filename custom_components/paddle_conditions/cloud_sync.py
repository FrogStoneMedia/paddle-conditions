"""Cloud sync client for bidirectional HA <-> PWA data exchange."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from aiohttp import ClientSession, ClientTimeout

LOGGER = logging.getLogger(__name__)
MAX_QUEUE_SIZE = 10
SYNC_TIMEOUT = ClientTimeout(total=10)


class CloudSyncClient:
    """Push conditions to and pull session data from a Cloudflare Worker."""

    def __init__(self, session: ClientSession, base_url: str, token: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._token = token
        self._queue: deque[dict[str, Any]] = deque(maxlen=MAX_QUEUE_SIZE)

    @property
    def enabled(self) -> bool:
        """Return True if sync is configured with both URL and token."""
        return bool(self._base_url and self._token)

    async def push(self, payload: dict[str, Any]) -> bool:
        """Push data to cloud. Returns True on success. Never raises."""
        if not self.enabled:
            return False

        # Flush queue first, then send current payload
        items_to_send = [*self._queue, payload]
        self._queue.clear()

        try:
            async with self._session.post(
                f"{self._base_url}/api/sync/push",
                json={"items": items_to_send},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=SYNC_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                return True
        except Exception:
            LOGGER.warning("Cloud sync push failed, queuing %d items", len(items_to_send), exc_info=True)
            for item in items_to_send:
                self._queue.append(item)
            return False

    async def pull(self) -> dict[str, Any] | None:
        """Pull data from cloud. Returns None on failure. Never raises."""
        if not self.enabled:
            return None

        try:
            async with self._session.get(
                f"{self._base_url}/api/sync/pull",
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=SYNC_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                result: dict[str, Any] = await resp.json()
                return result
        except Exception:
            LOGGER.warning("Cloud sync pull failed", exc_info=True)
            return None
