"""Backtest ICT masterbook tendencies on long Sensex / Nifty history (daily) and 2 years of hourly data."""
import math

import pandas as pd
import yfinance as yf

from common import now_ist, save

TICKERS = {"SENSEX": "^BSESN", "NIFTY": "^NSEI"}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CLAIM = {1: "bullish", 2: "caution", 3: "bullish", 4: "neutral", 5: "bullish", 6: "bearish", 7: "bearish",
         8: "volatile", 9: "bullish", 10: "volatile", 11: "bullish", 12: "bullish"}
HI_V = {"Holds": "data se sach nikla", "Weak": "thoda sach, par kamzor", "Doesn't hold": "data se sabit nahi hua"}


def z_prop(k, n, p0):
    if n == 0 or p0 <= 0 or p0 >= 1:
        return 0.0
    return (k / n - p0) / math.sqrt(p0 * (1 - p0) / n)


def z_mean(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    se = math.sqrt(a.var() / len(a) + b.var() / len(b))
    return 0.0 if se == 0 else (a.mean() - b.mean()) / se


def verdict(zv):
    return "Holds" if zv >= 2 else "Weak" if zv >= 1 else "Doesn't hold"


def pc(k, n):
    return f"{100 * k / n:.0f}%" if n else "-"


def daily(t):
    df = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=False)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    df.columns = ["o", "h", "l", "c"]
    return df[df["c"] > 0]


def hourly(t):
    df = yf.Ticker(t).history(period="730d", interval="1h", auto_adjust=False)
    if df is None or df.empty:
        return None
    idx = df.index
    df.index = idx.tz_convert("Asia/Kolkata") if idx.tz is not None else idx.tz_localize("UTC").tz_convert("Asia/Kolkata")
    df = df[["Open", "High", "Low", "Close"]].dropna()
    df.columns = ["o", "h", "l", "c"]
    return df.between_time("09:15", "15:29")


def t_weekly(d):
    up, dn, nu, nd = [0] * 5, [0] * 5, 0, 0
    for _, g in d.groupby(d.index.to_period("W-FRI")):
        if len(g) < 4 or (g.index.weekday > 4).any():
            continue
        if g["c"].iloc[-1] > g["o"].iloc[0]:
            up[g["l"].idxmin().weekday()] += 1
            nu += 1
        else:
            dn[g["h"].idxmax().weekday()] += 1
            nd += 1
    k1, k2 = up[1] + up[2], dn[1] + dn[2]
    v1, v2 = verdict(z_prop(k1, nu, 0.4)), verdict(z_prop(k2, nd, 0.4))
    return [
        {"id": "week_low", "title": "Tuesday/Wednesday low of the week (up weeks)",
         "title_hi": "Tezi wale hafte ka low Mangal/Budh ko", "claim": "In bullish weeks the weekly low tends to form on Tuesday or Wednesday.",
         "verdict": v1, "summary": f"Of {nu} up weeks, the low formed on Tue/Wed in {pc(k1, nu)} (random is about 40%). Monday held the low in {pc(up[0], nu)}.",
         "hi": f"{HI_V[v1]} — Mangal/Budh ko low {pc(k1, nu)} hafton mein (random ~40%), Somvar ko {pc(up[0], nu)}.",
         "cols": ["Day", "Share of up weeks"], "rows": [[DAYS[i], pc(up[i], nu)] for i in range(5)], "sample": f"{nu} up weeks since 2008"},
        {"id": "week_high", "title": "Tuesday/Wednesday high of the week (down weeks)",
         "title_hi": "Mandi wale hafte ka high Mangal/Budh ko", "claim": "In bearish weeks the weekly high tends to form on Tuesday or Wednesday.",
         "verdict": v2, "summary": f"Of {nd} down weeks, the high formed on Tue/Wed in {pc(k2, nd)} (random is about 40%). Monday held the high in {pc(dn[0], nd)}.",
         "hi": f"{HI_V[v2]} — Mangal/Budh ko high {pc(k2, nd)} hafton mein (random ~40%), Somvar ko {pc(dn[0], nd)}.",
         "cols": ["Day", "Share of down weeks"], "rows": [[DAYS[i], pc(dn[i], nd)] for i in range(5)], "sample": f"{nd} down weeks since 2008"},
    ]


