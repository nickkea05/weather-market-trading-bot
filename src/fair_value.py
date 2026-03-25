"""
Fair value distribution model.
Given a forecast temperature, assigns probability to each bucket.
Peaked distribution centered on forecast.
- Tighter for coastal/tropical cities (more predictable)
- Wider for interior/volatile cities
- Bucket size: 2F for US, 1C for international
- Edge buckets (X+ and <X) accumulate tail probability from all virtual sub-buckets
"""


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


def _bucket_distance(forecast, mid, step):
    """Distance in bucket units, with standard rounding (0.5 always rounds up)."""
    return int(abs(forecast - mid) / step + 0.5)


def _edge_fair_value(label, forecast, dist, step, volatile, max_d):
    """
    Fair value for an edge bucket (e.g. "68+" or "<49").
    Expands into virtual sub-buckets and sums their probabilities,
    since these buckets capture the entire tail of the distribution.
    """
    clean = label.strip().replace("\u00b0F", "").replace("\u00b0C", "").replace("\u00b0", "").strip()
    is_upper = clean.endswith("+")

    try:
        boundary = float(clean.rstrip("+").lstrip("<"))
    except ValueError:
        return 0.0

    total = 0.0
    n_virtual = max_d * 2 + 2

    for i in range(n_virtual):
        if is_upper:
            if step == 2:
                virtual_mid = boundary + 0.5 + i * step
            else:
                virtual_mid = boundary + i
        else:
            if step == 2:
                virtual_mid = boundary - 0.5 - i * step
            else:
                virtual_mid = boundary - i

        d = _bucket_distance(forecast, virtual_mid, step)
        entry = dist.get(d)
        if entry:
            total += _pick_pct(entry, volatile)

    return total


def bucket_fair_values(forecast_temp: float, buckets: list, city) -> dict:
    """
    Given a forecast temp and list of bucket dicts (from polymarket.py),
    return {label: fair_value_pct} for each bucket.
    """
    dist = DIST_2F if city.unit == "F" else DIST_1C
    max_d = max(dist.keys())
    step = city.bucket_size
    results = {}

    for bucket in buckets:
        label = bucket["label"]
        is_upper = label.endswith("+")
        is_lower = label.startswith("<")

        if is_upper or is_lower:
            results[label] = _edge_fair_value(label, forecast_temp, dist, step, city.volatile, max_d)
        else:
            mid = _parse_bucket_midpoint(label, step)
            if mid is None:
                results[label] = 0.0
                continue

            if step == 2:
                distance = abs(round((forecast_temp - mid) / 2))
            else:
                distance = abs(round(forecast_temp - mid))

            entry = dist.get(distance, dist.get(max_d, (0, 1)))
            results[label] = _pick_pct(entry, city.volatile)

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


def forecast_in_bucket(forecast, label, bucket_size):
    """Check if a forecast temperature falls within a bucket's range."""
    clean = label.strip().replace("\u00b0F", "").replace("\u00b0C", "").replace("\u00b0", "").strip()

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
