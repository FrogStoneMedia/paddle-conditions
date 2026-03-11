"""Tests for the base API client."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientResponseError

from custom_components.paddle_conditions.api.base import APIError, BaseAPIClient


def _make_json_response(data):
    """Create a mock response that returns JSON data."""
    resp = MagicMock()
    resp.json = AsyncMock(return_value=data)
    resp.raise_for_status = MagicMock()
    return resp


def _make_text_response(text):
    """Create a mock response that returns text."""
    resp = MagicMock()
    resp.text = AsyncMock(return_value=text)
    resp.raise_for_status = MagicMock()
    return resp


def _make_error_response(status, message):
    """Create a mock response that raises on raise_for_status."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(
        side_effect=ClientResponseError(request_info=MagicMock(), history=(), status=status, message=message)
    )
    return resp


async def test_get_json_success(mock_session):
    mock_session.get = AsyncMock(return_value=_make_json_response({"key": "value"}))

    client = BaseAPIClient(mock_session)
    result = await client._get_json("https://example.com/api")
    assert result == {"key": "value"}


async def test_get_json_timeout(mock_session):
    mock_session.get = AsyncMock(side_effect=TimeoutError)

    client = BaseAPIClient(mock_session, timeout=1)
    with pytest.raises(APIError, match="Timeout"):
        await client._get_json("https://example.com/api")


async def test_get_json_http_error(mock_session):
    mock_session.get = AsyncMock(return_value=_make_error_response(500, "Server Error"))

    client = BaseAPIClient(mock_session)
    with pytest.raises(APIError, match="Error fetching"):
        await client._get_json("https://example.com/api")


async def test_get_json_retries_on_transient_error(mock_session):
    """Should retry once on 500-level errors before raising."""
    fail_resp = _make_error_response(503, "Unavailable")
    ok_resp = _make_json_response({"ok": True})

    mock_session.get = AsyncMock(side_effect=[fail_resp, ok_resp])

    client = BaseAPIClient(mock_session, retries=1)
    result = await client._get_json("https://example.com/api")
    assert result == {"ok": True}
    assert mock_session.get.call_count == 2


async def test_get_text_success(mock_session):
    mock_session.get = AsyncMock(return_value=_make_text_response("hello"))

    client = BaseAPIClient(mock_session)
    result = await client._get_text("https://example.com/api")
    assert result == "hello"
