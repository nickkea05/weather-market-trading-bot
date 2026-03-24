"""
Auto-update module.
Runs in a background thread. At the top of every hour:
1. Checks each city's local time
2. If past noon local -> target date = tomorrow; else today
3. If any city's target date changed -> rotates slug, clears forecast, triggers refresh
Also auto-refreshes orderbooks every 5 minutes.
"""

import threading
import time
from datetime import datetime, timedelta, timezone

from cities import ALL_CITIES
from refresh import refresh_all, refresh_city


CUTOFF_HOUR = 12  # After noon local, switch to next day


def get_target_date(city) -> "date":
    """
    Determine which market date to show for a city right now.
    If city local time >= noon, show tomorrow. Otherwise show today.
    """
    utc_now = datetime.now(timezone.utc)
    city_offset = timedelta(hours=city.utc_offset)
    city_now = utc_now + city_offset

    if city_now.hour >= CUTOFF_HOUR:
        return (city_now + timedelta(days=1)).date()
    return city_now.date()


def init_dates(cache: dict):
    """Set initial target dates for all cities in the cache."""
    from cities import ALL_CITIES
    for city in ALL_CITIES:
        if city.slug not in cache:
            cache[city.slug] = {
                "date": None,
                "buckets": [],
                "center": {"label": "--", "price": 0.0},
                "forecast": None,
                "forecast_f": None,
                "forecast_source": None,
                "auto_forecast": None,
            }
        cache[city.slug]["date"] = get_target_date(city)


def check_date_rotations(cache: dict) -> list:
    """
    Check all cities for date changes. Returns list of city slugs that rotated.
    Clears forecast when date rotates (old forecast is for old date).
    """
    rotated = []
    for city in ALL_CITIES:
        new_date = get_target_date(city)
        entry = cache.get(city.slug)
        if entry and entry.get("date") != new_date:
            entry["date"] = new_date
            entry["buckets"] = []
            entry["center"] = {"label": "--", "price": 0.0}
            entry["forecast"] = None
            entry["forecast_f"] = None
            entry["forecast_source"] = None
            entry["auto_forecast"] = None
            rotated.append(city.slug)
    return rotated


def start_background(cache: dict, on_refresh=None):
    """
    Start background thread that:
    - Every 60s checks if we're at a new hour -> rotate dates + refresh rotated cities
    - Every 5 min refreshes all orderbooks
    """
    def loop():
        last_hour = datetime.now(timezone.utc).hour
        last_full_refresh = time.time()

        while True:
            time.sleep(30)

            now_utc = datetime.now(timezone.utc)

            # Hourly: check date rotations
            if now_utc.hour != last_hour:
                last_hour = now_utc.hour
                rotated = check_date_rotations(cache)
                if rotated:
                    for slug in rotated:
                        refresh_city(slug, cache)
                    if on_refresh:
                        on_refresh()

            # Every 5 minutes: full orderbook refresh
            if time.time() - last_full_refresh >= 300:
                refresh_all(cache)
                last_full_refresh = time.time()
                if on_refresh:
                    on_refresh()

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
