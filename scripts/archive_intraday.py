"""Grow a permanent 15-minute history (Yahoo only serves the last 60 days)."""
import os

import pandas as pd

from common import DATA


def merge(key, df):
    folder = os.path.join(DATA, "intraday_hist")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{key}_15m.csv")
    if os.path.exists(path):
        old = pd.read_csv(path, index_col=0)
        old.index = pd.to_datetime(old.index).tz_localize("Asia/Kolkata")
        df = pd.concat([old, df])
        df = df[~df.index.duplicated(keep="last")].sort_index()
    out = df.copy()
    out.index = out.index.tz_localize(None)
    out.round(2).to_csv(path)
    print(f"   archive {key}: {len(df)} bars, {len(set(df.index.date))} sessions")
    return df
