"""Does smart-money positioning predict index returns?  FII participant OI (2012+) and CFTC COT extremes (2010+)."""
import math

import pandas as pd
import requests

from backtest import daily
from common import load, save

INDEX = {"SENSEX": "^BSESN", "NIFTY": "^NSEI"}
COT_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
COT_MKTS = {"DXY": ("098662", "US Dollar Index", -1), "UST10Y": ("043602", "US 10Y T-Note", 1),
            "MSCIEM": ("244042", "MSCI Emerging Markets", 1), "CRUDE": ("067651", "WTI Crude Oil", -1)}
_cot = {}


def verdict(z):
    return "Holds" if z >= 2 else "Weak" if z >= 1 else "Doesn't hold"


def grp_test(tid, title, claim, a, b, la, lb, horizon, note):
    a, b = pd.Series(a, dtype=float).dropna(), pd.Series(b, dtype=float).dropna()
    row = lambda name, s: [name, len(s), f"{s.mean():+.2f}%" if len(s) else "-", f"{100 * (s > 0).mean():.0f}%" if len(s) else "-"]
    if len(a) < 8 or len(b) < 8:
        z, v, summ = 0.0, "Doesn't hold", f"Not enough cases yet ({len(a)} vs {len(b)})."
    else:
        se = math.sqrt(a.var() / len(a) + b.var() / len(b))
        diff = a.mean() - b.mean()
        z = diff / se if se > 0 else 0.0
        v = verdict(z)
        summ = f"Next {horizon}: {la} {a.mean():+.2f}% vs {lb} {b.mean():+.2f}% (difference {diff:+.2f}%, z {z:+.1f})."
        if z <= -2:
            summ += " The opposite relationship is significant."
    return {"id": tid, "title": title, "title_hi": "", "claim": claim, "verdict": v, "summary": summ, "hi": "",
            "cols": ["Group", "Cases", "Avg return", "% positive"], "rows": [row(la, a), row(lb, b)], "sample": note}


def fii_frame():
    rows = (load("participant_oi_hist.json", {}) or {}).get("rows", []) + (load("participant_oi.json", {}) or {}).get("rows", [])
    rec = {r["d"]: {"fii": r["FII"]["fil"] - r["FII"]["fis"], "cli": r["Client"]["fil"] - r["Client"]["fis"]}
           for r in rows if r.get("FII") and r.get("Client") and "fil" in r["FII"] and "fil" in r["Client"]}
    df = pd.DataFrame.from_dict(rec, orient="index")
    if df.empty:
        return df
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def fii_tests(c, f):
    d = f.join(c.rename("c"), how="inner")
    d["f5"], d["c5"], d["f20"], d["c20"] = d["fii"].diff(5), d["cli"].diff(5), d["fii"].diff(20), d["cli"].diff(20)
    lo, hi = d["fii"].rolling(60).min(), d["fii"].rolling(60).max()
    d["pos"] = (d["fii"] - lo) / (hi - lo) * 100
    d["r5"], d["r20"] = (d["c"].shift(-5) / d["c"] - 1) * 100, (d["c"].shift(-20) / d["c"] - 1) * 100
    span = f"{d.index[0]:%Y}-{d.index[-1]:%Y}"
    out = []
    s5 = d.dropna(subset=["f5", "c5", "r5"]).iloc[::5]
    s20 = d.dropna(subset=["f20", "c20", "pos", "r20"]).iloc[::20]
    q = lambda s, col: (s[col].quantile(0.8), s[col].quantile(0.2))
    h5, l5 = q(s5, "f5")
    out.append(grp_test("pos_fii5", "FII buying over 5 days leads the next 5 days",
                        "When FIIs add the most index-futures longs (or cover the most shorts) over 5 days, the index does better over the next 5 days than when they sell the most.",
                        s5.loc[s5.f5 >= h5, "r5"], s5.loc[s5.f5 <= l5, "r5"], "after strongest FII buying", "after strongest FII selling", "5 days",
                        f"FII participant OI {span}, non-overlapping 5-day samples, top vs bottom fifth"))
    h20, l20 = q(s20, "f20")
    out.append(grp_test("pos_fii20", "FII buying over 20 days leads the next 20 days",
                        "When FIIs buy the most over 20 days, the index does better over the next 20 days than when they sell the most.",
                        s20.loc[s20.f20 >= h20, "r20"], s20.loc[s20.f20 <= l20, "r20"], "after strongest FII buying", "after strongest FII selling", "20 days",
                        f"FII participant OI {span}, non-overlapping 20-day samples, top vs bottom fifth"))
    out.append(grp_test("pos_fii_extreme", "FII positioning at a 60-day high vs low",
                        "When FII index-futures positioning sits at the top of its 60-day range, the index does better over the next 20 days than when it sits at the bottom.",
                        s20.loc[s20.pos >= 80, "r20"], s20.loc[s20.pos <= 20, "r20"], "FII at 60-day high (>=80)", "FII at 60-day low (<=20)", "20 days",
                        f"FII participant OI {span}, non-overlapping 20-day samples"))
    hc, lc = q(s5, "c5")
    out.append(grp_test("pos_retail", "Retail selling is bullish (contrarian)",
                        "When retail (Client) sells the most index futures over 5 days, the index does better over the next 5 days than when retail buys the most.",
                        s5.loc[s5.c5 <= lc, "r5"], s5.loc[s5.c5 >= hc, "r5"], "after strongest retail selling", "after strongest retail buying", "5 days",
                        f"Client participant OI {span}, non-overlapping 5-day samples, bottom vs top fifth"))
    good = s20.loc[(s20.f20 > 0) & (s20.c20 < 0), "r20"]
    bad = s20.loc[(s20.f20 < 0) & (s20.c20 > 0), "r20"]
    out.append(grp_test("pos_divergence", "FII buying while retail sells ('healthy rally')",
                        "When FIIs buy while retail sells over 20 days, the index does better over the next 20 days than when FIIs sell while retail buys.",
                        good, bad, "FII buy + retail sell", "FII sell + retail buy", "20 days",
                        f"Participant OI {span}, non-overlapping 20-day samples"))
    return out


