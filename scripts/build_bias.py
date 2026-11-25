"""Turn raw data into a transparent, rule-based bias per instrument and timeframe."""
import pandas as pd

from common import load, now_ist, save

TIMEFRAMES = ["Yearly", "Quarterly", "Monthly", "Weekly", "Daily"]
RESAMPLE = {"Yearly": "YE", "Quarterly": "QE", "Monthly": "ME", "Weekly": "W-FRI"}
COT_LOOKBACK = {"Yearly": "156", "Quarterly": "52", "Monthly": "26"}
DRIVERS = ["DXY", "UST10Y", "MSCIEM", "CRUDE", "NASDAQ"]
INSTRUMENTS = ["SENSEX", "NIFTY", "BANKNIFTY", "USDINR"]
HI, LO = 80, 20


def comp(name, signal, value, note, asof):
    return {"name": name, "signal": int(signal), "value": value, "note": note, "asof": asof}


def direction(delta, rng, thr=0.05):
    if rng <= 0 or abs(delta) < thr * rng:
        return 0
    return 1 if delta > 0 else -1


def range_pos(vals):
    lo, hi = min(vals), max(vals)
    return 50.0 if hi == lo else (vals[-1] - lo) / (hi - lo) * 100


def price_df(prices, key):
    s = (prices.get("series") or {}).get(key)
    if not s:
        return None
    df = pd.DataFrame(s["rows"])
    df["t"] = pd.to_datetime(df["t"])
    return df.set_index("t").sort_index()


