"""
Time-aware fair value model using Laplace distribution.

The distribution width (scale parameter b = MAE) scales with lead time —
hours from now until the expected daily high (2pm local). City-specific
multipliers account for forecast difficulty.

Laplace was chosen because temperature forecast errors are leptokurtic
(sharper center, fatter tails than Gaussian), matching observed
verification data.

MAE by lead time (°F):
    6h: 1.0  |  12h: 1.4  |  24h: 2.2  |  48h: 3.2
    72h: 3.6 | 120h: 4.5  | 168h: 5.5  | 240h: 7.0

Sources:
  Meteoblue global verification (12h MAE 0.8°C ≈ 1.4°F, 24h MAE 1.2°C ≈ 2.2°F)
  NOAA Weather Prediction Center max temperature MAE (Day 1-7)
  ForecastWatch accuracy reports
"""

import math
from datetime import datetime, timezone, timedelta


# MAE in °F at various lead times (hours). Interpolated linearly.
MAE_TABLE_F = [
    (6,   1.0),
    (12,  1.4),
    (24,  2.2),
    (48,  3.2),
    (72,  3.6),
    (120, 4.5),
    (168, 5.5),
    (240, 7.0),
]

COASTAL_TROPICAL = {"singapore", "miami", "shenzhen", "houston"}
INTERIOR_VOLATILE = {
    "chicago", "dallas", "denver", "austin", "ankara", "beijing",
    "chengdu", "warsaw", "munich", "madrid", "buenos-aires", "sao-paulo",
}

PEAK_HOUR_LOCAL = 14  # daily high typically at 2pm


# ---------------------------------------------------------------------------
# Lead time + MAE
# ---------------------------------------------------------------------------

def get_lead_time_hours(city, target_date) -> float:
    """Hours from now until the expected daily high (2pm local)."""
    peak_local = datetime(
        target_date.year, target_date.month, target_date.day,
        PEAK_HOUR_LOCAL, 0,
    )
    peak_utc = peak_local - timedelta(hours=city.utc_offset)
    peak_utc = peak_utc.replace(tzinfo=timezone.utc)
    hours = (peak_utc - datetime.now(timezone.utc)).total_seconds() / 3600
    return max(hours, 1.0)


def _interpolate_mae_f(hours: float) -> float:
    """Linearly interpolate MAE (°F) from the lookup table."""
    if hours <= MAE_TABLE_F[0][0]:
        return MAE_TABLE_F[0][1]
    if hours >= MAE_TABLE_F[-1][0]:
        return MAE_TABLE_F[-1][1]
    for i in range(len(MAE_TABLE_F) - 1):
        h0, m0 = MAE_TABLE_F[i]
        h1, m1 = MAE_TABLE_F[i + 1]
        if h0 <= hours <= h1:
            t = (hours - h0) / (h1 - h0)
            return m0 + t * (m1 - m0)
    return MAE_TABLE_F[-1][1]


def _city_multiplier(city) -> float:
    if city.slug in COASTAL_TROPICAL:
        return 0.75
    if city.slug in INTERIOR_VOLATILE:
        return 1.3
    return 1.0


def get_mae(city, target_date) -> float:
    """MAE for a city at the current lead time, in the city's native unit."""
    hours = get_lead_time_hours(city, target_date)
    mae_f = _interpolate_mae_f(hours) * _city_multiplier(city)
    if city.unit == "C":
        return mae_f / 1.8
    return mae_f


def get_edge_threshold(city, target_date=None) -> float:
    """Dynamic edge threshold — scales with lead time uncertainty.
    Returns the threshold in the city's native unit (°F or °C)."""
    if target_date is not None:
        return get_mae(city, target_date)
    mae_f = _interpolate_mae_f(24) * _city_multiplier(city)
    if city.unit == "C":
        return mae_f / 1.8
    return mae_f


# ---------------------------------------------------------------------------
# Laplace distribution
# ---------------------------------------------------------------------------

