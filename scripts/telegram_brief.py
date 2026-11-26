"""Send the daily Market Pulse brief to Telegram (easy Hinglish, English market terms)."""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from common import load

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
SITE = os.environ.get("SITE_URL", "https://punkesh93.github.io/india-bias-dashboard/")
IST = timezone(timedelta(hours=5, minutes=30))
NAMES = {"SENSEX": "Sensex", "NIFTY": "Nifty 50", "BANKNIFTY": "Bank Nifty"}
VERD = {"Leaning Bullish": ("🟢", "Bullish bias"), "Leaning Bearish": ("🔴", "Bearish bias"),
        "Two-sided": ("⚪", "Sideways (direction clear nahi)")}
MACRO = {"Supportive": "Supportive", "Mixed": "Mixed", "Hostile": "Negative"}


def inr(x, d=0):
    s = f"{abs(x):.{d}f}"
    i, _, f = s.partition(".")
    if len(i) > 3:
        i = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", i[:-3]) + "," + i[-3:]
    return ("-" if x < 0 else "") + i + ("." + f if f else "")


def lakh(v):
    a = abs(v)
    return f"{a / 1e5:.2f} lakh" if a >= 1e5 else inr(a)


def show_levels():
    try:
        cfg = open(os.path.join(os.path.dirname(__file__), "..", "config.js"), encoding="utf-8").read()
        return not re.search(r"showTradeLevels\s*:\s*false", cfg)
    except OSError:
        return True


def majority(labels):
    u, d = labels.count("Bullish"), labels.count("Bearish")
    return "Bullish" if u > d else "Bearish" if d > u else "Neutral"


def index_block(key, bias, story, ict, prices, full):
    b = bias.get("instruments", {}).get(key)
    s = story.get("instruments", {}).get(key)
    rows = prices.get("series", {}).get(key, {}).get("rows", [])
    if not b or not s or len(rows) < 2:
        return ""
    c, chg = rows[-1]["c"], (rows[-1]["c"] / rows[-2]["c"] - 1) * 100
    icon, verdict = VERD.get(s["verdict"], ("⚪", s["verdict"]))
    head = f"<b>{NAMES[key]}</b> {inr(c, 2)} ({chg:+.2f}%)"
    if not full:
        return f"{head} · {icon} {verdict}"
    tf = b["timeframes"]
    big = majority([tf[t]["label"] for t in ("Yearly", "Quarterly", "Monthly")])
    lines = [head, f"{icon} {verdict}",
             f"Trend: Big picture {big} · Weekly {tf['Weekly']['label']} · Daily {tf['Daily']['label']}"]
    I = ict.get("instruments", {}).get(key)
    if I:
        r = I["ranges"][1]
        pos = r["pos"]
        zone = ("Premium zone" if pos >= 75 else "upper half (thoda Premium)" if pos >= 50
                else "lower half (thoda Discount)" if pos >= 25 else "Discount zone")
        lines.append(f"💰 Price: {zone} (40-day range ka {pos:.0f}%, equilibrium {inr(r['eq'])})")
        d = I.get("draw", {})
        if show_levels() and d.get("target"):
            def lv(x):
                if not x:
                    return "–"
                return f"{inr(x['low'])}–{inr(x['high'])}" if x.get("low") is not None else inr(x["price"])
            lines.append(f"🎯 Target {lv(d.get('target'))} · Entry zone {lv(d.get('entry'))} · Invalidation {lv(d.get('invalidation'))}")
    return "\n".join(lines)


def players(poi):
    rows = poi.get("rows", [])
    if len(rows) < 21 or "FII" not in rows[-1] or "Client" not in rows[-1]:
        return []
    net = lambda r, g: r[g]["fil"] - r[g]["fis"]
    f, df = net(rows[-1], "FII"), net(rows[-1], "FII") - net(rows[-21], "FII")
    dc = net(rows[-1], "Client") - net(rows[-21], "Client")
    side = "net short" if f < 0 else "net long"
    act = ("short covering" if f < 0 else "buying") if df > 0 else ("new shorts" if f < 0 else "long exit")
    return [f"🏦 FII: {side} {inr(abs(f))} · 20 days: {'+' if df >= 0 else '−'}{lakh(df)} ({act})",
            f"👥 Retail: 20 days: {'+' if dc >= 0 else '−'}{lakh(dc)} ({'buying' if dc > 0 else 'selling'})"]


def expiry_note():
    wd = (datetime.now(IST) + timedelta(days=1)).weekday()
    return {1: "⚠️ Kal Nifty weekly expiry", 3: "⚠️ Kal Sensex weekly expiry"}.get(wd)


def main():
    if not TOKEN or not CHAT:
        print("Telegram secrets not set - skipping.")
        return
    bias, story, ict = load("bias.json", {}) or {}, load("story.json", {}) or {}, load("ict.json", {}) or {}
    prices, poi = load("prices.json", {}) or {}, load("participant_oi.json", {}) or {}
    parts = [f"📊 <b>Market Pulse</b> · {datetime.now(IST):%d %b %Y}", "",
             index_block("SENSEX", bias, story, ict, prices, True), ""]
    parts += players(poi)
    parts.append(f"🌍 Global mood: {MACRO.get(story.get('macro', {}).get('summary'), 'Mixed')}")
    exp = expiry_note()
    if exp:
        parts.append(exp)
    parts += ["", index_block("NIFTY", bias, story, ict, prices, False),
              index_block("BANKNIFTY", bias, story, ict, prices, False), "",
              f'🔗 <a href="{SITE}">Full analysis dekho</a>',
              "<i>Sirf education ke liye · trading advice nahi</i>"]
    text = "\n".join(p for p in parts if p is not None)
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, timeout=30) as r:
        res = json.loads(r.read().decode())
    print("Telegram:", "sent" if res.get("ok") else res)


if __name__ == "__main__":
    main()
