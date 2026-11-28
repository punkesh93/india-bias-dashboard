"""Focus levels: nearest untouched liquidity above/below, with volatility-calibrated touch chances."""
import numpy as np

from backtest import daily

TICK = {"SENSEX": "^BSESN", "NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
GRID = np.round(np.arange(0, 30.01, 0.1), 2)
RANK = {"1-year": 6, "quarter": 5, "month": 4, "week": 3, "today": 1}


def excursion(d):
    d = d[(d.index >= "2008-01-01") & (d["h"] > d["l"])]
    adr = (d["h"] - d["l"]).rolling(14).mean()
    out = {}
    for k in (1, 5, 20):
        hi = d["h"].iloc[::-1].rolling(k).max().iloc[::-1].shift(-1)
        lo = d["l"].iloc[::-1].rolling(k).min().iloc[::-1].shift(-1)
        up = ((hi - d["c"]) / adr).dropna().values
        dn = ((d["c"] - lo) / adr).dropna().values
        out[f"up{k}"] = [round(float((up >= g).mean()), 3) for g in GRID]
        out[f"dn{k}"] = [round(float((dn >= g).mean()), 3) for g in GRID]
    return out


def tables():
    out = {}
    for key, t in TICK.items():
        try:
            out[key] = excursion(daily(t))
        except Exception as e:
            print(f"excursion table {key} failed: {e}")
    return out


def prob(tbl, side, k, x):
    i = int(round(min(max(float(x), 0.0), 30.0) / 0.1))
    return tbl[f"{side}{k}"][i]


def focus(df, tbl):
    if not tbl or len(df) < 260:
        return None
    c = float(df["c"].iloc[-1])
    adr = float((df["h"] - df["l"]).iloc[-14:].mean())
    pw_, pm_, pq_ = df.index.to_period("W-FRI"), df.index.to_period("M"), df.index.to_period("Q")
    cur = lambda per: df[per == per[-1]]

    def prev(per):
        p = per[per < per[-1]]
        return df[per == p.max()] if len(p) else None

    tw, tm, tq = cur(pw_), cur(pm_), cur(pq_)
    lw, lm, lq = prev(pw_), prev(pm_), prev(pq_)
    y, t = df.iloc[-252:], df.iloc[-1]
    C = []

    def add(name, tf, price, taken=False):
        C.append({"name": name, "tf": tf, "price": round(float(price), 2), "taken": bool(taken)})

    add("Today's high", "today", t["h"]); add("Today's low", "today", t["l"])
    add("This week's high", "week", tw["h"].max()); add("This week's low", "week", tw["l"].min())
    for lab, tf, P, Cur in (("Last week's", "week", lw, tw), ("Last month's", "month", lm, tm), ("Last quarter's", "quarter", lq, tq)):
        if P is not None:
            add(f"{lab} high", tf, P["h"].max(), Cur["h"].max() > P["h"].max())
            add(f"{lab} low", tf, P["l"].min(), Cur["l"].min() < P["l"].min())
    add("1-year high", "1-year", y["h"].max()); add("1-year low", "1-year", y["l"].min())
    C = sorted([x for x in C if not x["taken"]], key=lambda x: -RANK[x["tf"]])
    kept = []
    for x in C:
        dup = next((k for k in kept if abs(k["price"] / x["price"] - 1) < 0.0015), None)
        if dup:
            dup.setdefault("also", []).append(x["name"])
        else:
            kept.append(x)
    for x in kept:
        side = "up" if x["price"] > c else "dn"
        xa = abs(x["price"] - c) / adr
        x.update({"dir": "above" if side == "up" else "below", "dist": round((x["price"] / c - 1) * 100, 2),
                  "adr": round(xa, 1), "p1": int(round(100 * prob(tbl, side, 1, xa))),
                  "p5": int(round(100 * prob(tbl, side, 5, xa))), "p20": int(round(100 * prob(tbl, side, 20, xa)))})
        x.pop("taken", None)
    above = sorted([x for x in kept if x["dir"] == "above"], key=lambda x: x["price"])[:3]
    below = sorted([x for x in kept if x["dir"] == "below"], key=lambda x: -x["price"])[:3]
    yl, yh = float(y["l"].min()), float(y["h"].max())
    r = {"low": round(yl, 2), "high": round(yh, 2), "pos": round((c - yl) / (yh - yl) * 100, 1) if yh > yl else 50.0,
         "to_high": round((yh / c - 1) * 100, 2), "to_low": round((yl / c - 1) * 100, 2),
         "p_high5": int(round(100 * prob(tbl, "up", 5, (yh - c) / adr))), "p_high20": int(round(100 * prob(tbl, "up", 20, (yh - c) / adr))),
         "p_low5": int(round(100 * prob(tbl, "dn", 5, (c - yl) / adr))), "p_low20": int(round(100 * prob(tbl, "dn", 20, (c - yl) / adr)))}
    return {"close": round(c, 2), "adr": round(adr, 1), "adr_pct": round(adr / c * 100, 2), "above": above, "below": below, "range1y": r}
