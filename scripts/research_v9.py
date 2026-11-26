"""v9 research: weekly stop-hunt trades, fib retracement levels, global premium/discount."""
import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yfinance as yf

from backtest import daily
from common import now_ist, save

RES, FACTS = [], []
FIB = [0.25, 0.5, 0.625, 0.75, 0.875]
WORLD = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Nikkei": "^N225", "DAX": "^GDAXI", "FTSE 100": "^FTSE",
         "CAC 40": "^FCHI", "Hang Seng": "^HSI", "KOSPI": "^KS11", "Taiwan": "^TWII", "ASX 200": "^AXJO",
         "Bovespa": "^BVSP", "Mexico": "^MXX", "Indonesia": "^JKSE", "Sensex": "^BSESN"}


def verdict(z):
    return "Holds (strong)" if z >= 3 else "Holds" if z >= 2 else "Weak" if z >= 1 else "Doesn't hold"


def rec(group, title, z, summary, v=None):
    v = v or ("n/a" if z is None else verdict(z))
    RES.append({"group": group, "title": title, "verdict": v, "z": None if z is None else round(z, 2), "summary": summary})
    print(f"{v:15} | {title}: {summary}", flush=True)


def fact(text):
    FACTS.append(text)
    print(f"FACT            | {text}", flush=True)


def stt(rs):
    rs = [x for x in rs if x is not None and not math.isnan(x)]
    n = len(rs)
    if n < 2:
        return n, 0.0, 0.0, 0.0
    m = sum(rs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in rs) / (n - 1))
    return n, 100 * sum(x > 0 for x in rs) / n, m, (m / (sd / math.sqrt(n)) if sd > 0 else 0.0)


# ------------------------------------------------------------ 1. Weekly stop-hunt trades
def sim(side, entry, stop, target, rest, close):
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    if target is not None and ((side == "long" and target <= entry) or (side == "short" and target >= entry)):
        target = None
    for _, b in rest.iterrows():
        if side == "long":
            if b["l"] <= stop:
                return -1.0, risk
            if target is not None and b["h"] >= target:
                return (target - entry) / risk, risk
        else:
            if b["h"] >= stop:
                return -1.0, risk
            if target is not None and b["l"] <= target:
                return (entry - target) / risk, risk
    return ((close - entry) if side == "long" else (entry - close)) / risk, risk


def weekly_trades(ticker, label):
    G = "1. Weekly stop-hunt trades"
    d = daily(ticker)
    d = d[(d.index >= "2008-01-01") & (d["h"] > d["l"])]
    weeks = [g for _, g in d.groupby(d.index.to_period("W-FRI")) if len(g) >= 3]
    T = {"fade_mid": [], "fade_close": [], "follow_close": []}
    for prev, g in zip(weeks[:-1], weeks[1:]):
        pwh, pwl = prev["h"].max(), prev["l"].min()
        eq = (pwh + pwl) / 2
        f0, rest, wc = g.iloc[0], g.iloc[1:], g["c"].iloc[-1]
        day = g.index[0]
        cases = []
        if f0["h"] > pwh:
            cases.append(("fade", "short", f0["h"]) if f0["c"] < pwh else ("follow", "long", f0["l"]))
        if f0["l"] < pwl:
            cases.append(("fade", "long", f0["l"]) if f0["c"] > pwl else ("follow", "short", f0["h"]))
        for rule, side, stop in cases:
            exits = (("fade_mid", eq), ("fade_close", None)) if rule == "fade" else (("follow_close", None),)
            for name, target in exits:
                r = sim(side, f0["c"], stop, target, rest, wc)
                if r:
                    T[name].append({"date": day, "r": r[0], "cost_r": f0["c"] / r[1]})
    names = {"fade_mid": "Fade the Monday trap (exit last week's midpoint, else Friday)",
             "fade_close": "Fade the Monday trap (hold to Friday close)",
             "follow_close": "Follow a Monday break that holds (to Friday close)"}
    print(f"\n----- {label} -----")
    for k, L in T.items():
        L = sorted(L, key=lambda x: x["date"])
        if len(L) < 30:
            rec(G, f"{label}: {names[k]}", None, f"only {len(L)} trades")
            continue
        mid = len(L) // 2
        n, w, m, z = stt([x["r"] for x in L])
        _, _, m1, _ = stt([x["r"] for x in L[:mid]])
        _, _, m2, _ = stt([x["r"] for x in L[mid:]])
        _, w3, mc1, zc1 = stt([x["r"] - 0.0003 * x["cost_r"] for x in L])
        _, _, mc2, zc2 = stt([x["r"] - 0.0010 * x["cost_r"] for x in L])
        both = m1 > 0 and m2 > 0
        v = "Holds" if both and zc1 >= 2 else "Weak" if both and mc1 > 0 else "Doesn't hold"
        if v == "Holds" and zc1 >= 3:
            v = "Holds (strong)"
        rec(G, f"{label}: {names[k]}", zc1,
            f"{n} trades, win {w:.0f}%, {m:+.2f}R before costs | halves {m1:+.2f}R / {m2:+.2f}R | "
            f"after 0.03% cost {mc1:+.2f}R (z {zc1:+.1f}) | after 0.10% cost {mc2:+.2f}R", v=v)


