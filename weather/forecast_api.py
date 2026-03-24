"""
Auto-forecast estimates using Open-Meteo API.
Free, no API key needed. Returns daily max temperature forecasts.
These are model estimates — less accurate than checking Wunderground manually,
but useful as a baseline to spot obvious mispricings across all 35 cities.
"""

import requests

OPEN_METEO_API = "https://api.open-meteo.com/v1/forecast"


def _c_to_f(c: float) -> float:
    return c * 9 / 5 + 32


def fetch_estimate(city, target_date) -> float | None:
    """Fetch estimated daily high from Open-Meteo for a city and date.
    Returns temp in the city's display unit (°F or °C), or None on failure."""
    try:
        resp = requests.get(OPEN_METEO_API, params={
            "latitude": city.lat,
            "longitude": city.lon,
            "daily": "temperature_2m_max",
            "timezone": "auto",
            "forecast_days": 16,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        times = daily.get("time", [])
        temps = daily.get("temperature_2m_max", [])

        target_str = str(target_date)
        for i, t in enumerate(times):
            if t == target_str:
                temp_c = temps[i]
                if temp_c is None:
                    return None
                if city.unit == "F":
                    return round(_c_to_f(temp_c), 1)
                return round(temp_c, 1)
    except Exception:
        pass
    return None


def fetch_all_estimates(cache: dict, cities: list) -> int:
    """Fetch estimates for all cities. Updates cache in place. Returns count."""
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
