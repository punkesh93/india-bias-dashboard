"""Intraday ICT engine (15-minute): sessions, kill zones, Judas swing, PDH/PDL raids, MSS + FVG setups."""
import pandas as pd
import yfinance as yf

from common import load, now_ist, save

TICKERS = {"SENSEX": "^BSESN", "NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
ZONES = [("Open kill zone", "09:15", "10:30"), ("Midday lull", "10:30", "13:00"),
         ("London overlap", "13:00", "14:30"), ("Close kill zone", "14:30", "15:30")]
ZONES_HI = {"Open kill zone": "subah ka kill zone", "Midday lull": "dopahar ka sust samay",
            "London overlap": "London overlap", "Close kill zone": "closing kill zone"}
SB = [("09:30", "10:30"), ("13:30", "14:30")]


def fetch(ticker, key=None):
    df = yf.Ticker(ticker).history(period="60d", interval="15m", auto_adjust=False)
    if df is None or df.empty:
        return None
    idx = df.index
    df.index = idx.tz_convert("Asia/Kolkata") if idx.tz is not None else idx.tz_localize("UTC").tz_convert("Asia/Kolkata")
    df = df[["Open", "High", "Low", "Close"]].dropna()
    df.columns = ["o", "h", "l", "c"]
    df = df.between_time("09:15", "15:29")
    if key:
        try:
            import archive_intraday
            df = archive_intraday.merge(key, df)
        except Exception as e:
            print("archive merge skipped:", e)
    return df


def zone(ts):
    hm = ts.strftime("%H:%M")
    for name, a, b in ZONES:
        if a <= hm < b:
            return name
    return ZONES[-1][0]


def in_sb(ts):
    hm = ts.strftime("%H:%M")
    return any(a <= hm < b for a, b in SB)


def f0(x):
    return f"{x:,.0f}"


def analyse_day(g, prev):
    o, h, l, c = float(g["o"].iloc[0]), float(g["h"].max()), float(g["l"].min()), float(g["c"].iloc[-1])
    th, tl = g["h"].idxmax(), g["l"].idxmin()
    pdh, pdl = float(prev["h"].max()), float(prev["l"].min())
    rng = (h - l) or 1
    bull = c >= o
    judas = None
    if bull and tl < th and zone(tl) == "Open kill zone" and (o - l) / rng >= 0.25:
        judas = "bullish"
    elif not bull and th < tl and zone(th) == "Open kill zone" and (h - o) / rng >= 0.25:
        judas = "bearish"

    def status(side):
        lvl = pdh if side == "high" else pdl
        took = h > lvl if side == "high" else l < lvl
        if not took:
            return "untouched"
        beyond = c > lvl if side == "high" else c < lvl
        return "closed beyond" if beyond else "raided, closed back inside"

    return {"date": g.index[0].strftime("%Y-%m-%d"), "open": round(o, 2), "high": round(h, 2), "low": round(l, 2),
            "close": round(c, 2), "high_time": th.strftime("%H:%M"), "high_zone": zone(th),
            "low_time": tl.strftime("%H:%M"), "low_zone": zone(tl), "direction": "bullish" if bull else "bearish",
            "pdh": round(pdh, 2), "pdl": round(pdl, 2), "pdh_status": status("high"), "pdl_status": status("low"),
            "judas": judas, "_open_kz": zone(th) == "Open kill zone" or zone(tl) == "Open kill zone"}


def narrate(d):
    st = {"untouched": ("not reached", "touch nahi hua"),
          "closed beyond": ("taken and closed beyond", "toda aur uske paar band hua"),
          "raided, closed back inside": ("raided, then price closed back inside (stop hunt)", "toda gaya par price wapas andar band hua (stop hunt)")}
    up = d["direction"] == "bullish"
    en = [f"Opened {f0(d['open'])}, closed {f0(d['close'])} ({'up' if up else 'down'} day).",
          f"High {f0(d['high'])} at {d['high_time']} ({d['high_zone']}); low {f0(d['low'])} at {d['low_time']} ({d['low_zone']}).",
          f"Previous-day high {f0(d['pdh'])}: {st[d['pdh_status']][0]}. Previous-day low {f0(d['pdl'])}: {st[d['pdl_status']][0]}."]
    hi = [f"{f0(d['open'])} pe khula, {f0(d['close'])} pe band hua — {'tezi' if up else 'mandi'} wala din.",
          f"Din ka high {f0(d['high'])} ({d['high_time']}, {ZONES_HI[d['high_zone']]}), low {f0(d['low'])} ({d['low_time']}, {ZONES_HI[d['low_zone']]}).",
          f"Kal ka high {f0(d['pdh'])}: {st[d['pdh_status']][1]}. Kal ka low {f0(d['pdl'])}: {st[d['pdl_status']][1]}."]
    if d["judas"] == "bullish":
        en.append("Judas swing: the morning dip in the open kill zone was the manipulation leg; the real move was up.")
        hi.append("Judas swing: subah ki girawat nakli thi (stop-loss saaf karne ke liye), asli move upar ka tha.")
    elif d["judas"] == "bearish":
        en.append("Judas swing: the morning rally in the open kill zone was the manipulation leg; the real move was down.")
        hi.append("Judas swing: subah ki tezi nakli thi, asli move neeche ka tha.")
    return en, hi


def find_setups(df, days):
    ab = (df["c"] - df["o"]).abs().rolling(20, min_periods=5).mean()
    out = []
    for di in range(1, len(days)):
        g = df[df.index.date == days[di]]
        prev = df[df.index.date == days[di - 1]]
        if len(g) < 8 or len(prev) < 4:
            continue
        pdh, pdl = float(prev["h"].max()), float(prev["l"].min())
        O, H, L, C = (g[k].values for k in ("o", "h", "l", "c"))
        T, A = g.index, ab.loc[g.index].values
        i = 1
        while i < len(g) - 3:
            found = None
            if L[i] < L[:i].min():
                for j in range(i + 1, min(i + 5, len(g) - 1)):
                    if C[j] > H[max(0, i - 2):i + 1].max() and L[j + 1] > H[j - 1] and abs(C[j] - O[j]) >= 1.2 * A[j]:
                        entry, stop = L[j + 1], L[i:j + 1].min()
                        target = max(pdh, H[:i].max())
                        if target <= entry:
                            target = entry + 2 * (entry - stop)
                        found = ("bullish", j, "previous-day low" if L[i] < pdl else "intraday low", L[i], H[j - 1], L[j + 1], entry, stop, target)
                        break
            if not found and H[i] > H[:i].max():
                for j in range(i + 1, min(i + 5, len(g) - 1)):
                    if C[j] < L[max(0, i - 2):i + 1].min() and H[j + 1] < L[j - 1] and abs(C[j] - O[j]) >= 1.2 * A[j]:
                        entry, stop = H[j + 1], H[i:j + 1].max()
                        target = min(pdl, L[:i].min())
                        if target >= entry:
                            target = entry - 2 * (stop - entry)
                        found = ("bearish", j, "previous-day high" if H[i] > pdh else "intraday high", H[i], H[j + 1], L[j - 1], entry, stop, target)
                        break
            if not found:
                i += 1
                continue
            side, j, ref, lvl, zlo, zhi, entry, stop, target = found
            risk = abs(entry - stop) or 1
            result, r = "no fill", 0.0
            filled = False
            for k in range(j + 2, len(g)):
                if not filled:
                    if (side == "bullish" and L[k] <= entry) or (side == "bearish" and H[k] >= entry):
                        filled = True
                    else:
                        continue
                if (side == "bullish" and L[k] <= stop) or (side == "bearish" and H[k] >= stop):
                    result, r = "loss", -1.0
                    break
                if (side == "bullish" and H[k] >= target) or (side == "bearish" and L[k] <= target):
                    result, r = "win", abs(target - entry) / risk
                    break
            if filled and result == "no fill":
                result = "open at close"
                r = ((C[-1] - entry) if side == "bullish" else (entry - C[-1])) / risk
            out.append({"date": T[j].strftime("%Y-%m-%d"), "time": T[j].strftime("%H:%M"), "side": side, "sweep": ref,
                        "sweep_level": round(float(lvl), 2), "fvg_low": round(float(zlo), 2), "fvg_high": round(float(zhi), 2),
                        "stop": round(float(stop), 2), "target": round(float(target), 2), "zone": zone(T[j]),
                        "silver_bullet": bool(in_sb(T[min(j + 1, len(T) - 1)])), "result": result, "r": round(float(r), 2)})
            i = j + 1
    return out


def stats(recs, sets):
    n = len(recs)
    pct = lambda k: round(100 * k / n, 1) if n else None
    filled = [s for s in sets if s["result"] != "no fill"]
    sb = [s for s in filled if s["silver_bullet"]]
    wr = lambda lst: round(100 * sum(s["result"] == "win" for s in lst) / len(lst), 1) if lst else None
    avg = lambda lst: round(sum(s["r"] for s in lst) / len(lst), 2) if lst else None
    return {"sessions": n,
            "high_in_open_kz": pct(sum(d["high_zone"] == "Open kill zone" for d in recs)),
            "low_in_open_kz": pct(sum(d["low_zone"] == "Open kill zone" for d in recs)),
            "extreme_in_open_kz": pct(sum(d["_open_kz"] for d in recs)),
            "judas_days": pct(sum(d["judas"] is not None for d in recs)),
            "pd_level_taken": pct(sum(d["pdh_status"] != "untouched" or d["pdl_status"] != "untouched" for d in recs)),
            "pd_level_raided": pct(sum("raided" in d["pdh_status"] or "raided" in d["pdl_status"] for d in recs)),
            "setups": {"found": len(sets), "filled": len(filled), "win_rate": wr(filled), "avg_r": avg(filled),
                       "sb_filled": len(sb), "sb_win_rate": wr(sb), "sb_avg_r": avg(sb)}}


def daily_trend(key):
    rows = ((load("prices.json", {}) or {}).get("series", {}).get(key, {}) or {}).get("rows", [])
    if len(rows) < 25:
        return {}
    s = pd.Series([r["c"] for r in rows], index=[r["t"] for r in rows])
    sma = s.rolling(20).mean()
    out = {}
    for i in range(1, len(s)):
        if pd.notna(sma.iloc[i - 1]):
            out[s.index[i]] = "bullish" if s.iloc[i - 1] > sma.iloc[i - 1] else "bearish"
    return out


def stats_with_filters(recs, sets, key):
    st = stats(recs, sets)
    trend = daily_trend(key)
    filled = [s for s in sets if s["result"] != "no fill"]

    def agg(name, lst):
        if not lst:
            return {"name": name, "n": 0, "win_rate": None, "avg_r": None}
        return {"name": name, "n": len(lst), "win_rate": round(100 * sum(s["result"] == "win" for s in lst) / len(lst), 1),
                "avg_r": round(sum(s["r"] for s in lst) / len(lst), 2)}

    al = [s for s in filled if trend.get(s["date"]) == s["side"]]
    ct = [s for s in filled if trend.get(s["date"]) and trend.get(s["date"]) != s["side"]]
    kz = [s for s in filled if s["zone"] == "Open kill zone"]
    st["setups"]["filters"] = [agg("All filled setups", filled), agg("Trend-aligned (20-day average)", al),
                               agg("Counter-trend", ct), agg("Open kill zone only", kz),
                               agg("Trend-aligned + open kill zone", [s for s in al if s["zone"] == "Open kill zone"])]
    return st


def main():
    out = {"generated": now_ist(), "zones": [{"name": n, "from": a, "to": b} for n, a, b in ZONES],
           "silver_bullet": [{"from": a, "to": b} for a, b in SB], "instruments": {}}
    for key, t in TICKERS.items():
        try:
            df = fetch(t, key)
        except Exception as e:
            print(f"{key}: intraday fetch failed ({e})")
            continue
        if df is None or len(df) < 100:
            print(f"{key}: no intraday data")
            continue
        days = sorted(set(df.index.date))
        recs = []
        for k in range(1, len(days)):
            g, prev = df[df.index.date == days[k]], df[df.index.date == days[k - 1]]
            if len(g) >= 4 and len(prev) >= 4:
                recs.append(analyse_day(g, prev))
        if not recs:
            continue
        sets = find_setups(df, days)
        today = dict(recs[-1])
        en, hi = narrate(today)
        today = {k: v for k, v in today.items() if not k.startswith("_")}
        today["story"], today["story_hi"] = en, hi
        recent = df[df.index.date >= days[-5]] if len(days) >= 5 else df
        bars = [{"t": int(ts.timestamp()) + 19800, "o": round(float(r.o), 2), "h": round(float(r.h), 2),
                 "l": round(float(r.l), 2), "c": round(float(r.c), 2)} for ts, r in recent.iterrows()]
        out["instruments"][key] = {
            "today": today, "next": {"pdh": today["high"], "pdl": today["low"], "prev_close": today["close"]},
            "bars": bars, "setups_today": [s for s in sets if s["date"] == today["date"]], "setups_recent": sets[-12:],
            "stats": stats_with_filters(recs, sets, key),
            "history": [{k: v for k, v in r.items() if not k.startswith("_")} for r in recs[-10:]]}
        s = out["instruments"][key]["stats"]
        for fl in s["setups"].get("filters", []):
            print(f"   {key:9} {fl['name']:32} n={fl['n']:3}  win={fl['win_rate']}%  avgR={fl['avg_r']}")
        print(f"{key:9} {today['date']} {today['direction']:8} judas={today['judas']} | {s['sessions']} sessions, "
              f"extreme in open KZ {s['extreme_in_open_kz']}%, setups {s['setups']['filled']} filled, win {s['setups']['win_rate']}%")
    save("intraday.json", out)


if __name__ == "__main__":
    main()
