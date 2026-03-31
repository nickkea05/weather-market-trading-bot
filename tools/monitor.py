"""
Weather Market Monitor — 24/7 daemon for a VPS.

All-in-one background service that feeds the research terminal:
  1. Wunderground scraper   (every 20 min) — 10-day forecasts for all cities
  2. Orderbook refresh      (every 5 min)  — Polymarket prices
  3. Date rotation check    (every 60s)    — noon-local cutoff logic
  4. Forecast history        — time series per city for shift detection
  5. Shift detection         — sliding window alerts (2°F/1h, 4°F/2h, etc.)
  6. (future) Notifications  — phone/Telegram push on significant moves

Writes JSON state to tools/data/ for the local CLI to consume.

Usage:
    python tools/monitor.py
    python tools/monitor.py --scrape-interval 15
    python tools/monitor.py --no-scraper
"""

import json
import os
import sys
import time
import threading
import random
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# Allow imports from src/
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC_DIR)

from cities import ALL_CITIES, CITY_BY_SLUG
from refresh import refresh_all, refresh_city
from autoupdate import init_dates, check_date_rotations
from scraper import scrape_all as run_scraper

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(TOOLS_DIR, "data")
FORECASTS_FILE = os.path.join(DATA_DIR, "forecasts.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
ALERTS_FILE = os.path.join(DATA_DIR, "alerts.json")
CACHE_FILE = os.path.join(DATA_DIR, "cache.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ORDERBOOK_SEC = 300         # 5 minutes
DEFAULT_SCRAPE_MIN = 20     # 20 minutes
HISTORY_RETENTION_H = 4     # keep 4 hours of forecast history

THRESHOLDS = [
    {"window_min": 60,  "delta_f": 2, "delta_c": 1, "label": "1h"},
    {"window_min": 120, "delta_f": 4, "delta_c": 2, "label": "2h"},
]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
cache: dict = {}
forecast_history: dict[str, list[dict]] = defaultdict(list)
alerts: list[dict] = []

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict | list:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)


def save_cache():
    _save_json(CACHE_FILE, cache)


def save_forecasts(scraper_data: dict):
    """Write scraper output in the format the CLI's `w` command expects."""
    export = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "cities": scraper_data,
    }
    _save_json(FORECASTS_FILE, export)


def save_history():
    _save_json(HISTORY_FILE, dict(forecast_history))


def save_alerts():
    _save_json(ALERTS_FILE, alerts[-100:])


def load_state():
    global cache, forecast_history, alerts

    loaded = _load_json(CACHE_FILE)
    if isinstance(loaded, dict):
        cache.update(loaded)

    loaded_hist = _load_json(HISTORY_FILE)
    if isinstance(loaded_hist, dict):
        for k, v in loaded_hist.items():
            forecast_history[k] = v

    loaded_alerts = _load_json(ALERTS_FILE)
    if isinstance(loaded_alerts, list):
        alerts.extend(loaded_alerts)

# ---------------------------------------------------------------------------
# Scraper → cache integration
# ---------------------------------------------------------------------------

def apply_scraper_results(scraper_data: dict):
    """Push scraped forecasts into the cache and record history."""
    name_to_city = {c.name: c for c in ALL_CITIES}

    for city_name, info in scraper_data.items():
        city = name_to_city.get(city_name)
        if not city:
            continue

        entry = cache.get(city.slug)
        if not entry or not entry.get("date"):
            continue

        target_str = str(entry["date"])
        forecasts = info.get("forecasts", {})
        high = forecasts.get(target_str)

        if high is not None:
            entry["auto_forecast"] = high
            _record_history(city.slug, high, target_str)

# ---------------------------------------------------------------------------
# Forecast history & sliding window shift detection
# ---------------------------------------------------------------------------

def _record_history(slug: str, high: float, target_date: str):
    now = datetime.now(timezone.utc).isoformat()
    forecast_history[slug].append({
        "ts": now,
        "high": high,
        "target_date": target_date,
    })
    _prune_history(slug)


def _prune_history(slug: str):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=HISTORY_RETENTION_H)).isoformat()
    forecast_history[slug] = [r for r in forecast_history[slug] if r["ts"] >= cutoff]


