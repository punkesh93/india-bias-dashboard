import json
import os
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")


def load(name, default=None):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))


def range_index(values, lookback):
    """Williams-style COT index: where each value sits in its trailing range (0-100)."""
    out = []
    for i in range(len(values)):
        if i + 1 < lookback:
            out.append(None)
            continue
        window = values[i + 1 - lookback: i + 1]
        lo, hi = min(window), max(window)
        out.append(50.0 if hi == lo else round((values[i] - lo) / (hi - lo) * 100, 1))
    return out
