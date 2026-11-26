"""Robustness check for the opening rules: split halves + trading costs (adds robust_* tests to backtest.json)."""
import math

from backtest import TICKERS, hourly
from common import load, save

COSTS = [("futures-like cost (0.03%)", 0.0003), ("conservative cost (0.10%)", 0.0010)]
CLAIMS = {
    "follow": ("Robustness: follow a first-hour break that holds",
               "Following a first-hour PDH/PDL break that closes beyond stays profitable in both halves of the sample and after costs."),
    "fade": ("Robustness: fade a first-hour sweep that closes back inside",
             "Fading a first-hour PDH/PDL sweep that closes back inside stays profitable in both halves of the sample and after costs."),
}


def sim(rule, side, entry, stop, target, rest, close, day):
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    if target is not None and ((side == "long" and target <= entry) or (side == "short" and target >= entry)):
        target = None
    r = None
    for _, b in rest.iterrows():
        if side == "long":
            if b["l"] <= stop:
                r = -1.0; break
            if target is not None and b["h"] >= target:
                r = (target - entry) / risk; break
        else:
            if b["h"] >= stop:
                r = -1.0; break
            if target is not None and b["l"] <= target:
                r = (entry - target) / risk; break
    if r is None:
        r = ((close - entry) if side == "long" else (entry - close)) / risk
    return {"rule": rule, "date": str(day), "r": float(r), "risk": float(risk), "entry": float(entry)}


def collect(h):
    out, prev = [], None
    for day, g in h.groupby(h.index.date):
        if len(g) < 5:
            continue
        if prev is not None:
            pdh, pdl = prev["h"].max(), prev["l"].min()
            eq = (pdh + pdl) / 2
            f, rest, close = g.iloc[0], g.iloc[1:], g["c"].iloc[-1]
            if f["h"] > pdh:
                out.append(sim("fade", "short", f["c"], f["h"], eq, rest, close, day) if f["c"] < pdh
                           else sim("follow", "long", f["c"], f["l"], None, rest, close, day))
            if f["l"] < pdl:
                out.append(sim("fade", "long", f["c"], f["l"], eq, rest, close, day) if f["c"] > pdl
                           else sim("follow", "short", f["c"], f["h"], None, rest, close, day))
        prev = g
    return [t for t in out if t]


def stt(rs):
    n = len(rs)
    if n == 0:
        return 0, 0.0, 0.0, 0.0
    m = sum(rs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in rs) / (n - 1)) if n > 1 else 0.0
    z = m / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return n, 100 * sum(x > 0 for x in rs) / n, m, z


def main():
    bt = load("backtest.json", {}) or {}
    inst = bt.get("instruments", {})
    for key, t in TICKERS.items():
        try:
            h = hourly(t)
        except Exception as e:
            print(f"{key}: hourly fetch failed ({e})")
            continue
        if h is None:
            continue
        trades = collect(h)
        tests = [x for x in inst.get(key, []) if not x["id"].startswith("robust_")]
        for rule in ("follow", "fade"):
            L = sorted([x for x in trades if x["rule"] == rule], key=lambda x: x["date"])
            if len(L) < 20:
                continue
            mid = len(L) // 2
            rows = []

            def row(name, rs):
                n, w, m, z = stt(rs)
                rows.append([name, n, f"{w:.0f}%", f"{m:+.2f}R", f"{z:+.1f}"])
                return m, z

            row("All (no costs)", [x["r"] for x in L])
            m1, _ = row(f"First half ({L[0]['date']} to {L[mid - 1]['date']})", [x["r"] for x in L[:mid]])
            m2, _ = row(f"Second half ({L[mid]['date']} to {L[-1]['date']})", [x["r"] for x in L[mid:]])
            cres = [row(f"After {name}", [x["r"] - c * x["entry"] / x["risk"] for x in L]) for name, c in COSTS]
            (mc1, zc1), (mc2, zc2) = cres
            both = m1 > 0 and m2 > 0
            v = "Holds" if both and zc1 >= 2 else "Weak" if both and mc1 > 0 else "Doesn't hold"
            stop_pct = 100 * sum(x["risk"] / x["entry"] for x in L) / len(L)
            title, claim = CLAIMS[rule]
            tests.append({"id": f"robust_{rule}", "title": title, "title_hi": "", "claim": claim, "verdict": v,
                          "summary": f"Halves: {m1:+.2f}R and {m2:+.2f}R ({'both positive' if both else 'not both positive'}). "
                                     f"After futures-like costs {mc1:+.2f}R per trade (z {zc1:+.1f}); after conservative costs {mc2:+.2f}R. "
                                     f"Average stop distance {stop_pct:.2f}% of price.",
                          "hi": "", "cols": ["Subset", "Trades", "Win rate", "Avg R", "z-score"], "rows": rows,
                          "sample": "2 years of hourly data; options theta/IV not modelled; multiple tests were run, so treat Weak results with caution"})
            print(f"\n{key} · {title}  ->  {v}")
            for r in rows:
                print(f"   {r[0]:48} trades={r[1]:>4}  win={r[2]:>4}  avg={r[3]:>7}  z={r[4]:>5}")
        inst[key] = tests
    bt["instruments"] = inst
    save("backtest.json", bt)


if __name__ == "__main__":
    main()
