"""API clients for Paddle Conditions."""

from .base import APIError, BaseAPIClient
from .cdec import CDECClient, CDECData, CDECReading
from .noaa import NOAAClient, NOAAData, TidePrediction
from .nws import NWSClient, NWSForecast
from .open_meteo import (
    AQIData,
    OpenMeteoAQIClient,
    OpenMeteoWeatherClient,
    WeatherData,
)
from .paddle_conditions import CuratedSpot, PaddleConditionsClient, SpotStations
from .usgs import USGSClient, USGSData

__all__ = [
    "APIError",
    "AQIData",
    "BaseAPIClient",
    "CDECClient",
    "CDECData",
    "CDECReading",
    "CuratedSpot",
    "NOAAClient",
    "NOAAData",
    "NWSClient",
    "NWSForecast",
    "OpenMeteoAQIClient",
    "OpenMeteoWeatherClient",
    "PaddleConditionsClient",
    "SpotStations",
    "TidePrediction",
    "USGSClient",
    "USGSData",
    "WeatherData",
]
