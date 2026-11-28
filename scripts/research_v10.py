"""v10 research: ICT conditional chains vs normal volatility.
Does a trap send price to the opposite liquidity? Are equal highs/lows and 1-year extremes magnets?"""
import math

import numpy as np
import pandas as pd

from backtest import daily, hourly
from common import now_ist, save

RES = []


def verdict(z):
    return "Holds (strong)" if z >= 3 else "Holds" if z >= 2 else "Weak" if z >= 1 else "Doesn't hold"


def rec(group, title, z, summary):
    v = "n/a" if z is None else verdict(z)
    RES.append({"group": group, "title": title, "verdict": v, "z": None if z is None else round(z, 2), "summary": summary})
    print(f"{v:15} | {title}: {summary}", flush=True)


def exp_test(group, title, events, what):
    events = [e for e in events if e is not None]
    n = len(events)
    if n < 20:
        return rec(group, title, None, f"only {n} cases")
    hits = sum(h for h, p in events)
    exp = sum(p for h, p in events)
    var = sum(p * (1 - p) for h, p in events)
    z = (hits - exp) / math.sqrt(var) if var > 0 else 0.0
    rec(group, title, z, f"{what} {100 * hits / n:.0f}% vs {100 * exp / n:.0f}% expected from normal volatility ({n} cases)")


def pge(arr, x):
    return float((arr >= x).mean())


def prep(t):
    d = daily(t)
    d = d[(d.index >= "2008-01-01") & (d["h"] > d["l"])].copy()
    d["adr"] = (d["h"] - d["l"]).rolling(14).mean()
    return d.dropna(subset=["adr"])


def dist_k(d, k):
    hi = d["h"].iloc[::-1].rolling(k).max().iloc[::-1].shift(-1)
    lo = d["l"].iloc[::-1].rolling(k).min().iloc[::-1].shift(-1)
    return ((hi - d["c"]) / d["adr"]).dropna().values, ((d["c"] - lo) / d["adr"]).dropna().values


def weekly_draw(d, label):
    G = "1. Weekly trap -> opposite liquidity"
    D = {k: dist_k(d, k) for k in range(1, 6)}
    weeks = [g for _, g in d.groupby(d.index.to_period("W-FRI")) if len(g) >= 3]
    rej, held = [], []
    for prev, g in zip(weeks[:-1], weeks[1:]):
        pwh, pwl, f0, rest = prev["h"].max(), prev["l"].min(), g.iloc[0], g.iloc[1:]
        k, a = min(len(rest), 5), f0["adr"]
        if k < 1 or a <= 0:
            continue
        if f0["h"] > pwh and not f0["l"] < pwl:
            x = (f0["c"] - pwl) / a
            if x > 0:
                (rej if f0["c"] < pwh else held).append((bool(rest["l"].min() <= pwl), pge(D[k][1], x)))
        if f0["l"] < pwl and not f0["h"] > pwh:
            x = (pwh - f0["c"]) / a
            if x > 0:
                (rej if f0["c"] > pwl else held).append((bool(rest["h"].max() >= pwh), pge(D[k][0], x)))
    exp_test(G, f"{label}: after a weekly trap, the week reaches the OTHER side of last week's range", rej, "reached it")
    exp_test(G, f"{label}: control - after a held weekly breakout, the week reaches the other side", held, "reached it")


def daily_draw(t, label):
    G = "2. Daily trap -> opposite liquidity"
    h = hourly(t)
    if h is None:
        return
    days = [(k, g) for k, g in h.groupby(h.index.date) if len(g) >= 5]
    rng = pd.Series({k: g["h"].max() - g["l"].min() for k, g in days})
    adr = rng.rolling(14).mean().shift(1)
    upx, dnx = [], []
    for k, g in days:
        a = adr.get(k)
        if a is None or not a > 0:
            continue
        f, rest = g.iloc[0], g.iloc[1:]
        upx.append((rest["h"].max() - f["c"]) / a)
        dnx.append((f["c"] - rest["l"].min()) / a)
    upx, dnx = np.array(upx), np.array(dnx)
    rej, held, prev = [], [], None
    for k, g in days:
        a = adr.get(k)
        if prev is not None and a is not None and a > 0:
            pdh, pdl, f, rest = prev["h"].max(), prev["l"].min(), g.iloc[0], g.iloc[1:]
            if f["h"] > pdh and not f["l"] < pdl:
                x = (f["c"] - pdl) / a
                if x > 0:
                    (rej if f["c"] < pdh else held).append((bool(rest["l"].min() <= pdl), pge(dnx, x)))
            if f["l"] < pdl and not f["h"] > pdh:
                x = (pdh - f["c"]) / a
                if x > 0:
                    (rej if f["c"] > pdl else held).append((bool(rest["h"].max() >= pdh), pge(upx, x)))
        prev = g
    exp_test(G, f"{label}: after a first-hour trap, the day reaches the OTHER side of yesterday's range", rej, "reached it")
    exp_test(G, f"{label}: control - after a held opening breakout, the day reaches the other side", held, "reached it")


