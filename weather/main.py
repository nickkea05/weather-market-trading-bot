"""
Polymarket Weather Edge Finder
Entry point. Rich display, command loop, state management.
"""

import json
import os
import sys
from datetime import date as date_type, datetime, timezone

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from cities import ALL_CITIES, find_city, CITY_BY_SLUG
from fair_value import bucket_fair_values, _parse_bucket_midpoint
from forecast_api import fetch_all_estimates
from refresh import refresh_all, refresh_city
from autoupdate import init_dates, start_background

console = Console()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "cache.json")

# In-memory cache: {city_slug: {date, buckets, center, forecast, forecast_source, forecast_f}}
cache = {}


# ============================================================================
# PERSISTENCE — full cache (market data + forecasts) survives restarts
# ============================================================================

def save_cache():
    """Persist entire cache to disk — market data, centers, and forecasts."""
    serializable = {}
    for slug, entry in cache.items():
        d = entry.get("date")
        serializable[slug] = {
            "date": str(d) if d else None,
            "buckets": entry.get("buckets", []),
            "center": entry.get("center", {"label": "--", "price": 0.0}),
            "forecast": entry.get("forecast"),
            "forecast_f": entry.get("forecast_f"),
            "forecast_source": entry.get("forecast_source"),
            "auto_forecast": entry.get("auto_forecast"),
        }
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "cities": serializable,
    }
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass


def load_cache():
    """Load cached market data and forecasts from disk.
    Only restores data for cities whose target date hasn't changed since last save."""
    if not os.path.exists(CACHE_FILE):
        return 0
    try:
        with open(CACHE_FILE, "r") as f:
            payload = json.load(f)
    except Exception:
        return 0

    saved_at = payload.get("saved_at", "")
    cities_data = payload.get("cities", {})
    restored = 0

    for slug, saved in cities_data.items():
        if slug not in cache:
            continue
        current_date_str = str(cache[slug].get("date", ""))
        if saved.get("date") != current_date_str:
            continue

        if saved.get("buckets"):
            cache[slug]["buckets"] = saved["buckets"]
            cache[slug]["center"] = saved.get("center", {"label": "--", "price": 0.0})
            restored += 1

        if saved.get("forecast") is not None:
            cache[slug]["forecast"] = saved["forecast"]
            cache[slug]["forecast_f"] = saved.get("forecast_f")
            cache[slug]["forecast_source"] = saved.get("forecast_source", "manual")

        if saved.get("auto_forecast") is not None:
            cache[slug]["auto_forecast"] = saved["auto_forecast"]

    return restored


# ============================================================================
# DISPLAY
# ============================================================================

def render_table():
    """Build and print the main market table."""
    now = datetime.now(timezone.utc)
    madrid_hour = (now.hour + 1) % 24
    madrid_str = now.strftime(f"%b %d, {madrid_hour}:%M CET")

    console.print(f"\n  Polymarket Weather Edge Finder")
    console.print(f"  Madrid time: {madrid_str}")
    console.print()

    table = Table(show_header=True, header_style="bold", pad_edge=True, expand=False)
    table.add_column("City", min_width=16)
    table.add_column("Date", min_width=7)
    table.add_column("Center", min_width=14)
    table.add_column("Forecast", min_width=10)
    table.add_column("Estimate", min_width=9)
    table.add_column("Gap", min_width=7)
    table.add_column("Status", min_width=12)

    for city in ALL_CITIES:
        entry = cache.get(city.slug, {})
        target_date = entry.get("date")
        date_str = target_date.strftime("%b %d") if target_date else "--"

        center = entry.get("center", {})
        center_label = center.get("label", "--")
        center_price = center.get("price", 0)
        unit = city.unit
        if center_price > 0:
            center_str = f"{center_label}°{unit} @{center_price*100:.0f}c"
        else:
            center_str = "--"

        # Manual forecast
        forecast = entry.get("forecast")
        if forecast is not None:
            forecast_str = f"{forecast}°{unit}"
        else:
            forecast_str = "--"

        # Auto estimate
        auto = entry.get("auto_forecast")
        if auto is not None:
            auto_str = f"{auto}°{unit}"
        else:
            auto_str = "--"

        # Gap + status: prefer manual, fall back to auto estimate
        gap_str = "--"
        status = "[dim]No data[/dim]" if center_price == 0 else "[dim]--[/dim]"
        effective_forecast = forecast if forecast is not None else auto
        is_manual = forecast is not None

        if effective_forecast is not None and center_price > 0:
            center_mid = _parse_center_temp(center_label, city.bucket_size)
            if center_mid is not None:
                gap = effective_forecast - center_mid
                gap_str = f"{gap:+.0f}°{unit}"
                threshold = 2 if unit == "F" else 1
                if abs(gap) >= threshold:
                    if is_manual:
                        status = "[bold red]** EDGE **[/bold red]"
                    else:
                        status = "[yellow]Potential[/yellow]"
                elif abs(gap) >= threshold / 2:
                    status = "[yellow]Possible[/yellow]"
                else:
                    status = "[green]Fair[/green]"

        table.add_row(city.name, date_str, center_str, forecast_str, auto_str, gap_str, status)

    console.print(table)


