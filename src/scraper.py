"""
Wunderground forecast scraper — importable from the CLI.

Core scraping logic: fetches 10-day daily highs from the embedded JSON
on wunderground.com/forecast/ pages via SeleniumBase UC mode.
"""

import re
import time
import random
from bs4 import BeautifulSoup
from seleniumbase import SB

from cities import ALL_CITIES, City

# ICAO → Wunderground URL path segment.
# Most follow the pattern "<country>/<city>/<ICAO>" but some need overrides.
WU_PATHS: dict[str, str] = {
    "KLGA": "us/ny/new-york-city/KLGA",
    "KORD": "us/il/chicago/KORD",
    "KDAL": "us/tx/dallas/KDAL",
    "KMIA": "us/fl/miami/KMIA",
    "KBKF": "us/co/aurora/KBKF",
    "KSFO": "us/ca/san-francisco/KSFO",
    "KSEA": "us/wa/seattle/KSEA",
    "KAUS": "us/tx/austin/KAUS",
    "KHOU": "us/tx/houston/KHOU",
    "KLAX": "us/ca/los-angeles/KLAX",
    "KATL": "us/ga/atlanta/KATL",
    "RKSI": "kr/incheon/RKSI",
    "ZSPD": "cn/shanghai/ZSPD",
    "RJTT": "jp/tokyo/RJTT",
    "NZWN": "nz/wellington/NZWN",
    "VILK": "in/lucknow/VILK",
    "EGLC": "gb/london/EGLC",
    "EPWA": "pl/warsaw/EPWA",
    "LFPG": "fr/paris/LFPG",
    "WSSS": "sg/singapore/WSSS",
    "LTAC": "tr/ankara/LTAC",
    "ZGSZ": "cn/shenzhen/ZGSZ",
    "SAEZ": "ar/buenos-aires/SAEZ",
    "ZBAA": "cn/beijing/ZBAA",
    "ZUUU": "cn/chengdu/ZUUU",
    "ZHHH": "cn/wuhan/ZHHH",
    "ZUCK": "cn/chongqing/ZUCK",
    "CYYZ": "ca/mississauga/CYYZ",
    "LEMD": "es/madrid/LEMD",
    "EDDM": "de/munich/EDDM",
    "SBGR": "br/sao-paulo/SBGR",
    "LIMC": "it/milan/LIMC",
}


def wu_forecast_url(icao: str) -> str:
    """Build the Wunderground 10-day forecast URL for a station."""
    path = WU_PATHS.get(icao.upper(), icao)
    return f"https://www.wunderground.com/forecast/{path}"


def f_to_c(f: int | float) -> float:
    return round((f - 32) * 5 / 9, 1)


# ---------------------------------------------------------------------------
# JSON extraction from page source
# ---------------------------------------------------------------------------

def _parse_num_array(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip().lstrip("-").isdigit()]


def _find_str_array(ctx: str, key: str) -> list[str]:
    m = re.search(rf'"{key}"\s*:\s*\[([^\]]+)\]', ctx)
    return re.findall(r'"([^"]*)"', m.group(1)) if m else []


def extract_daily_forecast(page_source: str) -> list[dict] | None:
    """Pull the longest calendarDayTemperatureMax array and sibling data."""
    soup = BeautifulSoup(page_source, "html.parser")
    best = None
    best_len = 0

    for script in soup.find_all("script"):
        text = script.string or ""
        if "calendarDayTemperatureMax" not in text:
            continue
        for m in re.finditer(r'"calendarDayTemperatureMax"\s*:\s*\[([^\]]+)\]', text):
            nums = _parse_num_array(m.group(1))
            if len(nums) <= best_len:
                continue
            ctx = text[max(0, m.start() - 500):min(len(text), m.end() + 20000)]
            dates = _find_str_array(ctx, "validTimeLocal")
            best_len = len(nums)
            best = {"highs": nums, "dates": dates}

    if not best:
        return None
    return [
        {"date": best["dates"][i][:10] if i < len(best["dates"]) else None,
         "high_f": h}
        for i, h in enumerate(best["highs"])
    ]


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def scrape_city(sb, city: City, attempt: int = 1) -> dict | None:
    """Scrape one city. Returns {date_str: temp, ...} in the city's unit, or None."""
    url = wu_forecast_url(city.icao)
    try:
        sb.open(url)
        time.sleep(random.uniform(2.0, 3.5))
        sb.wait_for_element("body", timeout=12)
        time.sleep(0.5)
    except Exception:
        if attempt < 2:
            time.sleep(2)
            return scrape_city(sb, city, attempt + 1)
        return None

    forecast = extract_daily_forecast(sb.get_page_source())
    if not forecast:
        if attempt < 2:
            time.sleep(2)
            return scrape_city(sb, city, attempt + 1)
        return None

    result: dict[str, float | int] = {}
    for entry in forecast:
        if not entry["date"]:
            continue
        if city.unit == "C":
            result[entry["date"]] = f_to_c(entry["high_f"])
        else:
            result[entry["date"]] = entry["high_f"]
    return result


def scrape_all(
    cities: list[City] | None = None,
    on_progress=None,
) -> dict[str, dict]:
    """Scrape every city in one browser session.

    Args:
        cities: list of City objects (defaults to ALL_CITIES).
        on_progress: optional callback(index, total, city_name, status)
            called after each city finishes.

    Returns:
        {city_name: {"forecasts": {date: temp, ...}, "unit": "F"|"C"}, ...}
    """
    if cities is None:
        cities = ALL_CITIES
    total = len(cities)
    all_data: dict[str, dict] = {}

    with SB(uc=True, headless=True) as sb:
        for i, city in enumerate(cities):
            if i > 0:
                time.sleep(random.uniform(1.0, 2.5))

            data = scrape_city(sb, city)
            status = "ok" if data else "fail"

            if data:
                all_data[city.name] = {"forecasts": data, "unit": city.unit}

            if on_progress:
                on_progress(i, total, city.name, status)

    return all_data
