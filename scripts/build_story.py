"""Plain-English market story: where price is coming from, what it is doing, what is next."""
import pandas as pd

from build_bias import poi_series, price_df
from common import load, now_ist, save

EQUITIES = {"SENSEX": "Sensex", "NIFTY": "Nifty", "BANKNIFTY": "Bank Nifty"}
WEIGHTS = {"Yearly": 1, "Quarterly": 1.5, "Monthly": 2, "Weekly": 2, "Daily": 1}
WHAT = {
    "DXY": "a stronger US dollar",
    "UST10Y": "higher bond prices (falling US yields)",
    "MSCIEM": "rising emerging-market stocks",
    "NASDAQ": "rising US tech stocks",
    "SP500": "rising US stocks",
    "CRUDE": "higher crude oil",
    "GOLD": "higher gold",
}


def macro(cot):
    lines, neutral, score = [], [], 0
    for k, m in cot.get("markets", {}).items():
        v = m["idx"]["52"][-1]
        if v is None:
            continue
        if 20 < v < 80:
            neutral.append(m["label"])
            continue
        lean = 1 if v >= 80 else -1
        effect = lean * m["impact"]
        score += effect
        verb = "favours" if lean > 0 else "leans against"
        side = "bullish" if lean > 0 else "bearish"
        india = "good for Indian equities" if effect > 0 else "a headwind for Indian equities" if effect < 0 else "context only"
        lines.append(f"{m['label']}: hedgers near their most {side} in a year ({v:.0f}/100), "
                     f"which {verb} {WHAT.get(k, m['label'])} - {india}.")
    summary, tone = ("Supportive", "bull") if score >= 2 else ("Hostile", "bear") if score <= -2 else ("Mixed", "neutral")
    return {"summary": summary, "tone": tone, "lines": lines, "neutral": neutral}


def swing(df):
    win = df.iloc[-250:]
    hi_d, lo_d = win["h"].idxmax(), win["l"].idxmin()
    hi, lo, c = float(win["h"].max()), float(win["l"].min()), float(df["c"].iloc[-1])
    out = []
    if lo_d > hi_d:
        recent = "low"
        n = len(win.loc[lo_d:]) - 1
        out.append(f"Fell {(1 - lo / hi) * 100:.1f}% from its 1-year high {hi:,.0f} ({hi_d:%d %b %Y}) "
                   f"to the low {lo:,.0f} ({lo_d:%d %b %Y}).")
        prior = win[(win.index > hi_d) & (win.index < lo_d - pd.Timedelta(days=30))]
        if len(prior):
            pl, pdate = float(prior["l"].min()), prior["l"].idxmin()
            if lo < pl and (pl - lo) / pl < 0.03:
                out.append(f"That low ran just below the earlier low of {pl:,.0f} ({pdate:%b %Y}) - "
                           f"a sell-side liquidity sweep before the turn.")
        out.append(f"Since the low it has moved {(c / lo - 1) * 100:+.1f}% in {n} sessions.")
    else:
        recent = "high"
        n = len(win.loc[hi_d:]) - 1
        out.append(f"Rallied {(hi / lo - 1) * 100:.1f}% from its 1-year low {lo:,.0f} ({lo_d:%d %b %Y}) "
                   f"to the high {hi:,.0f} ({hi_d:%d %b %Y}).")
        prior = win[(win.index > lo_d) & (win.index < hi_d - pd.Timedelta(days=30))]
        if len(prior):
            ph, pdate = float(prior["h"].max()), prior["h"].idxmax()
            if hi > ph and (hi - ph) / ph < 0.03:
                out.append(f"That high ran just above the earlier high of {ph:,.0f} ({pdate:%b %Y}) - "
                           f"a buy-side liquidity sweep.")
        out.append(f"Since the high it has moved {(c / hi - 1) * 100:+.1f}% in {n} sessions.")
    pos = 50.0 if hi == lo else (c - lo) / (hi - lo) * 100
    return out, {"hi": hi, "lo": lo, "close": c, "pos": pos, "recent": recent}


def doing(df, sw, levels, poi):
    c, out = sw["close"], []
    ch20 = (c / float(df["c"].iloc[-21]) - 1) * 100 if len(df) > 21 else 0.0
    zone = "premium (upper half)" if sw["pos"] > 50 else "discount (lower half)"
    out.append(f"Last close {c:,.2f}: {ch20:+.1f}% over 20 sessions, in the {zone} "
               f"of its 1-year range ({sw['pos']:.0f}%).")
    w = levels.get("Weekly")
    if w:
        if c > w["prev_high"]:
            out.append(f"Closed above last week's high {w['prev_high']:,.0f} - buyers in control this week.")
        elif c < w["prev_low"]:
            out.append(f"Closed below last week's low {w['prev_low']:,.0f} - sellers in control this week.")
        else:
            out.append(f"Inside last week's range {w['prev_low']:,.0f} - {w['prev_high']:,.0f}: no weekly break yet.")
    fii = poi_series(poi, "FII", "fut")
    if len(fii) > 20:
        now, d20 = fii[-1][1], fii[-1][1] - fii[-21][1]
        if now < 0:
            act = "covering shorts" if d20 > 0 else "adding shorts"
        else:
            act = "adding longs" if d20 > 0 else "cutting longs"
        out.append(f"FIIs are net {'short' if now < 0 else 'long'} {abs(now):,.0f} index-futures contracts "
                   f"and have been {act} ({d20:+,.0f} in 20 sessions).")
    cli = poi_series(poi, "Client", "fut")
    if len(cli) > 20:
        now, d20 = cli[-1][1], cli[-1][1] - cli[-21][1]
        out.append(f"Retail (Client) is net {'long' if now > 0 else 'short'} {abs(now):,.0f} contracts "
                   f"({d20:+,.0f} in 20 sessions) - read contrarian.")
    return out