def _laplace_cdf(x: float, mu: float, b: float) -> float:
    if b <= 0:
        return 1.0 if x >= mu else 0.0
    z = (x - mu) / b
    if z < 0:
        return 0.5 * math.exp(z)
    return 1.0 - 0.5 * math.exp(-z)


def _bucket_bounds(label: str, bucket_size: int):
    """(lower, upper) bounds for a bucket.
    Uses ±0.5 boundaries because reported temps are integers."""
    clean = label.strip().replace("\u00b0F", "").replace("\u00b0C", "")
    clean = clean.replace("\u00b0", "").strip()

    if clean.endswith("+"):
        try:
            return (float(clean.rstrip("+")) - 0.5, None)
        except ValueError:
            return (None, None)

    if clean.startswith("<"):
        try:
            return (None, float(clean.lstrip("<")) + 0.5)
        except ValueError:
            return (None, None)

    if "-" in clean and not clean.startswith("-"):
        parts = clean.split("-")
        try:
            lo = float(parts[0].strip())
            hi = float(parts[1].strip().rstrip("+"))
            return (lo - 0.5, hi + 0.5)
        except ValueError:
            return (None, None)

    try:
        val = float(clean)
        return (val - 0.5, val + 0.5)
    except ValueError:
        return (None, None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def bucket_fair_values(forecast_temp: float, buckets: list, city,
                       target_date=None) -> dict:
    """Compute fair value (%) for each bucket using Laplace(forecast, MAE).
    target_date enables time-aware scaling; falls back to 24h if None."""
    if target_date is not None:
        b = get_mae(city, target_date)
    else:
        mae_f = _interpolate_mae_f(24) * _city_multiplier(city)
        b = mae_f / 1.8 if city.unit == "C" else mae_f

    results = {}
    for bucket in buckets:
        label = bucket["label"]
        lo, hi = _bucket_bounds(label, city.bucket_size)

        if lo is None and hi is None:
            results[label] = 0.0
            continue

        if lo is None:
            prob = _laplace_cdf(hi, forecast_temp, b)
        elif hi is None:
            prob = 1.0 - _laplace_cdf(lo, forecast_temp, b)
        else:
            prob = _laplace_cdf(hi, forecast_temp, b) - _laplace_cdf(lo, forecast_temp, b)

        results[label] = round(prob * 100, 1)

    return results


def _parse_bucket_midpoint(label: str, bucket_size: int):
    """Parse bucket label to its midpoint temperature.
    "48-49" -> 48.5, "14" -> 14.0, "72+" -> 72.5, "<40" -> 39.5
    """
    label = label.strip().replace("\u00b0F", "").replace("\u00b0C", "")
    label = label.replace("\u00b0", "").strip()

    if "-" in label and not label.startswith("-"):
        parts = label.split("-")
        try:
            lo = float(parts[0].strip())
            hi = float(parts[1].strip().rstrip("+"))
            return (lo + hi) / 2
        except ValueError:
            pass

    if label.endswith("+"):
        try:
            return float(label.rstrip("+")) + bucket_size / 2
        except ValueError:
            pass

    if label.startswith("<"):
        try:
            return float(label.lstrip("<")) - bucket_size / 2
        except ValueError:
            pass

    try:
        return float(label)
    except ValueError:
        return None


def forecast_in_bucket(forecast, label, bucket_size):
    """Check if a forecast temperature falls within a bucket's range."""
    clean = label.strip().replace("\u00b0F", "").replace("\u00b0C", "")
    clean = clean.replace("\u00b0", "").strip()

    if clean.endswith("+"):
        try:
            return forecast >= float(clean.rstrip("+"))
        except ValueError:
            return False

    if clean.startswith("<"):
        try:
            return forecast <= float(clean.lstrip("<"))
        except ValueError:
            return False

    mid = _parse_bucket_midpoint(clean, bucket_size)
    if mid is None:
        return False
    return abs(forecast - mid) < bucket_size / 2 + 0.1