def equal_levels(d, label):
    G = "3. Equal highs/lows as magnets"
    up20, dn20 = dist_k(d, 20)
    H, L, C, A, n = d["h"].values, d["l"].values, d["c"].values, d["adr"].values, len(d)
    piv = {"h": [i for i in range(2, n - 2) if H[i] > max(H[i - 2], H[i - 1], H[i + 1], H[i + 2])],
           "l": [i for i in range(2, n - 2) if L[i] < min(L[i - 2], L[i - 1], L[i + 1], L[i + 2])]}
    eq, single = [], []
    for kind, P in piv.items():
        for j, i in enumerate(P):
            t = i + 2
            if t + 20 >= n:
                break
            lvl = H[i] if kind == "h" else L[i]
            partner = None
            for i0 in reversed(P[:j]):
                if i - i0 > 40:
                    break
                v = H[i0] if kind == "h" else L[i0]
                if abs(v / lvl - 1) <= 0.001:
                    seg = H[i0 + 1:i] if kind == "h" else L[i0 + 1:i]
                    if len(seg) and ((kind == "h" and seg.max() < max(v, lvl)) or (kind == "l" and seg.min() > min(v, lvl))):
                        partner = v
                        break
            L0 = (max(lvl, partner) if kind == "h" else min(lvl, partner)) if partner else lvl
            if kind == "h":
                if H[i + 1:t + 1].max() >= L0 or L0 <= C[t]:
                    continue
                e = (bool(H[t + 1:t + 21].max() >= L0), pge(up20, (L0 - C[t]) / A[t]))
            else:
                if L[i + 1:t + 1].min() <= L0 or L0 >= C[t]:
                    continue
                e = (bool(L[t + 1:t + 21].min() <= L0), pge(dn20, (C[t] - L0) / A[t]))
            (eq if partner else single).append((t, e))

    def thin(lst):
        out, last = [], -10
        for t, e in sorted(lst, key=lambda x: x[0]):
            if t - last >= 5:
                out.append(e)
                last = t
        return out

    E, S = thin(eq), thin(single)
    exp_test(G, f"{label}: relative equal highs/lows get taken within 20 sessions", E, "taken")
    exp_test(G, f"{label}: control - single swing highs/lows get taken within 20 sessions", S, "taken")
    if len(E) >= 20 and len(S) >= 20:
        re_ = np.array([h - p for h, p in E], dtype=float)
        rs_ = np.array([h - p for h, p in S], dtype=float)
        se = math.sqrt(re_.var(ddof=1) / len(re_) + rs_.var(ddof=1) / len(rs_))
        z = (re_.mean() - rs_.mean()) / se if se > 0 else 0.0
        rec(G, f"{label}: equal highs/lows attract MORE than single highs/lows", z,
            f"excess over volatility: equal {100 * re_.mean():+.0f} pts vs single {100 * rs_.mean():+.0f} pts (z {z:+.1f})")


def yearly_magnet(d, label):
    G = "4. 1-year high/low as magnets"
    up20, dn20 = dist_k(d, 20)
    H, L, C, A, n = d["h"].values, d["l"].values, d["c"].values, d["adr"].values, len(d)
    yh, yl = d["h"].rolling(252).max().values, d["l"].rolling(252).min().values
    nh, nl, lh, ll = [], [], -100, -100
    for t in range(252, n - 20):
        if 0 < yh[t] / C[t] - 1 <= 0.05 and t - lh >= 20:
            nh.append((bool(H[t + 1:t + 21].max() >= yh[t]), pge(up20, (yh[t] - C[t]) / A[t]))); lh = t
        if 0 < 1 - yl[t] / C[t] <= 0.05 and t - ll >= 20:
            nl.append((bool(L[t + 1:t + 21].min() <= yl[t]), pge(dn20, (C[t] - yl[t]) / A[t]))); ll = t
    exp_test(G, f"{label}: within 5% of the 1-year HIGH -> touched within 20 sessions", nh, "touched")
    exp_test(G, f"{label}: within 5% of the 1-year LOW -> touched within 20 sessions", nl, "touched")


def main():
    for label, t in (("Sensex", "^BSESN"), ("Nifty", "^NSEI")):
        print(f"\n----- {label} -----")
        try:
            d = prep(t)
        except Exception as e:
            print(f"   data failed: {e}")
            continue
        for fn in (lambda: weekly_draw(d, label), lambda: daily_draw(t, label), lambda: equal_levels(d, label), lambda: yearly_magnet(d, label)):
            try:
                fn()
            except Exception as e:
                print(f"   section failed: {e}")
    save("research_v10.json", {"generated": now_ist(), "results": RES})
    passed = [r for r in RES if r["verdict"].startswith("Holds")]
    print(f"\n===== SUMMARY: {len(passed)} of {len(RES)} tests passed =====")
    for r in passed:
        print(f"   {r['verdict']:15} {r['title']} (z {r['z']})")


if __name__ == "__main__":
    main()