def _print_commands():
    console.print()
    console.print("Commands:")
    console.print('  f <city> <temp>  — Input forecast in °F (auto-converts to °C)')
    console.print("  c <city>         — Clear forecast for a city")
    console.print("  o                — Overview table (all cities)")
    console.print("  d <city>         — Detailed analysis for a city")
    console.print("  a                — Show price discrepancies")
    console.print("  p / p <city>     — Wunderground + Polymarket links")
    console.print("  r                — Refresh orderbooks now")
    console.print("  q                — Quit")
    console.print()


def _parse_center_temp(label: str, bucket_size: int):
    """Parse center bucket label to midpoint temp.
    Labels are clean: '50-51', '14', '60+', '<41'.
    """
    label = label.strip()
    label = label.replace("\u00b0F", "").replace("\u00b0C", "").replace("\u00b0", "").strip()

    if label.startswith("<"):
        try:
            return float(label[1:]) - bucket_size / 2
        except ValueError:
            return None

    if "-" in label and not label.startswith("-"):
        parts = label.split("-")
        try:
            return (float(parts[0]) + float(parts[1].rstrip("+"))) / 2
        except ValueError:
            pass

    try:
        return float(label.rstrip("+"))
    except ValueError:
        return None


# ============================================================================
# COMMANDS
# ============================================================================

def _f_to_c(f: float) -> float:
    return (f - 32) * 5 / 9


def cmd_forecast(args: str):
    """f <city> <temp> -- set manual forecast. Temp is always °F (from Wunderground).
    Auto-converts to °C for international cities."""
    parts = args.strip().split()
    if len(parts) < 2:
        console.print("  Usage: f <city> <temp>  (temp always in °F)")
        return

    temp_str = parts[-1]
    city_query = " ".join(parts[:-1])

    try:
        temp_f = float(temp_str)
    except ValueError:
        console.print(f"  Invalid temperature: {temp_str}")
        return

    city = find_city(city_query)
    if not city:
        console.print(f"  City not found: {city_query}")
        return

    entry = cache.get(city.slug)
    if not entry:
        console.print(f"  No cache entry for {city.name}")
        return

    if city.unit == "C":
        temp = round(_f_to_c(temp_f), 1)
        console.print(f"  {city.name} uses °C — converted {temp_f}°F → {temp}°C")
    else:
        temp = temp_f

    entry["forecast"] = temp
    entry["forecast_f"] = temp_f
    entry["forecast_source"] = "manual"
    save_cache()
    console.print(f"  {city.name} forecast set to {temp}°{city.unit} for {entry['date']}")


def cmd_clear(args: str):
    """c <city> -- clear forecast for a city."""
    city_query = args.strip()
    if not city_query:
        console.print("  Usage: c <city>")
        return

    city = find_city(city_query)
    if not city:
        console.print(f"  City not found: {city_query}")
        return

    entry = cache.get(city.slug)
    if not entry or entry.get("forecast") is None:
        console.print(f"  {city.name} has no forecast to clear.")
        return

    entry["forecast"] = None
    entry["forecast_f"] = None
    entry["forecast_source"] = None
    save_cache()
    console.print(f"  Cleared forecast for {city.name} ({entry.get('date')})")


def cmd_refresh():
    """r -- refresh all orderbooks."""
    console.print("  Refreshing orderbooks...")
    count = refresh_all(cache)
    save_cache()
    console.print(f"  Refreshed {count}/{len(cache)} cities")