def structure(df, tf):
    bars = df if tf == "Daily" else df.resample(RESAMPLE[tf]).agg(
        {"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    if len(bars) < 2:
        return None
    prev, cur = bars.iloc[-2], bars.iloc[-1]
    c, ph, pl = float(cur["c"]), float(prev["h"]), float(prev["l"])
    took_h, took_l = float(cur["h"]) > ph, float(cur["l"]) < pl
    zone = "premium" if c > (ph + pl) / 2 else "discount"
    p = tf.lower().replace("daily", "day").replace("ly", "")
    if c > ph:
        sig, note = 1, f"Closed above previous {p} high {ph:,.2f}"
    elif c < pl:
        sig, note = -1, f"Closed below previous {p} low {pl:,.2f}"
    elif took_h and not took_l:
        sig, note = -1, f"Swept previous {p} high {ph:,.2f} (buy-side) and closed back inside"
    elif took_l and not took_h:
        sig, note = 1, f"Swept previous {p} low {pl:,.2f} (sell-side) and closed back inside"
    else:
        sig, note = 0, f"Inside previous {p} range, in {zone}"
    c_ = comp(f"Price structure ({tf.lower()})", sig, round(c, 2), note,
              df.index[-1].strftime("%Y-%m-%d"))
    return c_, {"prev_high": ph, "prev_low": pl}


def pct_move(df, label, thr, sign):
    if df is None or len(df) < 2:
        return None
    ch = float((df["c"].iloc[-1] / df["c"].iloc[-2] - 1) * 100)
    raw = 0 if abs(ch) < thr else (1 if ch > 0 else -1)
    return comp(label, raw * sign, round(ch, 2), f"{ch:+.2f}% on the day",
                df.index[-1].strftime("%Y-%m-%d"))


def cot_extreme(cot, key, lb):
    m = cot["markets"].get(key)
    if not m or m["impact"] == 0:
        return None
    v = m["idx"][lb][-1]
    if v is None:
        return None
    raw = 1 if v >= HI else -1 if v <= LO else 0
    note = f"Commercials COT index {v:.0f}/100 over {lb} weeks"
    if raw:
        note += f", extreme {'long' if raw > 0 else 'short'}"
    return comp(f"{m['label']} COT ({lb}w)", raw * m["impact"], v, note, m["rows"][-1]["d"])


def cot_weekly(cot, key):
    m = cot["markets"].get(key)
    if not m or m["impact"] == 0 or len(m["rows"]) < 53:
        return None
    comm = [r["comm"] for r in m["rows"]]
    delta = comm[-1] - comm[-2]
    rng = max(comm[-52:]) - min(comm[-52:])
    note = f"Commercials net {delta:+,.0f} week on week ({delta / (rng or 1) * 100:+.0f}% of 52w range)"
    return comp(f"{m['label']} COT weekly change", direction(delta, rng) * m["impact"],
                delta, note, m["rows"][-1]["d"])


def poi_series(poi, who, kind):
    out = []
    for r in poi.get("rows", []):
        p = r.get(who)
        if not p:
            continue
        try:
            v = p["fil"] - p["fis"] if kind == "fut" else (p["icl"] - p["ics"]) - (p["ipl"] - p["ips"])
        except KeyError:
            continue
        out.append((r["d"], v))
    return out


def poi_extreme(s, label, lb=60, contrarian=False):
    if len(s) < lb:
        return None
    vals = [v for _, v in s[-lb:]]
    pos = range_pos(vals)
    raw = 1 if pos >= HI else -1 if pos <= LO else 0
    note = f"Net {vals[-1]:,.0f} contracts, at {pos:.0f}/100 of its {lb}-session range"
    if contrarian:
        raw, note = -raw, note + " (read contrarian)"
    return comp(label, raw, round(pos, 1), note, s[-1][0])


def poi_change(s, label, n, lb=60):
    if len(s) < max(lb, n + 1):
        return None
    vals = [v for _, v in s[-lb:]]
    delta = vals[-1] - vals[-1 - n]
    return comp(label, direction(delta, max(vals) - min(vals)), delta,
                f"{delta:+,.0f} contracts over {n} session(s)", s[-1][0])


def main():
    cot = load("cot.json", {}) or {}
    cot.setdefault("markets", {})
    poi = load("participant_oi.json", {}) or {}
    prices = load("prices.json", {}) or {}

    fii_fut = poi_series(poi, "FII", "fut")
    fii_opt = poi_series(poi, "FII", "opt")
    cli_fut = poi_series(poi, "Client", "fut")
    vix, inr = price_df(prices, "INDIAVIX"), price_df(prices, "USDINR")

    def drivers(tf):
        c = []
        if tf in COT_LOOKBACK:
            c += [cot_extreme(cot, k, COT_LOOKBACK[tf]) for k in DRIVERS]
        if tf == "Monthly":
            c += [poi_extreme(fii_fut, "FII index futures net (60 sessions)"),
                  poi_extreme(cli_fut, "Client index futures net (60 sessions)", contrarian=True)]
        if tf == "Weekly":
            c += [cot_weekly(cot, k) for k in DRIVERS]
            c += [poi_change(fii_fut, "FII index futures, 5-session change", 5),
                  poi_extreme(cli_fut, "Client index futures net (20 sessions)", lb=20, contrarian=True)]
        if tf == "Daily":
            c += [poi_change(fii_fut, "FII index futures, 1-session change", 1),
                  poi_change(fii_opt, "FII index options directional net, 1-session change", 1),
                  pct_move(vix, "India VIX", 5, -1),
                  pct_move(inr, "USDINR", 0.2, -1)]
        return [x for x in c if x]

    out = {"generated": now_ist(), "instruments": {}}
    for key in INSTRUMENTS:
        df = price_df(prices, key)
        inst = {"timeframes": {}, "levels": {}}
        for tf in TIMEFRAMES:
            comps = drivers(tf)
            if key == "USDINR":
                comps = [{**x, "signal": -x["signal"]} for x in comps if x["name"] != "USDINR"]
            ps = structure(df, tf) if df is not None else None
            if ps:
                comps.insert(0, ps[0])
                inst["levels"][tf] = ps[1]
            score, n = sum(x["signal"] for x in comps), len(comps)
            ratio = score / n if n else 0
            label = "Bullish" if ratio >= 0.3 else "Bearish" if ratio <= -0.3 else "Neutral"
            inst["timeframes"][tf] = {"label": label, "score": score, "n": n, "components": comps}
        out["instruments"][key] = inst
        print(f"{key:9}", " | ".join(f"{t}: {inst['timeframes'][t]['label']}" for t in TIMEFRAMES))
    save("bias.json", out)


if __name__ == "__main__":
    main()