# ------------------------------------------------------------ 2. Fib levels
def zigzag(H, L, th):
    piv, trend, hi_i, lo_i = [], 0, 0, 0
    for i in range(1, len(H)):
        if trend == 0:
            if H[i] > H[hi_i]: hi_i = i
            if L[i] < L[lo_i]: lo_i = i
            if lo_i < hi_i and H[hi_i] >= L[lo_i] * (1 + th):
                piv.append((lo_i, L[lo_i], "L", i)); trend = 1
            elif hi_i < lo_i and L[lo_i] <= H[hi_i] * (1 - th):
                piv.append((hi_i, H[hi_i], "H", i)); trend = -1
        elif trend == 1:
            if H[i] >= H[hi_i]: hi_i = i
            if L[i] <= H[hi_i] * (1 - th):
                piv.append((hi_i, H[hi_i], "H", i)); trend = -1; lo_i = i
        else:
            if L[i] <= L[lo_i]: lo_i = i
            if H[i] >= L[lo_i] * (1 + th):
                piv.append((lo_i, L[lo_i], "L", i)); trend = 1; hi_i = i
    return piv


def share_near(rs, levels, w=0.02):
    return float(np.mean([any(abs(r - x) <= w for x in levels) for r in rs])) if rs else 0.0


def fib_study(ticker, label, th):
    G = "2. Fib levels"
    d = daily(ticker)
    d = d[(d.index >= "2008-01-01") & (d["h"] > d["l"])]
    H, L = d["h"].values, d["l"].values
    piv = zigzag(H, L, th)
    rs, hits, probs = [], 0, []
    for (i0, p0, t0, _), (i1, p1, t1, _), (i2, p2, t2, c2) in zip(piv, piv[1:], piv[2:]):
        rng = abs(p1 - p0)
        if rng <= 0:
            continue
        r = abs(p1 - p2) / rng
        if 0 < r < 1:
            rs.append(r)
            up = t0 == "L"
            T = p1 + 1.5 * rng if up else p1 - 1.5 * rng
            S = d["c"].values[c2]
            if (up and not (p0 < S < T)) or (not up and not (T < S < p0)):
                continue
            res = None
            for k in range(c2 + 1, len(H)):
                if up:
                    if L[k] <= p0: res = 0; break
                    if H[k] >= T: res = 1; break
                else:
                    if H[k] >= p0: res = 0; break
                    if L[k] <= T: res = 1; break
            if res is None:
                continue
            hits += res
            probs.append((S - p0) / (T - p0))
    actual = share_near(rs, FIB)
    offs = [o for o in np.arange(-0.0625, 0.0626, 0.005) if abs(o) >= 0.03]
    null = [share_near(rs, [x + o for x in FIB]) for o in offs]
    z = (actual - np.mean(null)) / np.std(null) if np.std(null) > 0 else 0.0
    hist = np.histogram(rs, bins=[0, .2, .3, .4, .45, .55, .6, .65, .7, .8, .85, .9, 1])[0]
    fact(f"{label} {int(th*100)}% swings: {len(rs)} retracements; distribution by zone {list(hist)} "
         f"(bins 0-.2,.2-.3,.3-.4,.4-.45,.45-.55,.55-.6,.6-.65,.65-.7,.7-.8,.8-.85,.85-.9,.9-1)")
    rec(G, f"{label} ({int(th*100)}% swings): retracements cluster at your fib levels", float(z),
        f"{100*actual:.0f}% ended within ±0.02 of 0.25/0.5/0.625/0.75/0.875 vs {100*np.mean(null):.0f}% at shifted levels ({len(rs)} legs)")
    if probs:
        exp = sum(probs)
        sd = math.sqrt(sum(p * (1 - p) for p in probs))
        zt = (hits - exp) / sd if sd > 0 else 0.0
        rec(G, f"{label} ({int(th*100)}% swings): -1.5 projection is reached more than chance", zt,
            f"reached before the leg's origin broke in {hits} of {len(probs)} cases ({100*hits/len(probs):.0f}%) vs {100*exp/len(probs):.0f}% expected by chance")