def cmd_arbitrage():
    """a -- scan for arbitrage / edge across all cities with forecasts."""
    found = False
    for city in ALL_CITIES:
        entry = cache.get(city.slug, {})
        forecast = entry.get("forecast")
        buckets = entry.get("buckets", [])
        if forecast is None or not buckets:
            continue

        fv = bucket_fair_values(forecast, buckets, city)
        center = entry.get("center", {})

        console.print(f"\n  --- {city.name} ({city.icao}) | Forecast: {forecast}°{city.unit} ---")

        for b in buckets:
            label = b["label"]
            yes_price = b.get("yes_price") or b.get("yes_bid") or 0
            fair = fv.get(label, 0)
            edge = fair - (yes_price * 100)
            marker = ""
            if edge > 5:
                marker = " << UNDERPRICED"
                found = True
            elif edge < -5:
                marker = " << OVERPRICED"
                found = True
            console.print(
                f"    {label:>10}  Mkt: {yes_price*100:5.1f}c  FV: {fair:5.1f}c  Edge: {edge:+5.1f}c{marker}"
            )

        nearby_cost = 0
        nearby_labels = []
        for b in buckets:
            label = b["label"]
            mid = _parse_center_temp(label, city.bucket_size)
            if mid is None:
                continue
            dist = abs(forecast - mid)
            threshold = 4 if city.unit == "F" else 2
            if dist <= threshold:
                nearby_cost += (b.get("yes_price") or b.get("yes_bid") or 0)
                nearby_labels.append(label)

        if nearby_labels and nearby_cost < 0.85:
            profit = (1.0 - nearby_cost) * 100
            labels_str = "+".join(nearby_labels)
            console.print(
                f"    ARB: {labels_str} = {nearby_cost*100:.1f}c -> {profit:.0f}c guaranteed profit"
            )
            found = True

    if not found:
        console.print("\n  No edges or arbitrage found.")


