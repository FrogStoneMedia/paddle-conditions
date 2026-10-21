"""Tests for the Paddle Conditions public API client."""

from __future__ import annotations

import pytest

from custom_components.paddle_conditions.api.base import APIError
from custom_components.paddle_conditions.api.paddle_conditions import (
    PC_API_URL,
    CuratedSpot,
    PaddleConditionsClient,
)
from custom_components.paddle_conditions.scoring import StageBaseline

from .conftest import mock_get_json

DIRECTORY = {
    "states": [
        {
            "state": "California",
            "slug": "california",
            "count": 2,
            "spots": [
                {"name": "Folsom Lake", "slug": "folsom-lake", "type": "lake", "county": None},
                {"name": "Lake Oroville", "slug": "lake-oroville-ca", "type": "reservoir", "county": "Butte"},
                {"name": "", "slug": "broken"},
            ],
        }
    ],
    "totalSpots": 2,
    "topSpots": [],
}

STATIONS = {
    "slug": "american-river",
    "name": "American River",
    "type": "river",
    "lat": 38.6,
    "lng": -121.2,
    "reservoirCapacityAf": None,
    "damOutflowThresholdCfs": 8000,
    "stations": {
        "usgs": [{"id": "11446500", "name": "Fair Oaks", "distanceKm": 1.2, "dataTypes": ["flow"]}],
        "noaa": [],
        "cdec": [{"id": "AFO", "name": "Fair Oaks", "distanceKm": 1.2, "dataTypes": ["stage"]}],
    },
    "stageBaselines": {
        "AFO": [
            {"month": 10, "p10": 1, "p25": 2, "p50": 3, "p75": 4, "p90": 5, "p95": 6, "sampleCount": 120},
            {"month": 11, "p10": None},
        ],
        "EMPTY": [],
    },
}


async def test_curated_spots(mock_session):
    mock_session.get = mock_get_json(DIRECTORY)

    spots = await PaddleConditionsClient(mock_session).curated_spots()

    assert mock_session.get.call_args.args[0] == f"{PC_API_URL}/public/spots/directory"
    assert spots == [
        CuratedSpot("folsom-lake", "Folsom Lake", "lake", None, "California"),
        CuratedSpot("lake-oroville-ca", "Lake Oroville", "reservoir", "Butte", "California"),
    ]


async def test_spot_stations(mock_session):
    mock_session.get = mock_get_json(STATIONS)

    spot = await PaddleConditionsClient(mock_session).spot_stations("american-river")

    assert mock_session.get.call_args.args[0] == f"{PC_API_URL}/public/spot/american-river/stations"
    assert (spot.latitude, spot.longitude) == (38.6, -121.2)
    assert spot.usgs == ("11446500",)
    assert spot.noaa == ()
    assert spot.cdec == ("AFO",)
    assert spot.reservoir_capacity_af is None
    assert spot.dam_outflow_threshold_cfs == 8000
    # Malformed months and empty stations are dropped.
    assert spot.stage_baselines == {"AFO": {10: StageBaseline(1, 2, 3, 4, 5, 6, 120)}}


async def test_spot_stations_requires_coordinates(mock_session):
    mock_session.get = mock_get_json({**STATIONS, "lat": None})
    with pytest.raises(APIError):
        await PaddleConditionsClient(mock_session).spot_stations("american-river")
