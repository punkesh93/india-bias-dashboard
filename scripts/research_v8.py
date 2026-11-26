"""v8 research: big picture (3/6/12 months), higher-timeframe traps, Judas on weekly/monthly, FVG behaviour."""
import math

import pandas as pd
import statsmodels.api as sm

from backtest import daily
from common import now_ist, save
from positioning_study import fii_frame

RES, FACTS = [], []


def verdict(z):
    return "Holds (strong)" if z >= 3 else "Holds" if z >= 2 else "Weak" if z >= 1 else "Doesn't hold"


def rec(group, title, z, summary):
    v = "n/a" if z is None else verdict(z)
    RES.append({"group": group, "title": title, "verdict": v, "z": None if z is None else round(z, 2), "summary": summary})
    print(f"{v:15} | {title}: {summary}", flush=True)


def fact(text):
    FACTS.append(text)
    print(f"FACT            | {text}", flush=True)


def hac(y, a, b, lag):
    m = (a | b) & y.notna()
    if a[m].sum() < 10 or b[m].sum() < 10:
        return None
    Y, A = y[m].astype(float).values, a[m].astype(float).values
    r = sm.OLS(Y, sm.add_constant(A)).fit(cov_type="HAC", cov_kwds={"maxlags": max(1, lag)})
    return int(A.sum()), int(len(A) - A.sum()), float(Y[A == 1].mean()), float(Y[A == 0].mean()), float(r.tvalues[1])


def rech(group, title, t, hz, la, lb):
    if t is None:
        return rec(group, title, None, "not enough cases")
    na, nb, ma, mb, z = t
    rec(group, title, z, f"next {hz}: {la} {ma:+.2f}% vs {lb} {mb:+.2f}% (z {z:+.1f} overlap-corrected; {na} vs {nb} month-ends)")


def binom(k, n, p0=0.5):
    return 0.0 if n == 0 else (k / n - p0) / math.sqrt(p0 * (1 - p0) / n)


def twoprop(k1, n1, k2, n2):
    if min(n1, n2) < 10:
        return 0.0
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return 0.0 if se == 0 else (k1 / n1 - k2 / n2) / se


def pc(k, n):
    return f"{100 * k / n:.0f}%" if n else "-"


# ------------------------------------------------------------ 1. Big picture
def big_picture():
    G = "1. Big picture"
    print(f"\n===== {G} (3/6/12 months) =====")
    df = daily("^BSESN")
    c = df["c"]
    m = c.resample("ME").last()
    for h in (3, 6, 12):
        f = ((m.shift(-h) / m - 1) * 100).dropna()
        fact(f"Sensex {h} months later: higher {100 * (f > 0).mean():.0f}% of the time, average {f.mean():+.1f}% (month-ends since {m.index[0]:%Y})")
    for win, hs in ((12, (3, 6, 12)), (36, (6, 12))):
        hi, lo = m.rolling(win).max(), m.rolling(win).min()
        pos = (m - lo) / (hi - lo) * 100
        for h in hs:
            f = (m.shift(-h) / m - 1) * 100
            rech(G, f"Deep discount vs premium of {win}-month range", hac(f, pos <= 25, pos >= 75, h), f"{h} months",
                 "discount (<=25%)", "premium (>=75%)")
    ddm = ((1 - c / c.cummax()) * 100).resample("ME").last()
    for h in (6, 12):
        f = (m.shift(-h) / m - 1) * 100
        rech(G, "After a 15%+ fall from the high vs near the high (<5%)", hac(f, ddm >= 15, ddm < 5, h), f"{h} months",
             "15%+ below high", "within 5% of high")
    fr = fii_frame()
    d = fr.join(daily("^NSEI")["c"].rename("c"), how="inner")
    lo, hi = d["fii"].rolling(252).min(), d["fii"].rolling(252).max()
    dm = pd.DataFrame({"p": (d["fii"] - lo) / (hi - lo) * 100, "c": d["c"]}).resample("ME").last()
    for h in (3, 6):
        f = (dm.c.shift(-h) / dm.c - 1) * 100
        rech(G, "FII most long vs most short (1-year range) -> Nifty", hac(f, dm.p >= 90, dm.p <= 10, h), f"{h} months",
             "FII top 10%", "FII bottom 10%")