def cmd_detail(args: str):
    """d <city> -- comprehensive analysis for one city."""
    city_query = args.strip()
    if not city_query:
        console.print("  Usage: d <city>")
        return

    city = find_city(city_query)
    if not city:
        console.print(f"  City not found: {city_query}")
        return

    entry = cache.get(city.slug, {})
    buckets = entry.get("buckets", [])
    forecast = entry.get("forecast")
    forecast_f = entry.get("forecast_f")
    target_date = entry.get("date", "--")
    center = entry.get("center", {})
    center_label = center.get("label", "--")
    center_price = center.get("price", 0)
    unit = city.unit

    # --- Header ---
    console.print()
    console.print(Panel(
        f"[bold]{city.name}[/bold] ({city.icao})  —  {target_date}",
        subtitle=f"Polymarket: highest-temperature-in-{city.slug}",
        width=70,
    ))

    # Forecast info
    if forecast is not None:
        fc_str = f"{forecast}°{unit}"
        if city.unit == "C" and forecast_f is not None:
            fc_str += f"  (entered as {forecast_f}°F)"
        console.print(f"  Forecast:      {fc_str}")
    else:
        console.print("  Forecast:      [dim]not set — use 'f {city.slug} <temp>'[/dim]")

    if center_price > 0:
        console.print(f"  Market center: {center_label}°{unit} @{center_price*100:.0f}c")
    else:
        console.print("  Market center: [dim]no data[/dim]")

    # Gap summary
    if forecast is not None and center_price > 0:
        center_mid = _parse_center_temp(center_label, city.bucket_size)
        if center_mid is not None:
            gap = forecast - center_mid
            threshold = 2 if unit == "F" else 1
            if abs(gap) >= threshold:
                console.print(f"  Gap:           [bold red]{gap:+.1f}°{unit} — EDGE DETECTED[/bold red]")
            elif abs(gap) >= threshold / 2:
                console.print(f"  Gap:           [yellow]{gap:+.1f}°{unit} — Possible edge[/yellow]")
            else:
                console.print(f"  Gap:           [green]{gap:+.1f}°{unit} — Fair[/green]")

    if not buckets:
        console.print("\n  No orderbook data. Run 'r' to refresh.")
        return

    # --- Bucket table ---
    has_forecast = forecast is not None
    fv = bucket_fair_values(forecast, buckets, city) if has_forecast else {}

    console.print()
    tbl = Table(show_header=True, header_style="bold", pad_edge=True, expand=False, title="Bucket Analysis")
    tbl.add_column("Bucket", justify="right", min_width=10)
    tbl.add_column("Mkt Price", justify="right", min_width=10)
    tbl.add_column("Buy YES", justify="right", min_width=9)
    tbl.add_column("Buy NO", justify="right", min_width=9)
    if has_forecast:
        tbl.add_column("Fair Value", justify="right", min_width=10)
        tbl.add_column("Edge", justify="right", min_width=8)
        tbl.add_column("Signal", min_width=14)

    buy_opportunities = []

    for b in buckets:
        label = b["label"]
        yes_price = b.get("yes_price") or 0
        yes_ask = b.get("yes_ask") or yes_price
        no_price = 1.0 - yes_price if yes_price else 0

        price_str = f"{yes_price*100:.1f}c"
        buy_yes_str = f"{yes_ask*100:.1f}c"
        buy_no_str = f"{no_price*100:.1f}c"

        marker = ""
        if label == center_label:
            marker += " [bold cyan]◄ CENTER[/bold cyan]"

        row = [f"{label}°{unit}", price_str, buy_yes_str, buy_no_str]

        if has_forecast:
            fair = fv.get(label, 0)
            edge = fair - (yes_price * 100)
            fair_str = f"{fair:.1f}c"
            edge_str = f"{edge:+.1f}c"

            mid = _parse_bucket_midpoint(label, city.bucket_size)
            if mid is not None and abs(forecast - mid) < city.bucket_size / 2 + 0.1:
                marker += " [bold green]◄ FORECAST[/bold green]"

            if edge > 5:
                signal = f"[bold green]BUY YES[/bold green]{marker}"
                if yes_ask > 0:
                    pct_edge = (edge / (yes_price * 100)) * 100 if yes_price > 0 else 0
                    buy_opportunities.append((label, yes_ask, fair, pct_edge))
            elif edge < -5:
                signal = f"[bold red]BUY NO[/bold red]{marker}"
            else:
                signal = f"[dim]—[/dim]{marker}"

            row.extend([fair_str, edge_str, signal])
        else:
            row[0] += marker

        tbl.add_row(*row)

    console.print(tbl)

    if not has_forecast:
        console.print(f"\n  [dim]Set a forecast to see fair values and edge analysis: f {city.slug} <temp>[/dim]")
        return

    # --- Opportunities ---
    console.print()
    if buy_opportunities:
        buy_opportunities.sort(key=lambda x: x[3], reverse=True)
        console.print("[bold]  Best opportunities:[/bold]")
        for label, ask, fair, pct in buy_opportunities:
            console.print(f"    BUY {label}°{unit} YES at {ask*100:.1f}c  (FV {fair:.0f}c, {pct:+.0f}% edge)")
    else:
        console.print("  [dim]No significant buy opportunities.[/dim]")

    # --- Coverage / arb check ---
    nearby_cost = 0
    nearby_labels = []
    for b in buckets:
        label = b["label"]
        mid = _parse_center_temp(label, city.bucket_size)
        if mid is None:
            continue
        dist = abs(forecast - mid)
        threshold = 4 if unit == "F" else 2
        if dist <= threshold:
            price = b.get("yes_price") or b.get("yes_bid") or 0
            nearby_cost += price
            nearby_labels.append((label, price))

    if nearby_labels:
        console.print()
        console.print("[bold]  Coverage check[/bold] (buckets near forecast):")
        label_parts = []
        for label, price in nearby_labels:
            label_parts.append(f"{label}°{unit}={price*100:.0f}c")
        console.print(f"    {' + '.join(label_parts)}")
        console.print(f"    Total cost: {nearby_cost*100:.1f}c")

        if nearby_cost < 0.85:
            profit = (1.0 - nearby_cost) * 100
            console.print(f"    [bold green]→ {profit:.0f}c guaranteed profit if temp lands in range[/bold green]")
        elif nearby_cost < 1.0:
            console.print(f"    [dim]→ Covers range but no arb (cost > 85c)[/dim]")
        else:
            console.print(f"    [dim]→ Overpriced range (cost > $1)[/dim]")

    # --- Fair value distribution ---
    console.print()
    console.print("[bold]  Implied probability distribution[/bold] (your forecast model):")
    sorted_fv = sorted(fv.items(), key=lambda x: x[1], reverse=True)
    for label, pct in sorted_fv:
        if pct < 0.5:
            continue
        bar_len = int(pct / 2)
        bar = "█" * bar_len
        mid = _parse_bucket_midpoint(label, city.bucket_size)
        dist_from_fc = ""
        if mid is not None:
            d = mid - forecast
            if abs(d) < 0.1:
                dist_from_fc = " ← forecast"
            else:
                dist_from_fc = f" ({d:+.0f}°{unit})"
        console.print(f"    {label:>8}°{unit}  {bar} {pct:.1f}%{dist_from_fc}")


