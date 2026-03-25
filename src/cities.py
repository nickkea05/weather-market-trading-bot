"""
City definitions for all tracked Polymarket weather markets.
Each city has: slug, resolution station, ICAO code, coordinates, timezone offset, temperature unit.
"""

from dataclasses import dataclass


@dataclass
class City:
    name: str
    slug: str           # Polymarket slug component e.g. "nyc", "seoul"
    icao: str           # ICAO station code for METAR
    lat: float
    lon: float
    utc_offset: float   # Hours from UTC (e.g. -5 for EST, +9 for KST)
    unit: str           # "F" or "C"
    bucket_size: int    # 2 for F, 1 for C
    volatile: bool      # Interior/volatile city = True, coastal/tropical = False


US_CITIES = [
    City("New York",      "nyc",           "KLGA", 40.7769, -73.874,  -5,   "F", 2, False),
    City("Chicago",       "chicago",       "KORD", 41.9742, -87.9073, -6,   "F", 2, True),
    City("Dallas",        "dallas",        "KDAL", 32.8471, -96.8518, -6,   "F", 2, True),
    City("Miami",         "miami",         "KMIA", 25.7959, -80.2870, -5,   "F", 2, False),
    City("Denver",        "denver",        "KBKF", 39.7200, -104.752, -7,   "F", 2, True),
    City("San Francisco", "san-francisco", "KSFO", 37.6213, -122.379, -8,   "F", 2, False),
    City("Seattle",       "seattle",       "KSEA", 47.4502, -122.309, -8,   "F", 2, False),
    City("Austin",        "austin",        "KAUS", 30.1944, -97.6700, -6,   "F", 2, True),
    City("Houston",       "houston",       "KHOU", 29.6454, -95.2789, -6,   "F", 2, False),
    City("Los Angeles",   "los-angeles",   "KLAX", 33.9416, -118.409, -8,   "F", 2, False),
    City("Atlanta",       "atlanta",       "KATL", 33.6407, -84.4277, -5,   "F", 2, False),
]

INTL_CITIES = [
    City("Seoul",         "seoul",         "RKSI", 37.4602, 126.441,  +9,   "C", 1, True),
    City("Shanghai",      "shanghai",      "ZSSS", 31.1979, 121.336,  +8,   "C", 1, False),
    City("Tokyo",         "tokyo",         "RJTT", 35.5533, 139.781,  +9,   "C", 1, False),
    City("Wellington",    "wellington",    "NZWN", -41.327, 174.805,  +13,  "C", 1, False),
    City("Lucknow",       "lucknow",       "VILK", 26.7606, 80.8893,  +5.5, "C", 1, True),
    City("London",        "london",        "EGLL", 51.4700, -0.4543,  +0,   "C", 1, False),
    City("Warsaw",        "warsaw",        "EPWA", 52.1657, 20.9671,  +1,   "C", 1, True),
    City("Paris",         "paris",         "LFPG", 49.0097, 2.5478,   +1,   "C", 1, False),
    City("Singapore",     "singapore",     "WSSS", 1.3502,  103.994,  +8,   "C", 1, False),
    City("Ankara",        "ankara",        "LTAC", 39.9498, 32.6882,  +3,   "C", 1, True),
    City("Hong Kong",     "hong-kong",     "VHHH", 22.3089, 113.915,  +8,   "C", 1, False),
    City("Shenzhen",      "shenzhen",      "ZGSZ", 22.6393, 113.811,  +8,   "C", 1, False),
    City("Buenos Aires",  "buenos-aires",  "SAEZ", -34.822, -58.5358, -3,   "C", 1, False),
    City("Beijing",       "beijing",       "ZBAA", 40.0725, 116.598,  +8,   "C", 1, True),
    City("Chengdu",       "chengdu",       "ZUUU", 30.5785, 103.947,  +8,   "C", 1, True),
    City("Wuhan",         "wuhan",         "ZHHH", 30.7838, 114.208,  +8,   "C", 1, True),
    City("Chongqing",     "chongqing",     "ZUCK", 29.7192, 106.642,  +8,   "C", 1, True),
    City("Toronto",       "toronto",       "CYYZ", 43.6772, -79.6306, -5,   "C", 1, True),
    City("Madrid",        "madrid",        "LEMD", 40.4719, -3.5626,  +1,   "C", 1, True),
    City("Munich",        "munich",        "EDDM", 48.3537, 11.7750,  +1,   "C", 1, True),
    City("Sao Paulo",     "sao-paulo",     "SBGR", -23.431, -46.4697, -3,   "C", 1, False),
    City("Milan",         "milan",         "LIMC", 45.6306, 8.7231,   +1,   "C", 1, False),
    City("Tel Aviv",      "tel-aviv",      "LLBG", 32.0055, 34.8854,  +2,   "C", 1, False),
    City("Taipei",        "taipei",        "RCTP", 25.0777, 121.233,  +8,   "C", 1, False),
]

ALL_CITIES = US_CITIES + INTL_CITIES

CITY_BY_SLUG = {c.slug: c for c in ALL_CITIES}


def find_city(query: str):
    """Find a city by slug or partial name match (case-insensitive)."""
    q = query.lower().strip()
    if q in CITY_BY_SLUG:
        return CITY_BY_SLUG[q]
    for c in ALL_CITIES:
        if q in c.name.lower() or q in c.slug:
            return c
    return None
