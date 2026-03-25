"""
Auto-forecast estimates using WeatherAPI.com.
Queries by ICAO code for station-level accuracy (matches Wunderground resolution stations).
Free tier: 100k calls/month, 3-day forecast.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_API_URL = "https://api.weatherapi.com/v1/forecast.json"


def fetch_estimate(city, target_date) -> float | None:
    """Fetch estimated daily high from WeatherAPI.com for a city and date.
    Uses ICAO code for station-level accuracy.
    Returns temp in the city's display unit (°F or °C), or None on failure."""
    if not WEATHER_API_KEY:
        return None
    try:
        resp = requests.get(WEATHER_API_URL, params={
            "key": WEATHER_API_KEY,
            "q": f"metar:{city.icao}",
            "days": 3,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        target_str = str(target_date)
        for day in data.get("forecast", {}).get("forecastday", []):
            if day.get("date") == target_str:
                if city.unit == "F":
                    return round(day["day"]["maxtemp_f"], 1)
                return round(day["day"]["maxtemp_c"], 1)
    except Exception:
        pass
    return None


def fetch_all_estimates(cache: dict, cities: list) -> int:
    """Fetch estimates for all cities. Updates cache in place. Returns count."""
    if not WEATHER_API_KEY:
        return 0
    count = 0
    for city in cities:
        entry = cache.get(city.slug)
        if not entry or not entry.get("date"):
            continue
        temp = fetch_estimate(city, entry["date"])
        if temp is not None:
            entry["auto_forecast"] = temp
            count += 1
    return count
