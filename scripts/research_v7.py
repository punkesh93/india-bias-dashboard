"""v7 research: ICT COT method (FII + CFTC), stock SMT relative strength, seasonal windows, structure momentum."""
import math

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from backtest import daily
from common import now_ist, save
from positioning_study import COT_MKTS, COT_URL, fii_frame, fwd_after

RES = []
SEASON = (2, 3, 4, 5, 10, 11, 12, 1)
STOCKS = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "BHARTIARTL", "ITC", "LT", "SBIN", "KOTAKBANK",
          "AXISBANK", "HINDUNILVR", "BAJFINANCE", "MARUTI", "SUNPHARMA", "M&M", "TITAN", "ASIANPAINT", "ULTRACEMCO",
          "NTPC", "POWERGRID", "TATASTEEL", "JSWSTEEL", "HCLTECH", "WIPRO", "TECHM", "NESTLEIND", "ONGC", "COALINDIA",
          "ADANIENT", "ADANIPORTS", "BAJAJFINSV", "GRASIM", "HINDALCO", "DRREDDY", "CIPLA", "EICHERMOT", "HEROMOTOCO",
          "BRITANNIA", "INDUSINDBK", "APOLLOHOSP", "DIVISLAB", "BPCL", "SBILIFE", "HDFCLIFE", "TATACONSUM",
          "BAJAJ-AUTO", "SHRIRAMFIN", "TRENT"]


def verdict(z):
    return "Holds (strong)" if z >= 3 else "Holds" if z >= 2 else "Weak" if z >= 1 else "Doesn't hold"


def two(a, b):
    a, b = pd.Series(a, dtype=float).dropna(), pd.Series(b, dtype=float).dropna()
    if len(a) < 8 or len(b) < 8:
        return None
    se = math.sqrt(a.var() / len(a) + b.var() / len(b))
    d = a.mean() - b.mean()
    return len(a), len(b), float(a.mean()), float(b.mean()), float(d / se) if se else 0.0


def zstat(x):
    x = pd.Series(x, dtype=float).dropna()
    if len(x) < 8 or x.std() == 0:
        return len(x), float(x.mean()) if len(x) else 0.0, 0.0
    return len(x), float(x.mean()), float(x.mean() / (x.std() / math.sqrt(len(x))))


def rec(group, title, z, summary):
    v = verdict(z) if z is not None else "n/a"
    RES.append({"group": group, "title": title, "verdict": v, "z": None if z is None else round(z, 2), "summary": summary})
    print(f"{v:15} | {title}: {summary}", flush=True)


def rec2(group, title, t, horizon, la, lb):
    if t is None:
        return rec(group, title, None, "not enough cases")
    na, nb, ma, mb, z = t
    rec(group, title, z, f"next {horizon}: {la} {ma:+.2f}% vs {lb} {mb:+.2f}% (z {z:+.1f}; {na} vs {nb} cases)")


def rec1(group, title, xs, horizon, what):
    n, m, z = zstat(xs)
    if n < 8:
        return rec(group, title, None, f"not enough events ({n})")
    rec(group, title, z, f"next {horizon}: {what} {m:+.2f}% per event (z {z:+.1f}; {n} events)")


def thin_pos(dates, index, gap):
    keep, last = [], -10 ** 9
    for x in sorted(dates):
        p = index.get_loc(x)
        if p - last >= gap:
            keep.append(x)
            last = p
    return keep


def thin_days(dates, gap_days):
    keep, last = [], None
    for x in sorted(dates):
        if last is None or (x - last).days >= gap_days:
            keep.append(x)
            last = x
    return keep


