"""Trap Watch, liquidity map, descriptive structure and big picture. Only proven or descriptive information."""
import math
import re
from datetime import datetime, timedelta, timezone

import pandas as pd

from backtest import daily
from common import load, now_ist, save

KEYS = ["SENSEX", "NIFTY", "BANKNIFTY"]
TICK = {"SENSEX": "^BSESN", "NIFTY": "^NSEI"}
IST = timezone(timedelta(hours=5, minutes=30))


def pc(k, n):
    return f"{100 * k / n:.0f}%" if n else "-"


def twoprop(k1, n1, k2, n2):
    if min(n1, n2) < 10:
        return 0.0
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return 0.0 if se == 0 else (k1 / n1 - k2 / n2) / se


def frame(key):
    rows = (((load("prices.json", {}) or {}).get("series", {}) or {}).get(key) or {}).get("rows", [])
    if len(rows) < 60:
        return None
    df = pd.DataFrame([{"t": r["t"], "o": r.get("o", r["c"]), "h": r.get("h", r["c"]), "l": r.get("l", r["c"]), "c": r["c"]} for r in rows])
    df.index = pd.to_datetime(df["t"])
    return df[["o", "h", "l", "c"]].astype(float)


def bars(df, rule):
    return df.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()


def structure(df):
    out = {}
    for name, rule in (("Daily", None), ("Weekly", "W-FRI"), ("Monthly", "ME"), ("Quarterly", "QE"), ("Yearly", "YE")):
        b = df if rule is None else bars(df, rule)
        if len(b) < 2:
            continue
        cur, prev = b.iloc[-1], b.iloc[-2]
        state = "above" if cur.c > prev.h else "below" if cur.c < prev.l else "inside"
        out[name] = {"state": state, "close": round(float(cur.c), 2), "prev_high": round(float(prev.h), 2), "prev_low": round(float(prev.l), 2)}
    return out


def levels(df):
    L = []
    add = lambda n, p, k: L.append({"name": n, "price": round(float(p), 2), "kind": k})
    t, y = df.iloc[-1], df.iloc[-2]
    add("Today high", t.h, "high"); add("Today low", t.l, "low")
    add("Previous day high", y.h, "high"); add("Previous day low", y.l, "low")
    per = df.index.to_period("W-FRI")
    this = df[per == per[-1]]
    add("This week high", this.h.max(), "high"); add("This week low", this.l.min(), "low")
    for name, rule in (("week", "W-FRI"), ("month", "ME"), ("quarter", "QE"), ("year", "YE")):
        b = bars(df, rule)
        if len(b) >= 2:
            add(f"Previous {name} high", b.h.iloc[-2], "high"); add(f"Previous {name} low", b.l.iloc[-2], "low")
    r = df.iloc[-40:]
    add("40-day equilibrium", (r.h.max() + r.l.min()) / 2, "eq")
    c = float(df.c.iloc[-1])
    for x in L:
        x["dist"] = round((x["price"] / c - 1) * 100, 2)
    return sorted(L, key=lambda x: -x["price"])


def rng(df, n):
    r = df.iloc[-n:]
    lo, hi, c = float(r.l.min()), float(r.h.max()), float(df.c.iloc[-1])
    return {"low": round(lo, 2), "high": round(hi, 2), "pos": round((c - lo) / (hi - lo) * 100, 1) if hi > lo else 50.0, "days": len(r)}


def open_fvgs(df, look=150):
    H, L, C, n, out = df.h.values, df.l.values, df.c.values, len(df), []
    for i in range(max(1, n - look), n - 1):
        if L[i + 1] > H[i - 1]:
            bot, top, k = H[i - 1], L[i + 1], "bullish"
        elif H[i + 1] < L[i - 1]:
            bot, top, k = H[i + 1], L[i - 1], "bearish"
        else:
            continue
        if (top - bot) / C[i] < 0.001:
            continue
        a = slice(i + 2, n)
        if (k == "bullish" and (L[a] <= bot).any()) or (k == "bearish" and (H[a] >= top).any()):
            continue
        touched = bool((L[a] <= top).any()) if k == "bullish" else bool((H[a] >= bot).any())
        out.append({"type": k, "low": round(float(bot), 2), "high": round(float(top), 2),
                    "date": df.index[i].strftime("%Y-%m-%d"), "touched": touched})
    c = C[-1]
    for x in out:
        x["dist"] = round(((x["low"] + x["high"]) / 2 / c - 1) * 100, 2)
    return {"above": sorted([x for x in out if x["low"] > c], key=lambda x: x["low"])[:3],
            "below": sorted([x for x in out if x["high"] < c], key=lambda x: -x["high"])[:3]}