# ------------------------------------------------------------ 2. Higher-timeframe traps
def traps():
    G = "2. HTF traps"
    print(f"\n===== {G} (failed breakouts, retail trap) =====")
    df = daily("^BSESN")
    d = df[df["h"] > df["l"]]
    mb = d.resample("ME").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    p12h, p12l = mb["h"].rolling(12).max().shift(1), mb["l"].rolling(12).min().shift(1)
    failed_bo, true_bo = (mb.h > p12h) & (mb.c < p12h), mb.c > p12h
    failed_bd, true_bd = (mb.l < p12l) & (mb.c > p12l), mb.c < p12l
    for h in (3, 6):
        f = (mb.c.shift(-h) / mb.c - 1) * 100
        rech(G, "Monthly true breakout vs failed breakout (swept 12-month high, closed below)",
             hac(f, true_bo, failed_bo, h), f"{h} months", "true breakout", "failed breakout (trap)")
        rech(G, "Monthly failed breakdown (swept 12-month low, closed above) vs true breakdown",
             hac(f, failed_bd, true_bd, h), f"{h} months", "failed breakdown (bear trap)", "true breakdown")
    fr = fii_frame()
    dd = fr.join(daily("^NSEI")["c"].rename("c"), how="inner")
    lo, hi = dd["cli"].rolling(252).min(), dd["cli"].rolling(252).max()
    dm = pd.DataFrame({"p": (dd["cli"] - lo) / (hi - lo) * 100, "c": dd["c"]}).resample("ME").last()
    for h in (3, 6):
        f = (dm.c.shift(-h) / dm.c - 1) * 100
        rech(G, "Retail trap: retail most short vs most long (1-year range) -> Nifty", hac(f, dm.p <= 10, dm.p >= 90, h),
             f"{h} months", "retail most short", "retail most long")


# ------------------------------------------------------------ 3. Judas swing on higher timeframes
def judas():
    G = "3. HTF Judas"
    print(f"\n===== {G} (weekly / monthly) =====")
    d = daily("^NSEI")
    d = d[(d.index >= "2008-01-01") & (d["h"] > d["l"])]
    weeks = [g for _, g in d.groupby(d.index.to_period("W-FRI")) if len(g) >= 3]
    opp = n = 0
    for g in weeks:
        a, b = g.c.iloc[0] - g.o.iloc[0], g.c.iloc[-1] - g.c.iloc[0]
        if a and b:
            n += 1
            opp += (a > 0) != (b > 0)
    rec(G, "Weekly: first day's move is a fake-out", binom(opp, n), f"rest of week went opposite in {pc(opp, n)} of {n} weeks (random 50%)")
    opp = n = 0
    for _, g in d.groupby(d.index.to_period("M")):
        if len(g) < 10:
            continue
        a, b = g.c.iloc[4] - g.o.iloc[0], g.c.iloc[-1] - g.c.iloc[4]
        if a and b:
            n += 1
            opp += (a > 0) != (b > 0)
    rec(G, "Monthly: first 5 days are a fake-out", binom(opp, n), f"rest of month went opposite in {pc(opp, n)} of {n} months (random 50%)")
    rn = ri = bn = bi = 0
    for prev, g in zip(weeks[:-1], weeks[1:]):
        pwh, pwl, f0, wc = prev.h.max(), prev.l.min(), g.iloc[0], g.c.iloc[-1]
        for took, rejected, back in ((f0.h > pwh, f0.c < pwh, wc < pwh), (f0.l < pwl, f0.c > pwl, wc > pwl)):
            if took:
                if rejected:
                    rn += 1; ri += bool(back)
                else:
                    bn += 1; bi += bool(back)
    rec(G, "Weekly stop hunt: first-day sweep of last week's high/low + rejection", twoprop(ri, rn, bi, bn),
        f"rejection -> week closed back inside {pc(ri, rn)} ({rn} cases) vs held beyond {pc(bi, bn)} ({bn} cases)")