def cmd_pages(args: str):
    """p [city] -- show Wunderground forecast + Polymarket links."""
    from polymarket import build_slug

    if args.strip():
        city = find_city(args.strip())
        if not city:
            console.print(f"  City not found: {args.strip()}")
            return
        cities = [city]
    else:
        cities = ALL_CITIES

    for city in cities:
        entry = cache.get(city.slug, {})
        target_date = entry.get("date")
        date_str = target_date.strftime("%b %d") if target_date else "?"

        console.print(f"\n  [bold]{city.name}[/bold] ({city.icao}) — {date_str}")
        console.print(f"    Forecast:   https://www.wunderground.com/forecast/{city.icao}")
        if target_date:
            slug = build_slug(city.slug, target_date)
            console.print(f"    History:    https://www.wunderground.com/history/daily/{city.icao}/date/{target_date}")
            console.print(f"    Polymarket: https://polymarket.com/event/{slug}")
        else:
            console.print(f"    Polymarket: https://polymarket.com/event/highest-temperature-in-{city.slug}")

    console.print()


# ============================================================================
# MAIN
# ============================================================================

def _dispatch(cmd: str) -> bool:
    """Route a command string to the appropriate handler. Returns False to quit."""
    if cmd == "q":
        return False
    elif cmd == "o":
        render_table()
    elif cmd == "r":
        cmd_refresh()
    elif cmd.startswith("f "):
        cmd_forecast(cmd[2:])
    elif cmd == "a":
        cmd_arbitrage()
    elif cmd.startswith("d "):
        cmd_detail(cmd[2:])
    elif cmd.startswith("c "):
        cmd_clear(cmd[2:])
    elif cmd == "p" or cmd.startswith("p "):
        cmd_pages(cmd[1:] if cmd.startswith("p ") else "")
    else:
        console.print(f"  Unknown command: {cmd}")
    return True


def main():
    import threading

    init_dates(cache)

    # Load cached data from last session (market data + forecasts)
    restored = load_cache()
    if restored > 0:
        console.print(f"\n  Restored {restored}/{len(ALL_CITIES)} cities from cache.")

        # Fetch any cities that weren't in cache (date rotated, new cities, etc.)
        missing = [c for c in ALL_CITIES if not cache.get(c.slug, {}).get("buckets")]
        if missing:
            console.print(f"  Fetching {len(missing)} uncached cities...")
            for city in missing:
                success = refresh_city(city.slug, cache)
                if success:
                    console.print(f"  [green]✓[/green] {city.name}")
                else:
                    console.print(f"  [red]✗[/red] {city.name} [dim](no market data)[/dim]")

        # Fetch auto-estimates for cities that don't have them
        no_estimate = [c for c in ALL_CITIES if cache.get(c.slug, {}).get("auto_forecast") is None]
        if no_estimate:
            console.print(f"  Fetching weather estimates for {len(no_estimate)} cities...")
            est_count = fetch_all_estimates(cache, no_estimate)
            console.print(f"  Got {est_count} estimates from Open-Meteo.")

        save_cache()
        console.print("  Updating live prices in background...\n")
        start_background(cache, on_refresh=save_cache)
        threading.Thread(target=_background_refresh, daemon=True).start()
    else:
        console.print("\n  No cache found. Fetching orderbooks for all cities...\n")
        count = 0
        for city in ALL_CITIES:
            success = refresh_city(city.slug, cache)
            if success:
                count += 1
                console.print(f"  [green]✓[/green] {city.name}")
            else:
                console.print(f"  [red]✗[/red] {city.name} [dim](no market data)[/dim]")
        console.print(f"\n  Loaded {count}/{len(ALL_CITIES)} cities")

        console.print("  Fetching weather estimates...")
        est_count = fetch_all_estimates(cache, ALL_CITIES)
        console.print(f"  Got {est_count} estimates from Open-Meteo.\n")

        save_cache()
        start_background(cache, on_refresh=save_cache)

    # Show overview on startup then drop into prompt
    render_table()
    _print_commands()

    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  Shutting down.\n")
            save_cache()
            return

        if not cmd:
            continue

        if not _dispatch(cmd):
            console.print("\n  Shutting down.\n")
            save_cache()
            return

        _print_commands()


def _background_refresh():
    """One-shot refresh all cities and estimates, save to cache. Runs in a thread."""
    refresh_all(cache)
    fetch_all_estimates(cache, ALL_CITIES)
    save_cache()


if __name__ == "__main__":
    main()