def t_tuesday(d):
    r = d["c"].pct_change()
    tue = r[r.index.weekday == 1].dropna()
    cond = [val for ts, val in tue.items() if (ts - pd.Timedelta(days=1)) in r.index and r[ts - pd.Timedelta(days=1)] < 0]
    cond = pd.Series(cond, dtype=float)
    p0, k, n = float((tue > 0).mean()), int((cond > 0).sum()), len(cond)
    v = verdict(z_prop(k, n, p0))
    return {"id": "tuesday", "title": "Tuesday reversal after a down Monday", "title_hi": "Somvar girne ke baad Mangalvar ko tezi",
            "claim": "If Monday closes down, Tuesday tends to reverse up.", "verdict": v,
            "summary": f"After a down Monday, Tuesday closed up {pc(k, n)} of the time vs {p0 * 100:.0f}% for all Tuesdays.",
            "hi": f"{HI_V[v]} — girte Somvar ke baad Mangalvar {pc(k, n)} baar upar, normal Mangalvar {p0 * 100:.0f}%.",
            "cols": [], "rows": [], "sample": f"{n} down Mondays since 2008"}


def t_trend(d):
    rng = d["h"] - d["l"]
    trend = (d["c"] - d["o"]).abs() >= 0.6 * rng
    rp = rng / d["c"].shift() * 100
    wd = d.index.weekday
    base = float(trend.mean())
    rows = [[DAYS[i], f"{100 * trend[wd == i].mean():.0f}%", f"{rp[wd == i].mean():.2f}%"] for i in range(5)]
    wed = trend[wd == 2]
    v = verdict(z_prop(int(wed.sum()), len(wed), base))
    best = DAYS[max(range(5), key=lambda i: trend[wd == i].mean())]
    return {"id": "wednesday", "title": "Wednesday is the strongest trend day", "title_hi": "Budhvar sabse strong trend wala din",
            "claim": "Wednesday delivers the cleanest trending day of the week.", "verdict": v,
            "summary": f"Trend days (body at least 60% of range): Wednesday {100 * wed.mean():.0f}% vs {base * 100:.0f}% overall. Most trend days fall on {best}.",
            "hi": f"{HI_V[v]} — Budhvar trend day {100 * wed.mean():.0f}% vs average {base * 100:.0f}%; sabse zyada {best} ko.",
            "cols": ["Day", "Trend-day share", "Avg range"], "rows": rows, "sample": f"{len(d)} sessions since 2008"}


def t_expiry(d, start, end, weekday, label):
    x = d[(d.index >= start) & (d.index <= end)]
    rp = ((x["h"] - x["l"]) / x["c"].shift() * 100).dropna()
    mv = ((x["c"] - x["c"].shift()).abs() / x["c"].shift() * 100).dropna()
    e, o = rp[rp.index.weekday == weekday], rp[rp.index.weekday != weekday]
    em, om = mv[mv.index.weekday == weekday], mv[mv.index.weekday != weekday]
    v = verdict(z_mean(e, o))
    return {"id": f"expiry_{label}", "title": f"Expiry-day volatility ({label})", "title_hi": f"Expiry ke din zyada hilchal ({label})",
            "claim": "Expiry days see larger, sharper moves than other days.", "verdict": v,
            "summary": f"Average high-low range on expiry days {e.mean():.2f}% vs {o.mean():.2f}% on other days; close-to-close move {em.mean():.2f}% vs {om.mean():.2f}%.",
            "hi": f"{HI_V[v]} — expiry pe range {e.mean():.2f}% vs baaki din {o.mean():.2f}%.",
            "cols": ["", "Expiry days", "Other days"],
            "rows": [["Avg range", f"{e.mean():.2f}%", f"{o.mean():.2f}%"], ["Avg move", f"{em.mean():.2f}%", f"{om.mean():.2f}%"], ["Days", len(e), len(o)]],
            "sample": f"{start} onward{'' if end > '2099' else ' to ' + end}; holiday shifts not adjusted"}


