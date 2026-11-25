"""Weekly CFTC Legacy COT (futures only) for the global drivers of Indian markets."""
from datetime import date, timedelta

import requests

from common import now_ist, range_index, save

URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# impact = how a BULLISH reading in this market tends to affect Indian equities
MARKETS = {
    "DXY":    {"code": "098662", "label": "US Dollar Index",       "impact": -1},
    "UST10Y": {"code": "043602", "label": "US 10Y T-Note",         "impact": +1},
    "MSCIEM": {"code": "244042", "label": "MSCI Emerging Markets", "impact": +1},
    "NASDAQ": {"code": "209742", "label": "Nasdaq-100 Mini",       "impact": +1},
    "SP500":  {"code": "13874A", "label": "E-mini S&P 500",        "impact": +1},
    "CRUDE":  {"code": "067651", "label": "WTI Crude Oil",         "impact": -1},
    "GOLD":   {"code": "088691", "label": "Gold",                  "impact": 0},
}
LOOKBACKS = (26, 52, 156)


def num(row, key):
    return float(row.get(key) or 0)


def fetch(code, start):
    params = {
        "$where": f"cftc_contract_market_code='{code}' AND report_date_as_yyyy_mm_dd >= '{start}'",
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": 5000,
    }
    r = requests.get(URL, params=params, timeout=60,
                     headers={"User-Agent": "india-bias-dashboard"})
    r.raise_for_status()
    return r.json()


def main():
    start = (date.today() - timedelta(weeks=212)).isoformat()
    out = {"updated": now_ist(), "markets": {}}
    missing = []
    for key, m in MARKETS.items():
        try:
            rows = fetch(m["code"], start)
        except Exception as e:
            print(f"{key}: request failed ({e})")
            rows = []
        if not rows:
            missing.append(key)
            continue
        recs = [{
            "d": r["report_date_as_yyyy_mm_dd"][:10],
            "oi": num(r, "open_interest_all"),
            "comm": num(r, "comm_positions_long_all") - num(r, "comm_positions_short_all"),
            "ls": num(r, "noncomm_positions_long_all") - num(r, "noncomm_positions_short_all"),
            "ss": num(r, "nonrept_positions_long_all") - num(r, "nonrept_positions_short_all"),
        } for r in rows]
        comm = [x["comm"] for x in recs]
        out["markets"][key] = {
            **m,
            "market_name": rows[-1].get("market_and_exchange_names", ""),
            "rows": recs,
            "idx": {str(n): range_index(comm, n) for n in LOOKBACKS},
        }
        print(f"{key:7} {recs[-1]['d']}  {out['markets'][key]['market_name']}  "
              f"commercials net = {comm[-1]:,.0f}")
    if out["markets"]:
        save("cot.json", out)
    if missing:
        print("WARNING: no rows for", missing, "- contract code may need fixing")


if __name__ == "__main__":
    main()