# ---------------------------------------------------------------- A. ICT COT method on FII positioning
def fii_ict(c):
    G = "A. ICT COT method on FII (Nifty)"
    print(f"\n===== {G} =====")
    d = fii_frame().join(c.rename("c"), how="inner")
    d["r20"] = (d.c.shift(-20) / d.c - 1) * 100
    d["r60"] = (d.c.shift(-60) / d.c - 1) * 100
    sma = d.c.rolling(20).mean()
    d["flow"] = np.where((d.c > sma) & (sma > sma.shift(5)), 1, np.where((d.c < sma) & (sma < sma.shift(5)), -1, 0))
    s = d.dropna(subset=["r60"]).iloc[::60]
    rec2(G, "Zero line: FII net long vs net short", two(s.loc[s.fii > 0, "r60"], s.loc[s.fii < 0, "r60"]),
         "60 days", "net long", "net short")
    for n, name in ((126, "6-month"), (252, "12-month")):
        lo, hi = d.fii.rolling(n).min(), d.fii.rolling(n).max()
        p = (d.fii - lo) / (hi - lo) * 100
        up = d.index[(p >= 50) & (p.shift(1) < 50)]
        dn = d.index[(p < 50) & (p.shift(1) >= 50)]
        eu, ed = thin_pos(up, d.index, 20), thin_pos(dn, d.index, 20)
        rec2(G, f"{name} range nodules (buy vs sell)", two(d.loc[eu, "r20"], d.loc[ed, "r20"]), "20 days", "buy nodule", "sell nodule")
        bu = [x for x in eu if d.at[x, "flow"] == 1]
        bd = [x for x in ed if d.at[x, "flow"] == -1]
        rec2(G, f"{name} nodules + order flow agreeing", two(d.loc[bu, "r20"], d.loc[bd, "r20"]), "20 days",
             "buy nodule + bullish flow", "sell nodule + bearish flow")
    s = d.dropna(subset=["r20"]).iloc[::20]
    rec2(G, "Order flow alone (baseline)", two(s.loc[s.flow == 1, "r20"], s.loc[s.flow == -1, "r20"]), "20 days",
         "bullish flow", "bearish flow")
    for n, name in ((252, "1-year"), (504, "2-year"), (1008, "4-year")):
        lo, hi = d.fii.rolling(n).min(), d.fii.rolling(n).max()
        p = (d.fii - lo) / (hi - lo) * 100
        eh = thin_pos(d.index[p >= 95], d.index, 60)
        el = thin_pos(d.index[p <= 5], d.index, 60)
        rec2(G, f"{name} extreme: FII most long vs most short", two(d.loc[eh, "r60"], d.loc[el, "r60"]), "60 days",
             "FII at top 5%", "FII at bottom 5%")


# ---------------------------------------------------------------- B. ICT COT method on CFTC hedgers
def cot_net(code):
    r = requests.get(COT_URL, params={"$where": f"cftc_contract_market_code='{code}' AND report_date_as_yyyy_mm_dd >= '2006-01-01'",
                                      "$order": "report_date_as_yyyy_mm_dd ASC", "$limit": 5000},
                     timeout=60, headers={"User-Agent": "india-bias-dashboard"})
    r.raise_for_status()
    return pd.Series({pd.Timestamp(x["report_date_as_yyyy_mm_dd"][:10]):
                      float(x.get("comm_positions_long_all") or 0) - float(x.get("comm_positions_short_all") or 0)
                      for x in r.json()}).sort_index()


def cot_ict(c):
    G = "B. ICT COT method on CFTC hedgers (-> Nifty)"
    print(f"\n===== {G} =====")
    for key, (code, name, impact) in COT_MKTS.items():
        try:
            s = cot_net(code)
        except Exception as e:
            rec(G, f"{name}", None, f"fetch failed ({e})")
            continue
        lo, hi = s.rolling(26).min(), s.rolling(26).max()
        p = (s - lo) / (hi - lo) * 100
        up = p.index[(p >= 50) & (p.shift(1) < 50)]
        dn = p.index[(p < 50) & (p.shift(1) >= 50)]
        fav, unf = (up, dn) if impact > 0 else (dn, up)
        rec2(G, f"{name}: 26-week nodule favouring India vs against",
             two(fwd_after(c, thin_days(fav, 28), 20), fwd_after(c, thin_days(unf, 28), 20)), "20 days", "favourable", "unfavourable")
        for n, nm in ((104, "2-year"), (208, "4-year")):
            lo, hi = s.rolling(n).min(), s.rolling(n).max()
            q = (s - lo) / (hi - lo) * 100
            eh, el = q.index[q >= 95], q.index[q <= 5]
            fav, unf = (eh, el) if impact > 0 else (el, eh)
            rec2(G, f"{name}: {nm} extreme favouring India vs against",
                 two(fwd_after(c, thin_days(fav, 91), 65), fwd_after(c, thin_days(unf, 91), 65)), "13 weeks", "favourable", "unfavourable")


# ---------------------------------------------------------------- C. Stock SMT relative strength
def hist(t):
    h = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=True)
    if h is None or h.empty:
        return None
    if h.index.tz is not None:
        h.index = h.index.tz_localize(None)
    h.index = h.index.normalize()
    return h[["Close", "Low"]].dropna()