def t_season(df):
    m = df["c"].resample("ME").last().pct_change().dropna() * 100
    base = float((m > 0).mean())
    rows, ok, tested = [], 0, 0
    for i in range(1, 13):
        x = m[m.index.month == i]
        k, n = int((x > 0).sum()), len(x)
        res = "Info"
        if CLAIM[i] == "bullish":
            res = verdict(z_prop(k, n, base)); tested += 1; ok += res == "Holds"
        elif CLAIM[i] == "bearish":
            res = verdict(-z_prop(k, n, base)); tested += 1; ok += res == "Holds"
        rows.append([MON[i - 1], CLAIM[i], f"{x.mean():+.2f}%", pc(k, n), res])
    v = "Holds" if ok >= tested * 0.6 else "Weak" if ok >= tested * 0.3 else "Doesn't hold"
    yrs = len(m) // 12
    return {"id": "seasonality", "title": "Peak and lean months", "title_hi": "Achhe aur kamzor mahine",
            "claim": "Jan, Mar, May, Sep, Nov, Dec are bullish; Jun and Jul lean bearish.", "verdict": v,
            "summary": f"{ok} of {tested} directional month claims beat the base rate of {base * 100:.0f}% positive months ({yrs} years of data).",
            "hi": f"{HI_V[v]} — {ok}/{tested} mahino ka daava data se match hua ({yrs} saal).",
            "cols": ["Month", "Claim", "Avg return", "% up", "Verdict"], "rows": rows, "sample": f"{len(m)} months of Sensex closes"}


def t_hourly(h):
    days = [g for _, g in h.groupby(h.index.date) if len(g) >= 5]
    if not days:
        return []
    bars = int(pd.Series([len(g) for g in days]).median())
    opp = n = ext = sw = rev = 0
    prev = None
    for g in days:
        f, o, c = g.iloc[0], g["o"].iloc[0], g["c"].iloc[-1]
        if f["c"] != f["o"] and c != o:
            n += 1
            opp += (f["c"] > f["o"]) != (c > o)
        ext += (g["h"].values.argmax() == 0) or (g["l"].values.argmin() == 0)
        if prev is not None:
            pdh, pdl = prev["h"].max(), prev["l"].min()
            if f["h"] > pdh or f["l"] < pdl:
                sw += 1
                rev += (f["h"] > pdh and c < pdh) or (f["l"] < pdl and c > pdl)
        prev = g
    nd = len(days)
    p_ext = 1 - (1 - 1 / bars) ** 2
    v1, v2, v3 = verdict(z_prop(opp, n, 0.5)), verdict(z_prop(ext, nd, p_ext)), verdict(z_prop(rev, sw, 0.5))
    return [
        {"id": "fakeout", "title": "The opening move is a fake-out", "title_hi": "Subah ka move aksar nakli",
         "claim": "The first move after the open is usually opposite to the day's real direction.", "verdict": v1,
         "summary": f"The first hour pointed the opposite way to the day's close in {pc(opp, n)} of sessions (random 50%).",
         "hi": f"{HI_V[v1]} — pehle ghante ki disha {pc(opp, n)} din ulti nikli (random 50%).",
         "cols": [], "rows": [], "sample": f"{n} sessions (2 years, hourly)"},
        {"id": "first_hour", "title": "Day's high or low is set in the first hour", "title_hi": "Din ka high/low pehle ghante mein",
         "claim": "The open kill zone frequently prints the high or low of the day.", "verdict": v2,
         "summary": f"The first hour held the day's high or low in {pc(ext, nd)} of sessions (random about {p_ext * 100:.0f}%).",
         "hi": f"{HI_V[v2]} — {pc(ext, nd)} din high ya low pehle ghante mein bana (random ~{p_ext * 100:.0f}%).",
         "cols": [], "rows": [], "sample": f"{nd} sessions (2 years, hourly)"},
        {"id": "open_sweep", "title": "Opening sweep of PDH/PDL then reversal", "title_hi": "Subah kal ka high/low tod ke wapsi",
         "claim": "When the first hour takes the previous day's high or low, price usually closes back inside.", "verdict": v3,
         "summary": f"The first hour swept PDH or PDL on {sw} days; the day closed back inside in {pc(rev, sw)} (random 50%).",
         "hi": f"{HI_V[v3]} — {sw} din subah kal ka high/low toda, {pc(rev, sw)} din wapas andar band hua.",
         "cols": [], "rows": [], "sample": f"{sw} sweep days (2 years, hourly)"},
    ]