# ------------------------------------------------------------ 4. Fair value gaps
def fvg():
    G = "4. FVG"
    print(f"\n===== {G} (Nifty daily since 2008) =====")
    d = daily("^NSEI")
    d = d[(d.index >= "2008-01-01") & (d["h"] > d["l"])]
    H, L, C, idx, N = d["h"].values, d["l"].values, d["c"].values, d.index, len(d)
    base5 = float(((d["c"].shift(-5) / d["c"] - 1) * 100).mean())
    fills, nf, react = {5: 0, 20: 0, 60: 0}, 0, []
    holds = {1: [0, 0], 2: [0, 0], 3: [0, 0]}
    for i in range(1, N - 2):
        for kind in ("bull", "bear"):
            if kind == "bull":
                if not (L[i + 1] > H[i - 1]) or (L[i + 1] - H[i - 1]) / C[i] < 0.001:
                    continue
                bot, top = H[i - 1], L[i + 1]
            else:
                if not (H[i + 1] < L[i - 1]) or (L[i - 1] - H[i + 1]) / C[i] < 0.001:
                    continue
                bot, top = H[i + 1], L[i - 1]
            nf += 1
            filled, touches, inside_prev = None, 0, False
            for j in range(i + 2, min(i + 122, N)):
                inside = L[j] <= top if kind == "bull" else H[j] >= bot
                if filled is None and ((kind == "bull" and L[j] <= bot) or (kind == "bear" and H[j] >= top)):
                    filled = j - (i + 1)
                if inside and not inside_prev:
                    touches += 1
                    t = min(touches, 3)
                    seg = C[j:j + 6]
                    broke = bool((seg < bot).any()) if kind == "bull" else bool((seg > top).any())
                    holds[t][1] += 1
                    holds[t][0] += not broke
                    if touches == 1 and j + 5 < N:
                        ex = (C[j + 5] / C[j] - 1) * 100 - base5
                        react.append((idx[j], ex if kind == "bull" else -ex))
                    if broke:
                        break
                inside_prev = inside
            for k in fills:
                fills[k] += filled is not None and filled <= k
    fact(f"Nifty daily FVGs since 2008: {nf}. Fully filled within 5 days {pc(fills[5], nf)}, 20 days {pc(fills[20], nf)}, 60 days {pc(fills[60], nf)}")
    rec(G, "FVGs usually get filled within 20 days", binom(fills[20], nf), f"filled within 20 days: {pc(fills[20], nf)} of {nf} (vs 50%)")
    react.sort()
    kept, last = [], None
    for dt, ex in react:
        if last is None or (dt - last).days >= 7:
            kept.append(ex)
            last = dt
    s = pd.Series(kept, dtype=float)
    z = float(s.mean() / (s.std() / math.sqrt(len(s)))) if len(s) > 8 and s.std() > 0 else 0.0
    rec(G, "First touch: FVG acts as support/resistance (next 5 days)", z,
        f"after first touch, price moved in the FVG's direction by {s.mean():+.2f}% vs normal ({len(s)} touches, non-overlapping)")
    for t in (1, 2, 3):
        fact(f"FVG {'3rd+' if t == 3 else ('1st' if t == 1 else '2nd')} touch held (no close through it within 5 days): {pc(*holds[t])} of {holds[t][1]}")
    rec(G, "'FVGs rarely hold a third touch' (1st touch holds more than 3rd+)",
        twoprop(holds[1][0], holds[1][1], holds[3][0], holds[3][1]),
        f"1st touch held {pc(*holds[1])} vs 3rd+ touch {pc(*holds[3])}")


def main():
    for fn in (big_picture, traps, judas, fvg):
        try:
            fn()
        except Exception as e:
            print(f"   section failed: {e}")
    save("research_v8.json", {"generated": now_ist(), "facts": FACTS, "results": RES})
    passed = [r for r in RES if r["verdict"].startswith("Holds")]
    print(f"\n===== SUMMARY: {len(passed)} of {len(RES)} tests passed =====")
    for r in passed:
        print(f"   {r['verdict']:15} {r['group']}: {r['title']} (z {r['z']})")
    print("\nFacts:")
    for f in FACTS:
        print("   " + f)


if __name__ == "__main__":
    main()