def stock_rs():
    G = "C. Stock SMT relative strength (Nifty large caps)"
    print(f"\n===== {G} =====")
    ix = hist("^NSEI")
    C, L = {}, {}
    for s in STOCKS:
        try:
            h = hist(s + ".NS")
        except Exception:
            h = None
        if h is None or len(h) < 500:
            print(f"   skipped {s}")
            continue
        C[s], L[s] = h["Close"], h["Low"]
    print(f"   {len(C)} stocks loaded")
    C = pd.DataFrame(C).reindex(ix.index)
    L = pd.DataFrame(L).reindex(ix.index)
    keep = C.index >= "2008-01-01"
    C, L, ixc, ixl = C[keep], L[keep], ix["Close"][keep], ix["Low"][keep]
    ll = lambda low: low.rolling(5).min() < low.shift(5).rolling(15).min()
    idx_ll, st_ll = ll(ixl), ll(L)
    near = C >= 0.95 * C.rolling(252).max()
    for h_ in (20, 60):
        ex = ((C.shift(-h_) / C - 1) * 100).sub((ixc.shift(-h_) / ixc - 1) * 100, axis=0)
        d_rs, d_rsn, win, wout, last = [], [], [], [], -10 ** 9
        for i, d in enumerate(C.index):
            if not idx_ll.iloc[i] or i - last < h_:
                continue
            e = ex.loc[d]
            valid = e.notna() & L.loc[d].notna()
            lowmade = st_ll.loc[d].fillna(False).astype(bool)
            rs, wk = valid & ~lowmade, valid & lowmade
            if rs.sum() < 3 or wk.sum() < 3:
                continue
            last = i
            dd = e[rs].mean() - e[wk].mean()
            d_rs.append(dd)
            (win if d.month in SEASON else wout).append(dd)
            rsn = rs & near.loc[d].fillna(False).astype(bool)
            oth = valid & ~rsn
            if rsn.sum() >= 2 and oth.sum() >= 3:
                d_rsn.append(e[rsn].mean() - e[oth].mean())
        rec1(G, f"RS stocks (no lower low) vs weak stocks", d_rs, f"{h_} days", "RS minus weak, excess vs Nifty")
        rec1(G, f"RS + near 52-week high vs rest", d_rsn, f"{h_} days", "RS-breakout minus rest")
        rec1(G, f"RS stocks inside Feb-May / Oct-Jan windows", win, f"{h_} days", "RS minus weak")
        rec1(G, f"RS stocks outside the windows (Jun-Sep)", wout, f"{h_} days", "RS minus weak")


# ---------------------------------------------------------------- D. Seasonal windows (index)
def seasonal():
    G = "D. Seasonal windows (Sensex)"
    print(f"\n===== {G} =====")
    m = daily("^BSESN")["c"].resample("ME").last().pct_change().dropna() * 100
    rec2(G, "Feb-May + Oct-Jan months vs Jun-Sep months",
         two(m[m.index.month.isin(SEASON)], m[~m.index.month.isin(SEASON)]), "month", "window months", "Jun-Sep months")


# ---------------------------------------------------------------- E. Price structure momentum
def structure():
    G = "E. Price structure momentum"
    print(f"\n===== {G} =====")
    for label, t in (("Nifty", "^NSEI"), ("Sensex", "^BSESN")):
        df = daily(t)
        df = df[(df.index >= "2008-01-01") & (df["h"] > df["l"])]
        for rule, nm, hz in (("W-FRI", "weekly", "week"), ("ME", "monthly", "month")):
            b = df.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
            nxt = (b["c"].shift(-1) / b["c"] - 1) * 100
            up, dn = b["c"] > b["h"].shift(1), b["c"] < b["l"].shift(1)
            rec2(G, f"{label}: {nm} close above prior high vs below prior low", two(nxt[up], nxt[dn]), hz,
                 "closed above prior high", "closed below prior low")


def main():
    c = daily("^NSEI")["c"]
    for fn in (lambda: fii_ict(c), lambda: cot_ict(c), stock_rs, seasonal, structure):
        try:
            fn()
        except Exception as e:
            print(f"   section failed: {e}")
    save("research_v7.json", {"generated": now_ist(), "results": RES})
    passed = [r for r in RES if r["verdict"].startswith("Holds")]
    print(f"\n===== SUMMARY: {len(passed)} of {len(RES)} tests passed =====")
    for r in passed:
        print(f"   {r['verdict']:15} {r['group'][:2]} {r['title']}")


if __name__ == "__main__":
    main()