# ------------------------------------------------------------ 3. Global premium/discount
def global_pd():
    G = "3. Global premium/discount"
    rows = []
    for name, t in WORLD.items():
        try:
            h = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=False)
        except Exception:
            h = None
        if h is None or h.empty:
            print(f"   skipped {name}")
            continue
        c = h["Close"].dropna()
        if c.index.tz is not None:
            c.index = c.index.tz_localize(None)
        m = c.resample("ME").last().dropna()
        if len(m) < 120:
            continue
        hi, lo = m.rolling(36).max(), m.rolling(36).min()
        pos = (m - lo) / (hi - lo) * 100
        dd = (1 - m / m.cummax()) * 100
        for hz in (6, 12):
            f = (m.shift(-hz) / m - 1) * 100
            for dt in m.index:
                if pd.notna(f.get(dt)) and pd.notna(pos.get(dt)):
                    rows.append({"mkt": name, "date": dt, "h": hz, "f": f[dt], "pos": pos[dt], "dd": dd[dt]})
        print(f"   {name}: {len(m)} months from {m.index[0]:%Y}")
    df = pd.DataFrame(rows)

    def pooled(sub, a, b, title, la, lb, hz):
        s = sub[a | b].copy()
        if a[a | b].sum() < 30 or b[a | b].sum() < 30:
            return rec(G, title, None, "not enough cases")
        s["x"] = a[a | b].astype(float).values
        s["g"] = s["date"].dt.year // 2
        r = sm.OLS(s["f"].values, sm.add_constant(s["x"].values)).fit(cov_type="cluster", cov_kwds={"groups": s["g"].values})
        ma, mb = s.loc[s.x == 1, "f"].mean(), s.loc[s.x == 0, "f"].mean()
        mk = s.loc[s.x == 1, "mkt"].nunique()
        rec(G, title, float(r.tvalues[1]),
            f"next {hz} months: {la} {ma:+.1f}% vs {lb} {mb:+.1f}% (z {r.tvalues[1]:+.1f}, clustered by 2-year blocks; "
            f"{int(s.x.sum())} vs {int((1 - s.x).sum())} market-months, {mk} markets)")

    for hz in (6, 12):
        sub = df[df.h == hz].reset_index(drop=True)
        pooled(sub, sub.pos <= 25, sub.pos >= 75, f"World: deep discount vs premium of 3-year range ({hz}m)",
               "discount (<=25%)", "premium (>=75%)", hz)
    sub = df[df.h == 12].reset_index(drop=True)
    pooled(sub, sub.dd >= 20, sub.dd < 5, "World: 20%+ below the high vs within 5% of it (12m)", "20%+ below high", "near high", 12)
    for hz in (6, 12):
        x = df[df.h == hz]
        fact(f"World base rate: higher {hz} months later in {100*(x.f > 0).mean():.0f}% of market-months, average {x.f.mean():+.1f}%")


def main():
    for fn in (lambda: weekly_trades("^NSEI", "Nifty"), lambda: weekly_trades("^BSESN", "Sensex"),
               lambda: fib_study("^NSEI", "Nifty", 0.03), lambda: fib_study("^NSEI", "Nifty", 0.05),
               lambda: fib_study("^BSESN", "Sensex", 0.03), global_pd):
        try:
            fn()
        except Exception as e:
            print(f"   section failed: {e}")
    save("research_v9.json", {"generated": now_ist(), "facts": FACTS, "results": RES})
    passed = [r for r in RES if r["verdict"].startswith("Holds")]
    print(f"\n===== SUMMARY: {len(passed)} of {len(RES)} tests passed =====")
    for r in passed:
        print(f"   {r['verdict']:15} {r['group']}: {r['title']} (z {r['z']})")
    print("\nFacts:")
    for f in FACTS:
        print("   " + f)


if __name__ == "__main__":
    main()