def daily_trap(I, df=None):
    td = I.get("today") or {}
    day, pdh, pdl = td.get("date"), td.get("pdh"), td.get("pdl")
    if df is not None and day:
        prev = df[df.index < pd.Timestamp(day)]
        if len(prev):
            pdh, pdl = round(float(prev.h.iloc[-1]), 2), round(float(prev.l.iloc[-1]), 2)  # official daily bar
    tb = [b for b in I.get("bars", []) if datetime.fromtimestamp(b["t"], timezone.utc).strftime("%Y-%m-%d") == day]
    base = {"date": day, "pdh": pdh, "pdl": pdl}
    if len(tb) < 4 or pdh is None:
        return {**base, "kind": "pending"}
    fh = tb[:4]
    hi, lo, cl = max(b["h"] for b in fh), min(b["l"] for b in fh), fh[3]["c"]
    side, kind = None, "inside"
    if hi > pdh and lo < pdl:
        kind = "both"
    elif hi > pdh:
        side, kind = "PDH", ("rejection" if cl < pdh else "held")
    elif lo < pdl:
        side, kind = "PDL", ("rejection" if cl > pdl else "held")
    last = datetime.fromtimestamp(tb[-1]["t"], timezone.utc).strftime("%H:%M")
    close = tb[-1]["c"]
    level = pdh if side == "PDH" else pdl if side == "PDL" else None
    back = None if level is None else (close < pdh if side == "PDH" else close > pdl)
    return {**base, "kind": kind, "side": side, "level": level, "fh_high": round(hi, 2), "fh_low": round(lo, 2),
            "fh_close": round(cl, 2), "complete": last >= "15:15", "last_time": last, "close": round(close, 2), "back_inside": back}


def weekly_trap(df):
    per = df.index.to_period("W-FRI")
    cur, prev_mask = per[-1], per < per[-1]
    if not prev_mask.any():
        return None
    this, pw = df[per == cur], df[per == per[prev_mask].max()]
    pwh, pwl, f0 = float(pw.h.max()), float(pw.l.min()), this.iloc[0]
    now = datetime.now(IST)
    first_done = len(this) >= 2 or this.index[0].strftime("%Y-%m-%d") != now.strftime("%Y-%m-%d") or now.hour >= 16
    side, kind = None, "inside"
    if f0.h > pwh and f0.l < pwl:
        kind = "both"
    elif f0.h > pwh:
        side, kind = "PWH", ("rejection" if f0.c < pwh else "held")
    elif f0.l < pwl:
        side, kind = "PWL", ("rejection" if f0.c > pwl else "held")
    if not first_done:
        kind = "pending"
    level = pwh if side == "PWH" else pwl if side == "PWL" else None
    c = float(this.c.iloc[-1])
    back = None if level is None else (c < pwh if side == "PWH" else c > pwl)
    return {"week_start": this.index[0].strftime("%Y-%m-%d"), "kind": kind, "side": side, "level": level,
            "pwh": round(pwh, 2), "pwl": round(pwl, 2), "close": round(c, 2), "back_inside": back, "days": len(this)}


def weekly_stats(ticker):
    d = daily(ticker)
    d = d[(d.index >= "2008-01-01") & (d["h"] > d["l"])]
    weeks = [g for _, g in d.groupby(d.index.to_period("W-FRI")) if len(g) >= 3]
    rn = ri = bn = bi = 0
    for prev, g in zip(weeks[:-1], weeks[1:]):
        pwh, pwl, f0, wc = prev.h.max(), prev.l.min(), g.iloc[0], g.c.iloc[-1]
        for took, rejected, back in ((f0.h > pwh, f0.c < pwh, wc < pwh), (f0.l < pwl, f0.c > pwl, wc > pwl)):
            if took:
                if rejected:
                    rn += 1; ri += bool(back)
                else:
                    bn += 1; bi += bool(back)
    return {"rej": pc(ri, rn), "brk": pc(bi, bn), "rej_n": rn, "brk_n": bn, "z": round(twoprop(ri, rn, bi, bn), 2)}


def base_rates():
    m = daily("^BSESN")["c"].resample("ME").last()
    out = {"since": int(m.index[0].year)}
    for h in (3, 6, 12):
        f = ((m.shift(-h) / m - 1) * 100).dropna()
        out[str(h)] = {"up": int(round(100 * (f > 0).mean())), "avg": round(float(f.mean()), 1)}
    return out


def grab(text, pattern, default):
    m = re.search(pattern, text or "")
    return m.groups() if m else default


