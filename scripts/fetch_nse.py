"""Daily NSE participant-wise OI (FII / DII / Client / Pro), stored incrementally."""
import io
import sys
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from common import IST, load, now_ist, save

URL = "https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{}.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/csv,text/plain,*/*",
    "Referer": "https://www.nseindia.com/",
}
FIELDS = {
    "futureindexlong": "fil", "futureindexshort": "fis",
    "futurestocklong": "fsl", "futurestockshort": "fss",
    "optionindexcalllong": "icl", "optionindexputlong": "ipl",
    "optionindexcallshort": "ics", "optionindexputshort": "ips",
    "totallongcontracts": "tl", "totalshortcontracts": "ts",
}


def norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def parse(text):
    lines = text.strip().splitlines()
    start = next((i for i, l in enumerate(lines) if "client type" in l.lower()), None)
    if start is None:
        return None
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    cols = {c: norm(c) for c in df.columns}
    rec = {}
    for _, row in df.iterrows():
        who = str(row[df.columns[0]]).strip()
        if who.upper() == "TOTAL" or who.lower() == "nan":
            continue
        rec[who] = {FIELDS[n]: float(str(row[c]).replace(",", ""))
                    for c, n in cols.items() if n in FIELDS}
    return rec or None


def main(backfill_days=420):
    hist = load("participant_oi.json", {}) or {}
    rows = {r["d"]: r for r in hist.get("rows", [])}
    today = datetime.now(IST).date()
    if rows:
        start = max(date.fromisoformat(d) for d in rows) + timedelta(days=1)
    else:
        start = today - timedelta(days=backfill_days)

    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.nseindia.com", timeout=15)
    except requests.RequestException:
        pass

    added = blocked = 0
    d = start
    while d <= today:
        if d.weekday() < 5:
            try:
                r = s.get(URL.format(d.strftime("%d%m%Y")), timeout=20)
                if r.status_code == 200:
                    rec = parse(r.text)
                    if rec:
                        rows[d.isoformat()] = {"d": d.isoformat(), **rec}
                        added += 1
                elif r.status_code in (401, 403):
                    blocked += 1
            except requests.RequestException as e:
                print("error", d, e)
                blocked += 1
            if blocked >= 5 and added == 0:
                sys.exit("NSE is blocking this machine.")
            time.sleep(0.4)
        d += timedelta(days=1)

    ordered = [rows[k] for k in sorted(rows)]
    save("participant_oi.json", {"updated": now_ist(), "rows": ordered})
    last = ordered[-1]["d"] if ordered else "none"
    print(f"added {added} sessions, total {len(ordered)}, latest {last}")


if __name__ == "__main__":
    main()
