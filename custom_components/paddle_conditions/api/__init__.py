"""API clients for Paddle Conditions."""

from .base import APIError, BaseAPIClient
from .noaa import NOAAClient, NOAAData, TidePrediction
from .open_meteo import (
    AQIData,
    OpenMeteoAQIClient,
    OpenMeteoWeatherClient,
    WeatherData,
)
from .usgs import USGSClient, USGSData

__all__ = [
    "APIError",
    "AQIData",
    "BaseAPIClient",
    "NOAAClient",
    "NOAAData",
    "OpenMeteoAQIClient",
    "OpenMeteoWeatherClient",
    "TidePrediction",
    "USGSClient",
    "USGSData",
    "WeatherData",
]