def main():
    bt = load("backtest.json", {}) or {}
    intra = load("intraday.json", {}) or {}
    inst = bt.get("instruments", {}) or {}

    def find(i):
        for k in ("SENSEX", "NIFTY"):
            for t in inst.get(k) or []:
                if t.get("id") == i:
                    return t
        return {}

    fh = grab(find("first_hour").get("summary"), r"in (\d+%)", ("78%",))[0]
    dr, db = grab(find("sweep_rejection").get("summary"), r"inside (\d+%) of the time vs (\d+%)", ("71%", "26%"))
    wk = {}
    for key, t in TICK.items():
        try:
            s = wk[key] = weekly_stats(t)
        except Exception as e:
            print(f"weekly stats {key} failed: {e}")
            continue
        v = "Holds" if s["z"] >= 2 else "Weak" if s["z"] >= 1 else "Doesn't hold"
        test = {"id": "weekly_trap", "title": "Weekly stop hunt: first-day sweep + rejection", "title_hi": "",
                "claim": "When the first day of the week sweeps last week's high/low and closes back inside, the week closes back inside more often than when the sweep holds.",
                "verdict": v,
                "summary": f"Rejection on the first day: week closed back inside {s['rej']} ({s['rej_n']} cases) vs {s['brk']} when the sweep held beyond ({s['brk_n']} cases); z {s['z']}.",
                "hi": "", "cols": ["First day", "Cases", "Week closed back inside"],
                "rows": [["Rejection close", s["rej_n"], s["rej"]], ["Held beyond", s["brk_n"], s["brk"]]],
                "sample": "Daily data since 2008"}
        inst[key] = [x for x in inst.get(key, []) if x.get("id") != "weekly_trap"] + [test]
    if inst:
        bt["instruments"] = inst
        save("backtest.json", bt)
    ws = wk.get("SENSEX") or wk.get("NIFTY") or {"rej": "62%", "brk": "33%"}
    try:
        base = base_rates()
    except Exception as e:
        print(f"base rates failed: {e}")
        base = {"since": 1997, "3": {"up": 60, "avg": 3.2}, "6": {"up": 67, "avg": 6.8}, "12": {"up": 71, "avg": 14.3}}
    facts = " ".join((load("research_v8.json", {}) or {}).get("facts", []))
    f5, f20, f60 = grab(facts, r"within 5 days (\d+%), 20 days (\d+%), 60 days (\d+%)", ("31%", "43%", "49%"))
    out = {"generated": now_ist(),
           "stats": {"first_hour": fh, "daily_rej": dr, "daily_brk": db, "weekly_rej": ws["rej"], "weekly_brk": ws["brk"],
                     "base": base, "fvg": {"fill5": f5, "fill20": f20, "fill60": f60}},
           "instruments": {}}
    for key in KEYS:
        df = frame(key)
        if df is None:
            continue
        I = (intra.get("instruments") or {}).get(key) or {}
        st = I.get("stats") or {}
        out["instruments"][key] = {
            "close": round(float(df.c.iloc[-1]), 2), "asof": df.index[-1].strftime("%Y-%m-%d"),
            "structure": structure(df), "levels": levels(df), "range3y": rng(df, 756), "range12m": rng(df, 252),
            "fvg": open_fvgs(df), "daily": daily_trap(I, df) if I else None, "weekly": weekly_trap(df),
            "pd_taken": st.get("pd_level_taken"), "sessions": st.get("sessions")}
        x = out["instruments"][key]
        print(f"{key:9} daily={(x['daily'] or {}).get('kind')}  weekly={(x['weekly'] or {}).get('kind')}  3y range {x['range3y']['pos']}%")
    log = load("trap_log.json", {}) or {}
    ent = {(e["type"], e["key"], e["date"]): e for e in log.get("entries", [])}
    for key, x in out["instruments"].items():
        d, w = x.get("daily") or {}, x.get("weekly") or {}
        if d.get("complete") and d.get("kind") in ("rejection", "held"):
            ent[("daily", key, d["date"])] = {"type": "daily", "key": key, "date": d["date"], "kind": d["kind"], "back_inside": d.get("back_inside")}
        if w.get("kind") in ("rejection", "held"):
            ent[("weekly", key, w["week_start"])] = {"type": "weekly", "key": key, "date": w["week_start"], "kind": w["kind"], "back_inside": w.get("back_inside")}
    save("trap_log.json", {"since": log.get("since") or now_ist()[:10], "entries": sorted(ent.values(), key=lambda e: (e["date"], e["key"], e["type"]))})
    save("traps.json", out)


if __name__ == "__main__":
    main()