def cot_index(code):
    if code in _cot:
        return _cot[code]
    r = requests.get(COT_URL, params={"$where": f"cftc_contract_market_code='{code}' AND report_date_as_yyyy_mm_dd >= '2009-01-01'",
                                      "$order": "report_date_as_yyyy_mm_dd ASC", "$limit": 5000},
                     timeout=60, headers={"User-Agent": "india-bias-dashboard"})
    r.raise_for_status()
    s = pd.Series({pd.Timestamp(x["report_date_as_yyyy_mm_dd"][:10]):
                   float(x.get("comm_positions_long_all") or 0) - float(x.get("comm_positions_short_all") or 0) for x in r.json()}).sort_index()
    lo, hi = s.rolling(52).min(), s.rolling(52).max()
    _cot[code] = ((s - lo) / (hi - lo) * 100).dropna()
    return _cot[code]


def fwd_after(c, dates, h):
    idx, vals, out = c.index, c.values, {}
    for d in dates:
        p = idx.searchsorted(d + pd.Timedelta(days=3))
        if p + h < len(vals):
            out[d] = (vals[p + h] / vals[p] - 1) * 100
    return pd.Series(out, dtype=float)


def cot_tests(c):
    out, comp = [], None
    for key, (code, label, impact) in COT_MKTS.items():
        try:
            ix = cot_index(code)
        except Exception as e:
            print(f"COT {key} failed: {e}")
            continue
        m = pd.DataFrame({"idx": ix, "r": fwd_after(c, ix.index, 65)}).dropna().iloc[::13]
        fav = m.loc[(m.idx >= 80) if impact > 0 else (m.idx <= 20), "r"]
        unf = m.loc[(m.idx <= 20) if impact > 0 else (m.idx >= 80), "r"]
        out.append(grp_test(f"pos_cot_{key.lower()}", f"COT extreme in {label} → next 13 weeks",
                            f"When {label} hedgers sit at an extreme that favours India, the index does better over the next 13 weeks than at the opposite extreme.",
                            fav, unf, "favourable extreme", "unfavourable extreme", "13 weeks",
                            f"CFTC commercials, 52-week COT index, non-overlapping quarterly samples since {m.index[0]:%Y}" if len(m) else "CFTC"))
        sc = ((ix >= 80).astype(int) - (ix <= 20).astype(int)) * impact
        comp = sc if comp is None else comp.add(sc, fill_value=0)
    if comp is not None:
        m = pd.DataFrame({"s": comp, "r": fwd_after(c, comp.index, 65)}).dropna().iloc[::13]
        out.append(grp_test("pos_cot_composite", "Global hedger backdrop → next 13 weeks",
                            "When the combined COT backdrop (Dollar, US 10Y, MSCI EM, Crude extremes, impact-adjusted) favours India, the index does better over the next 13 weeks than when it is hostile.",
                            m.loc[m.s >= 1, "r"], m.loc[m.s <= -1, "r"], "supportive backdrop", "hostile backdrop", "13 weeks",
                            "CFTC commercials, non-overlapping quarterly samples"))
    return out


def main():
    bt = load("backtest.json", {}) or {}
    inst = bt.get("instruments", {})
    f = fii_frame()
    print(f"FII history: {len(f)} sessions" + (f" ({f.index[0]:%Y-%m-%d} to {f.index[-1]:%Y-%m-%d})" if len(f) else ""))
    for key, t in INDEX.items():
        try:
            c = daily(t)["c"]
        except Exception as e:
            print(f"{key}: price history failed ({e})")
            continue
        new = (fii_tests(c, f) if len(f) > 300 else []) + cot_tests(c)
        inst[key] = [x for x in inst.get(key, []) if not x["id"].startswith("pos_")] + new
        for x in new:
            print(f"{key:7} {x['verdict']:13} {x['title']}: {x['summary']}")
    bt["instruments"] = inst
    save("backtest.json", bt)


if __name__ == "__main__":
    main()