def t_hourly_cond(h):
    days = [g for _, g in h.groupby(h.index.date) if len(g) >= 5]
    if len(days) < 30:
        return []
    opp = n = rej_n = rej_rev = brk_n = brk_rev = 0
    prev = None
    for g in days:
        f, c = g.iloc[0], g["c"].iloc[-1]
        a, b = f["c"] - f["o"], c - f["c"]
        if a != 0 and b != 0:
            n += 1
            opp += (a > 0) != (b > 0)
        if prev is not None:
            pdh, pdl = prev["h"].max(), prev["l"].min()
            for took, rejected, back in ((f["h"] > pdh, f["c"] < pdh, c < pdh), (f["l"] < pdl, f["c"] > pdl, c > pdl)):
                if not took:
                    continue
                if rejected:
                    rej_n += 1
                    rej_rev += bool(back)
                else:
                    brk_n += 1
                    brk_rev += bool(back)
        prev = g
    v1 = verdict(z_prop(opp, n, 0.5))
    base = brk_rev / brk_n if brk_n else 0.5
    v2 = verdict(z_prop(rej_rev, rej_n, base)) if rej_n and brk_n else "Doesn't hold"
    return [
        {"id": "fakeout_fair", "title": "Opening move vs rest of day (fair test)", "title_hi": "",
         "claim": "After the first hour, the rest of the day tends to move against the opening move.", "verdict": v1,
         "summary": f"After the first hour, the rest of the day moved opposite to the first-hour move in {pc(opp, n)} of sessions (random 50%).",
         "hi": "", "cols": [], "rows": [], "sample": f"{n} sessions (2 years, hourly)"},
        {"id": "sweep_rejection", "title": "Opening PDH/PDL sweep: rejection close vs holding beyond", "title_hi": "",
         "claim": "A first-hour sweep of yesterday's high/low that closes back inside reverses more often than one that holds beyond.",
         "verdict": v2,
         "summary": f"With a rejection close in the first hour, the day closed back inside {pc(rej_rev, rej_n)} of the time vs {pc(brk_rev, brk_n)} when the first hour held beyond.",
         "hi": "", "cols": ["First hour", "Cases", "Day closed back inside"],
         "rows": [["Rejection close", rej_n, pc(rej_rev, rej_n)], ["Held beyond", brk_n, pc(brk_rev, brk_n)]],
         "sample": "2 years, hourly"},
    ]


def main():
    out = {"generated": now_ist(), "instruments": {}}
    for key, t in TICKERS.items():
        tests = []
        try:
            df = daily(t)
            d = df[(df.index >= "2008-01-01") & (df["h"] > df["l"])]
            tests += t_weekly(d)
            tests.append(t_tuesday(d))
            tests.append(t_trend(d))
            if key == "SENSEX":
                tests.append(t_expiry(d, "2025-09-01", "2100-01-01", 3, "Sensex Thursday"))
            else:
                tests.append(t_expiry(d, "2019-02-11", "2025-08-31", 3, "Nifty Thursday"))
                tests.append(t_expiry(d, "2025-09-01", "2100-01-01", 1, "Nifty Tuesday"))
            tests.append(t_season(df))
        except Exception as e:
            print(f"{key}: daily tests failed ({e})")
        try:
            h = hourly(t)
            if h is not None:
                tests += t_hourly(h)
                tests += t_hourly_cond(h)
        except Exception as e:
            print(f"{key}: hourly tests failed ({e})")
        out["instruments"][key] = tests
        for x in tests:
            print(f"{key:7} {x['verdict']:13} {x['title']}: {x['summary']}")
    save("backtest.json", out)


if __name__ == "__main__":
    main()