def check_forecast_shifts() -> list[dict]:
    """Sliding window change detection.  Returns new alerts."""
    now = datetime.now(timezone.utc)
    new_alerts = []

    for city in ALL_CITIES:
        slug = city.slug
        readings = forecast_history.get(slug, [])
        if len(readings) < 2:
            continue

        target_date = readings[-1]["target_date"]
        same_date = [r for r in readings if r["target_date"] == target_date]
        if len(same_date) < 2:
            continue

        for th in THRESHOLDS:
            window_start = (now - timedelta(minutes=th["window_min"])).isoformat()
            in_window = [r for r in same_date if r["ts"] >= window_start]
            if len(in_window) < 2:
                continue

            highs = [r["high"] for r in in_window]
            spread = max(highs) - min(highs)
            delta = th["delta_f"] if city.unit == "F" else th["delta_c"]

            if spread < delta:
                continue

            direction = "UP" if in_window[-1]["high"] > in_window[0]["high"] else "DOWN"
            alert_key = f"{slug}_{th['label']}_{target_date}"

            cooldown = (now - timedelta(minutes=30)).isoformat()
            if any(a.get("key") == alert_key and a["ts"] >= cooldown for a in alerts):
                continue

            alert = {
                "key": alert_key,
                "ts": now.isoformat(),
                "city": city.name,
                "slug": slug,
                "target_date": target_date,
                "window": th["label"],
                "direction": direction,
                "spread": round(spread, 1),
                "from": in_window[0]["high"],
                "to": in_window[-1]["high"],
                "unit": city.unit,
            }
            new_alerts.append(alert)
            alerts.append(alert)

    return new_alerts

# ---------------------------------------------------------------------------
# Daemon loops
# ---------------------------------------------------------------------------

def orderbook_loop():
    """Refresh Polymarket orderbooks on a fixed interval."""
    while True:
        try:
            _log("Refreshing orderbooks...")
            count = refresh_all(cache)
            _log(f"  Orderbooks: {count}/{len(cache)} cities")
            save_cache()
        except Exception as e:
            _log(f"  Orderbook error: {e}")
        time.sleep(ORDERBOOK_SEC)


def rotation_loop():
    """Check for date rotations every 60 seconds."""
    while True:
        try:
            rotated = check_date_rotations(cache)
            if rotated:
                _log(f"Date rotation: {', '.join(rotated)}")
                for slug in rotated:
                    forecast_history[slug] = []
                    refresh_city(slug, cache)
                save_cache()
                save_history()
        except Exception as e:
            _log(f"  Rotation error: {e}")
        time.sleep(60)


def scraper_loop(interval_sec: int):
    """Scrape Wunderground forecasts, apply results, check for shifts."""
    while True:
        try:
            _log("Starting Wunderground scrape...")
            start = time.time()

            def on_progress(i, total, name, status):
                tag = "[green]ok[/green]" if status == "ok" else "[red]FAIL[/red]"
                _log(f"  [{i+1:2d}/{total}] {name:<16s} {status}")

            scraper_data = run_scraper(on_progress=on_progress)
            elapsed = time.time() - start
            _log(f"  Scrape done: {len(scraper_data)}/{len(ALL_CITIES)} cities in {elapsed:.0f}s")

            apply_scraper_results(scraper_data)
            save_forecasts(scraper_data)
            save_cache()
            save_history()

            new_alerts = check_forecast_shifts()
            if new_alerts:
                save_alerts()
                for a in new_alerts:
                    _log(
                        f"  ALERT: {a['city']} {a['direction']} "
                        f"{a['spread']}{a['unit']} in {a['window']} "
                        f"({a['from']} -> {a['to']})"
                    )
            else:
                _log("  No forecast shift alerts")

        except Exception as e:
            _log(f"  Scraper loop error: {e}")

        _log(f"  Next scrape in {interval_sec // 60} min")
        time.sleep(interval_sec)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Weather Market Monitor — 24/7 daemon")
    parser.add_argument("--scrape-interval", type=int, default=DEFAULT_SCRAPE_MIN,
                        help=f"Minutes between scrapes (default: {DEFAULT_SCRAPE_MIN})")
    parser.add_argument("--no-scraper", action="store_true",
                        help="Run without Wunderground scraper (orderbooks + rotation only)")
    args = parser.parse_args()

    scrape_sec = args.scrape_interval * 60

    _log("=" * 54)
    _log("  Weather Market Monitor")
    _log(f"  Orderbook refresh : every {ORDERBOOK_SEC // 60} min")
    _log(f"  Scraper interval  : every {args.scrape_interval} min")
    _log(f"  History retention : {HISTORY_RETENTION_H}h")
    _log(f"  Data dir          : {DATA_DIR}")
    _log("=" * 54)

    load_state()
    _log(f"Loaded {len(cache)} cached cities, {sum(len(v) for v in forecast_history.values())} history readings")

    init_dates(cache)
    save_cache()
    _log("Target dates initialized")

    _log("Initial orderbook refresh...")
    count = refresh_all(cache)
    _log(f"  {count} cities refreshed")
    save_cache()

    threading.Thread(target=orderbook_loop, daemon=True, name="orderbook").start()
    threading.Thread(target=rotation_loop, daemon=True, name="rotation").start()

    if args.no_scraper:
        _log("Scraper disabled (--no-scraper). Orderbooks + rotation only.")
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            _log("Shutting down.")
    else:
        _log("Starting scraper loop (main thread)...")
        try:
            scraper_loop(scrape_sec)
        except KeyboardInterrupt:
            _log("Shutting down.")


if __name__ == "__main__":
    main()
