"""
Fair value distribution model.
Given a forecast temperature, assigns probability to each bucket.
Peaked distribution centered on forecast.
- Tighter for coastal/tropical cities (more predictable)
- Wider for interior/volatile cities
- Bucket size: 2F for US, 1C for international
"""


# Distribution tables: distance_from_center -> (low%, high%)
# Volatile/interior cities use low end, coastal/tropical use high end

DIST_2F = {
    0: (33, 42),    # Center bucket
    1: (15, 25),    # +/- 1 bucket (2F away)
    2: (5, 10),     # +/- 2 buckets (4F away)
    3: (2, 4),      # +/- 3 buckets (6F away)
    4: (0.5, 2),    # +/- 4 buckets (8F away)
}

DIST_1C = {
    0: (30, 40),
    1: (18, 25),
    2: (6, 12),
    3: (2, 5),
    4: (0.5, 2),
}


def _pick_pct(dist_entry, volatile: bool) -> float:
    """Pick from range: volatile cities use low end, coastal use high end."""
    lo, hi = dist_entry
    if volatile:
        return lo
    return hi


def bucket_fair_values(forecast_temp: float, buckets: list, city) -> dict:
    """
    Given a forecast temp and list of bucket dicts (from polymarket.py),
    return {label: fair_value_pct} for each bucket.

    Bucket labels are like "48-49" (2F) or "14" (1C).
    We parse the midpoint of each bucket, compute distance from forecast,
    and assign probability from the distribution table.
    """
    dist = DIST_2F if city.unit == "F" else DIST_1C
    results = {}

    for bucket in buckets:
        label = bucket["label"]
        mid = _parse_bucket_midpoint(label, city.bucket_size)
        if mid is None:
            results[label] = 0.0
            continue

        if city.bucket_size == 2:
            distance = abs(round((forecast_temp - mid) / 2))
        else:
            distance = abs(round(forecast_temp - mid))

        dist_entry = dist.get(distance, dist.get(4, (0, 1)))
        results[label] = _pick_pct(dist_entry, city.volatile)

    return results


def _parse_bucket_midpoint(label: str, bucket_size: int):
    """
    Parse bucket label to its midpoint temperature.
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
