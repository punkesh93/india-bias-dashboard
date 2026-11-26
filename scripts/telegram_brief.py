"""Send the daily Market Pulse brief to Telegram (Hinglish)."""
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
LBL = {"Bullish": "Upar", "Bearish": "Neeche", "Neutral": "Saaf nahi"}
VERD = {"Leaning Bullish": ("🟢", "Tezi ki taraf jhukav"),
        "Leaning Bearish": ("🔴", "Mandi ki taraf jhukav"),
        "Two-sided": ("⚪", "Abhi koi saaf disha nahi")}
MACRO = {"Supportive": "Saath de raha hai", "Mixed": "Mila-jula", "Hostile": "Khilaf hai"}


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
    return "Upar" if u > d else "Neeche" if d > u else "Saaf nahi"


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
             f"Bada trend: {big} · Is hafte: {LBL[tf['Weekly']['label']]} · Aaj: {LBL[tf['Daily']['label']]}"]
    I = ict.get("instruments", {}).get(key)
    if I:
        r = I["ranges"][1]
        pos = r["pos"]
        zone = "mehnga zone" if pos >= 75 else "thoda mehnga" if pos >= 50 else "thoda sasta" if pos >= 25 else "sasta zone"
        lines.append(f"💰 Price: {zone} (40-din range ka {pos:.0f}%, beech {inr(r['eq'])})")
        d = I.get("draw", {})
        if show_levels() and d.get("target"):
            def lv(x):
                if not x:
                    return "–"
                return f"{inr(x['low'])}–{inr(x['high'])}" if x.get("low") is not None else inr(x["price"])
            lines.append(f"🧲 Magnet {lv(d.get('target'))} · Entry zone {lv(d.get('entry'))} · Galat {lv(d.get('invalidation'))}")
    return "\n".join(lines)


def players(poi):
    rows = poi.get("rows", [])
    if len(rows) < 21 or "FII" not in rows[-1] or "Client" not in rows[-1]:
        return []
    net = lambda r, g: r[g]["fil"] - r[g]["fis"]
    f, df = net(rows[-1], "FII"), net(rows[-1], "FII") - net(rows[-21], "FII")
    dc = net(rows[-1], "Client") - net(rows[-21], "Client")
    side = "net short" if f < 0 else "net long"
    act = ("short cover" if f < 0 else "aur kharida") if df > 0 else ("naye short" if f < 0 else "long kam kiye")
    return [f"🏦 FII: {side} {inr(abs(f))} · 20 din: {'+' if df >= 0 else '−'}{lakh(df)} ({act})",
            f"👥 Retail: 20 din: {'+' if dc >= 0 else '−'}{lakh(dc)} ({'khareed rahe hain' if dc > 0 else 'bech rahe hain'})"]


def expiry_note():
    wd = (datetime.now(IST) + timedelta(days=1)).weekday()  # tomorrow: Mon=0
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
    parts.append(f"🌍 Global hawa: {MACRO.get(story.get('macro', {}).get('summary'), 'Mila-jula')}")
    exp = expiry_note()
    if exp:
        parts.append(exp)
    parts += ["", index_block("NIFTY", bias, story, ict, prices, False),
              index_block("BANKNIFTY", bias, story, ict, prices, False), "",
              f'🔗 <a href="{SITE}">Pura analysis dekho</a>',
              "<i>Sirf shiksha ke liye · trading advice nahi</i>"]
    text = "\n".join(p for p in parts if p is not None)
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, timeout=30) as r:
        res = json.loads(r.read().decode())
    print("Telegram:", "sent" if res.get("ok") else res)


if __name__ == "__main__":
    main()
