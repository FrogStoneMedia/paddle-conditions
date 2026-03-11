"""Tests for cloud sync client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.paddle_conditions.cloud_sync import CloudSyncClient

MAX_QUEUE_SIZE = 10


def _make_response(*, status=200, json_data=None):
    """Create a mock aiohttp response as a context manager."""
    resp = MagicMock()
    resp.status = status
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=json_data or {})

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


class TestCloudSyncEnabled:
    """Test enabled/disabled logic."""

    def test_enabled_when_url_and_token_set(self, mock_session):
        client = CloudSyncClient(mock_session, "https://sync.example.com", "my-token")
        assert client.enabled is True

    def test_disabled_when_no_url(self, mock_session):
        client = CloudSyncClient(mock_session, "", "my-token")
        assert client.enabled is False

    def test_disabled_when_no_token(self, mock_session):
        client = CloudSyncClient(mock_session, "https://sync.example.com", "")
        assert client.enabled is False

    def test_disabled_when_both_empty(self, mock_session):
        client = CloudSyncClient(mock_session, "", "")
        assert client.enabled is False


class TestCloudSyncPush:
    """Test push functionality."""

    async def test_push_sends_auth_header(self, mock_session):
        """Push sends Bearer token in Authorization header."""
        mock_session.post = MagicMock(return_value=_make_response())
        client = CloudSyncClient(mock_session, "https://sync.example.com", "secret-token")

        result = await client.push({"location": "test", "score": 85})

        assert result is True
        mock_session.post.assert_called_once()
        call_kwargs = mock_session.post.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer secret-token"

    async def test_push_sends_to_correct_url(self, mock_session):
        """Push sends to {base_url}/api/sync/push."""
        mock_session.post = MagicMock(return_value=_make_response())
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")

        await client.push({"location": "test"})

        call_args = mock_session.post.call_args
        assert call_args.args[0] == "https://sync.example.com/api/sync/push"

    async def test_push_sends_payload_as_json(self, mock_session):
        """Push wraps payload in items array."""
        mock_session.post = MagicMock(return_value=_make_response())
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")

        payload = {"location": "Lake Merritt", "score": 72}
        await client.push(payload)

        call_kwargs = mock_session.post.call_args
        assert call_kwargs.kwargs["json"] == {"items": [payload]}

    async def test_push_failure_does_not_raise(self, mock_session):
        """Push failures are non-fatal — never raise."""
        mock_session.post = MagicMock(side_effect=Exception("network error"))
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")

        result = await client.push({"location": "test"})

        assert result is False

    async def test_push_queues_on_failure(self, mock_session):
        """Failed push items are queued for retry."""
        mock_session.post = MagicMock(side_effect=Exception("timeout"))
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")

        await client.push({"location": "test", "attempt": 1})

        assert len(client._queue) == 1
        assert client._queue[0]["location"] == "test"

    async def test_push_flushes_queue_on_success(self, mock_session):
        """Successful push includes queued items and clears queue."""
        # First push fails — queues the item
        mock_session.post = MagicMock(side_effect=Exception("fail"))
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")
        await client.push({"location": "queued-item"})
        assert len(client._queue) == 1

        # Second push succeeds — should send queued + new item
        mock_session.post = MagicMock(return_value=_make_response())
        result = await client.push({"location": "new-item"})

        assert result is True
        assert len(client._queue) == 0
        call_kwargs = mock_session.post.call_args
        items = call_kwargs.kwargs["json"]["items"]
        assert len(items) == 2
        assert items[0]["location"] == "queued-item"
        assert items[1]["location"] == "new-item"

    async def test_push_queue_max_size(self, mock_session):
        """Queue is capped at MAX_QUEUE_SIZE items."""
        mock_session.post = MagicMock(side_effect=Exception("fail"))
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")

        for i in range(MAX_QUEUE_SIZE + 5):
            await client.push({"item": i})

        assert len(client._queue) == MAX_QUEUE_SIZE
        # Oldest items are dropped (deque maxlen behavior)
        assert client._queue[0]["item"] == 5

    async def test_push_disabled_is_noop(self, mock_session):
        """Disabled client returns False without making requests."""
        client = CloudSyncClient(mock_session, "", "")

        result = await client.push({"location": "test"})

        assert result is False
        mock_session.post.assert_not_called()

    async def test_push_strips_trailing_slash_from_url(self, mock_session):
        """Trailing slashes in base URL are stripped."""
        mock_session.post = MagicMock(return_value=_make_response())
        client = CloudSyncClient(mock_session, "https://sync.example.com/", "token")

        await client.push({"location": "test"})

        call_args = mock_session.post.call_args
        assert call_args.args[0] == "https://sync.example.com/api/sync/push"


class TestCloudSyncPull:
    """Test pull functionality."""

    async def test_pull_returns_data(self, mock_session):
        """Pull returns parsed JSON response."""
        pull_data = {
            "session_logs": [{"date": "2026-03-10", "location": "Lake Merritt"}],
            "preferences": {"activity": "sup"},
            "locations": [],
            "timestamp": "2026-03-10T12:00:00Z",
        }
        mock_session.get = MagicMock(return_value=_make_response(json_data=pull_data))
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")

        result = await client.pull()

        assert result == pull_data

    async def test_pull_sends_auth_header(self, mock_session):
        """Pull sends Bearer token in Authorization header."""
        mock_session.get = MagicMock(return_value=_make_response())
        client = CloudSyncClient(mock_session, "https://sync.example.com", "secret-token")

        await client.pull()

        call_kwargs = mock_session.get.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer secret-token"

    async def test_pull_uses_correct_url(self, mock_session):
        """Pull fetches from {base_url}/api/sync/pull."""
        mock_session.get = MagicMock(return_value=_make_response())
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")

        await client.pull()

        call_args = mock_session.get.call_args
        assert call_args.args[0] == "https://sync.example.com/api/sync/pull"

    async def test_pull_failure_returns_none(self, mock_session):
        """Pull failures return None — never raise."""
        mock_session.get = MagicMock(side_effect=Exception("network error"))
        client = CloudSyncClient(mock_session, "https://sync.example.com", "token")

        result = await client.pull()

        assert result is None

    async def test_pull_disabled_returns_none(self, mock_session):
        """Disabled client returns None without making requests."""
        client = CloudSyncClient(mock_session, "", "")

        result = await client.pull()

        assert result is None
        mock_session.get.assert_not_called()
