"""Backfill NSE participant-wise OI history into data/participant_oi_hist.json.  Usage: nse_backfill.py START END"""
import sys
import time
from datetime import date, timedelta

import requests

from common import load, save
from fetch_nse import HEADERS, URL, parse


def main(start, end):
    hist = load("participant_oi_hist.json", {}) or {}
    rows = {r["d"]: r for r in hist.get("rows", [])}
    cur = sorted(r["d"] for r in (load("participant_oi.json", {}) or {}).get("rows", []))
    limit = date.fromisoformat(cur[0]) - timedelta(days=1) if cur else date.today()
    d, end = date.fromisoformat(start), min(date.fromisoformat(end), limit)
    todo = []
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in rows:
            todo.append(d)
        d += timedelta(days=1)
    if not todo:
        print(f"{start[:4]}: nothing to fetch ({sum(1 for k in rows if k.startswith(start[:4]))} sessions already saved)")
        return
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=15)
    except requests.RequestException:
        pass
    added = blocked = 0
    for i, day in enumerate(todo, 1):
        try:
            r = s.get(URL.format(day.strftime("%d%m%Y")), timeout=20)
            if r.status_code == 200:
                rec = parse(r.text)
                if rec:
                    rows[day.isoformat()] = {"d": day.isoformat(), **rec}
                    added += 1
            elif r.status_code in (401, 403):
                blocked += 1
        except requests.RequestException:
            pass
        if blocked >= 20 and added == 0:
            sys.exit("NSE is blocking this machine.")
        if i % 60 == 0:
            print(f"   {start[:4]}: {i}/{len(todo)} days checked, {added} sessions added", flush=True)
        time.sleep(0.25)
    save("participant_oi_hist.json", {"rows": [rows[k] for k in sorted(rows)]})
    print(f"{start[:4]}: done, {added} sessions added ({len(rows)} total in history)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
