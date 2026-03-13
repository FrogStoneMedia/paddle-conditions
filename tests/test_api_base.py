"""Tests for the base API client."""

from unittest.mock import MagicMock

import pytest

from custom_components.paddle_conditions.api.base import APIError, BaseAPIClient

from .conftest import MockAsyncContextManager, mock_get_error, mock_get_json, mock_get_text


async def test_get_json_success(mock_session):
    mock_session.get = mock_get_json({"key": "value"})

    client = BaseAPIClient(mock_session)
    result = await client._get_json("https://example.com/api")
    assert result == {"key": "value"}


async def test_get_json_timeout(mock_session):
    mock_session.get = MagicMock(return_value=MockAsyncContextManager(side_effect=TimeoutError()))

    client = BaseAPIClient(mock_session, timeout=1)
    with pytest.raises(APIError, match="Timeout"):
        await client._get_json("https://example.com/api")


async def test_get_json_http_error(mock_session):
    mock_session.get = mock_get_error(500, "Server Error")

    client = BaseAPIClient(mock_session)
    with pytest.raises(APIError, match="Error fetching"):
        await client._get_json("https://example.com/api")


async def test_get_json_retries_on_transient_error(mock_session):
    """Should retry once on 500-level errors before raising."""
    from unittest.mock import AsyncMock

    from aiohttp import ClientResponseError

    fail_resp = MagicMock()
    fail_resp.raise_for_status = MagicMock(
        side_effect=ClientResponseError(request_info=MagicMock(), history=(), status=503, message="Unavailable")
    )
    ok_resp = MagicMock()
    ok_resp.json = AsyncMock(return_value={"ok": True})
    ok_resp.raise_for_status = MagicMock()

    mock_session.get = MagicMock(side_effect=[MockAsyncContextManager(fail_resp), MockAsyncContextManager(ok_resp)])

    client = BaseAPIClient(mock_session, retries=1)
    result = await client._get_json("https://example.com/api")
    assert result == {"ok": True}
    assert mock_session.get.call_count == 2


async def test_get_text_success(mock_session):
    mock_session.get = mock_get_text("hello")

    client = BaseAPIClient(mock_session)
    result = await client._get_text("https://example.com/api")
    assert result == "hello"