def stance(tfs):
    tot = sum(WEIGHTS[t] * (v["score"] / v["n"] if v["n"] else 0) for t, v in tfs.items())
    w = tot / sum(WEIGHTS.values())
    label = "Leaning Bullish" if w >= 0.2 else "Leaning Bearish" if w <= -0.2 else "Two-sided"
    return label, round(w, 2)


def nxt(verdict, sw, levels, tfs):
    c, out = sw["close"], []
    w = levels.get("Weekly", {})
    if "Bullish" in verdict:
        if sw["hi"] > c * 1.001:
            out.append(f"Draw on liquidity: buy-side resting above the 1-year high {sw['hi']:,.0f} "
                       f"({(sw['hi'] / c - 1) * 100:+.1f}% away).")
        else:
            out.append("Price is at fresh 1-year highs - no obvious buy-side pool above; manage risk on extensions.")
        if w:
            mid = (w["prev_high"] + w["prev_low"]) / 2
            out.append(f"Better longs come on pullbacks below {mid:,.0f} (discount of last week's range) after a sell-side sweep.")
            out.append(f"The bullish case weakens on a daily close below last week's low {w['prev_low']:,.0f}.")
    elif "Bearish" in verdict:
        if sw["lo"] < c * 0.999:
            out.append(f"Draw on liquidity: sell-side resting below the 1-year low {sw['lo']:,.0f} "
                       f"({(sw['lo'] / c - 1) * 100:+.1f}% away).")
        else:
            out.append("Price is at fresh 1-year lows - no obvious sell-side pool below; manage risk on extensions.")
        if w:
            mid = (w["prev_high"] + w["prev_low"]) / 2
            out.append(f"Better shorts come on rallies above {mid:,.0f} (premium of last week's range) after a buy-side sweep.")
            out.append(f"The bearish case weakens on a daily close above last week's high {w['prev_high']:,.0f}.")
    else:
        if w:
            out.append(f"No clear edge. Range to watch: {w['prev_low']:,.0f} - {w['prev_high']:,.0f}. "
                       f"Wait for a sweep of one side and a close back inside.")
    d = tfs.get("Daily")
    if d:
        out.append(f"Daily context: {d['label']} ({d['score']:+d}/{d['n']}) - use for session timing only.")
    return out


def risks(verdict, tfs):
    sign = 1 if "Bull" in verdict else -1 if "Bear" in verdict else 0
    if not sign:
        return []
    seen, out = set(), []
    for t in ("Monthly", "Weekly", "Quarterly"):
        for c in tfs.get(t, {}).get("components", []):
            if c["signal"] == -sign and c["name"] not in seen:
                seen.add(c["name"])
                out.append(f"{c['name']}: {c['note']}")
    return out[:4]


def level_list(levels, sw):
    tags = {"Daily": "day", "Weekly": "week", "Monthly": "month", "Quarterly": "quarter", "Yearly": "year"}
    out = []
    for tf, t in tags.items():
        L = levels.get(tf)
        if L:
            out += [{"name": f"Prev {t} high", "price": L["prev_high"]},
                    {"name": f"Prev {t} low", "price": L["prev_low"]}]
    out += [{"name": "1-year high", "price": sw["hi"]}, {"name": "1-year low", "price": sw["lo"]}]
    for x in out:
        x["dist"] = round((x["price"] / sw["close"] - 1) * 100, 2)
        x["price"] = round(x["price"], 2)
    return sorted(out, key=lambda x: -x["price"])


def main():
    bias = load("bias.json", {}) or {}
    prices = load("prices.json", {}) or {}
    poi = load("participant_oi.json", {}) or {}
    cot = load("cot.json", {}) or {}
    old = load("story.json", {}) or {}
    out = {"generated": now_ist(), "macro": macro(cot), "instruments": {}, "ai": old.get("ai", {})}
    for key, name in EQUITIES.items():
        df = price_df(prices, key)
        inst = bias.get("instruments", {}).get(key)
        if df is None or not inst or len(df) < 60:
            continue
        tfs, levels = inst["timeframes"], inst.get("levels", {})
        came, sw = swing(df)
        verdict, w = stance(tfs)
        groups = {}
        for t, v in tfs.items():
            groups.setdefault(v["label"], []).append(t)
        headline = f"{name} is {verdict.lower()}. " + " · ".join(
            f"{lab}: {', '.join(ts)}" for lab, ts in groups.items())
        out["instruments"][key] = {
            "name": name, "verdict": verdict, "weight": w, "headline": headline,
            "close": round(sw["close"], 2), "asof": df.index[-1].strftime("%d %b %Y"),
            "coming_from": came, "doing": doing(df, sw, levels, poi),
            "next": nxt(verdict, sw, levels, tfs), "risks": risks(verdict, tfs),
            "levels": level_list(levels, sw),
        }
        print(f"{key:9} {verdict} ({w:+.2f})")
    save("story.json", out)


if __name__ == "__main__":
    main()
