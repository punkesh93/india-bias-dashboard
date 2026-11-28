"""Evening Market Pulse brief: focus levels, traps, range meaning. No buy/sell, no forecasts."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from common import load

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
SITE = os.environ.get("SITE_URL", "https://punkesh93.github.io/india-bias-dashboard/")
IST = timezone(timedelta(hours=5, minutes=30))
NAMES = {"SENSEX": "Sensex", "NIFTY": "Nifty 50", "BANKNIFTY": "Bank Nifty"}


def inr(x, d=0):
    if x is None:
        return "-"
    s = f"{abs(x):.{d}f}"
    i, _, f = s.partition(".")
    if len(i) > 3:
        i = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", i[:-3]) + "," + i[-3:]
    return ("-" if x < 0 else "") + i + ("." + f if f else "")


def send(text):
    if os.environ.get("DRY_RUN"):
        print(text)
        return
    if not TOKEN or not CHAT:
        print("Telegram secrets not set - skipping.")
        return
    data = urllib.parse.urlencode({"chat_id": CHAT, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, timeout=30) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        res = json.loads(body) if body.startswith("{") else {"ok": False, "description": body}
    print("Telegram:", "sent" if res.get("ok") else res)


def daily_line(d, S):
    if not d or d.get("kind") in (None, "pending"):
        return None
    side = "high" if d.get("side") == "PDH" else "low"
    k = d["kind"]
    if k == "rejection":
        return f"🪤 Aaj daily trap: kal ka {side} {inr(d['level'])} sweep + rejection → din {'range ke andar close ✓' if d.get('back_inside') else 'beyond close ✗'} (historically {S['daily_rej']})"
    if k == "held":
        return f"🚀 Aaj opening breakout hold: kal ka {side} {inr(d['level'])} toot ke hold hua (trap nahi)"
    if k == "both":
        return "↔️ Aaj outside opening (kal ka high aur low dono toote)"
    return None


def weekly_line(w, S):
    if not w or w.get("kind") in (None, "pending", "inside"):
        return None
    side = "high" if w.get("side") == "PWH" else "low"
    if w["kind"] == "rejection":
        return f"🪤 Weekly trap active: last week ka {side} {inr(w['level'])} sweep + rejection → historically {S['weekly_rej']} week range ke andar close (abhi price range ke {'andar' if w.get('back_inside') else 'bahar'})"
    if w["kind"] == "held":
        return f"🚀 Weekly breakout hold: last week ka {side} {inr(w['level'])} toot ke hold hua (trap nahi)"
    return None


def px(prices, key):
    rows = ((prices.get("series") or {}).get(key) or {}).get("rows", [])
    if len(rows) < 2:
        return None, None
    return rows[-1]["c"], (rows[-1]["c"] / rows[-2]["c"] - 1) * 100


def focus_line(F, short=False):
    a = ((F or {}).get("above") or [None])[0]
    b = ((F or {}).get("below") or [None])[0]
    seg = []
    if a:
        seg.append(f"upar {inr(a['price'])}" + ("" if short else f" {a['name']} ({a['dist']:+.1f}%, kal touch ~{a['p1']}%)"))
    if b:
        seg.append(f"neeche {inr(b['price'])}" + ("" if short else f" {b['name']} ({b['dist']:+.1f}%, kal touch ~{b['p1']}%)"))
    return " · ".join(seg)


def main():
    T = load("traps.json", {}) or {}
    prices = load("prices.json", {}) or {}
    S = T.get("stats") or {}
    I = T.get("instruments") or {}
    parts = [f"📊 <b>Market Pulse</b> · {datetime.now(IST):%d %b %Y}", ""]
    K = I.get("SENSEX")
    if K:
        c, chg = px(prices, "SENSEX")
        if c:
            parts.append(f"<b>Sensex</b> {inr(c, 2)} ({chg:+.2f}%)")
        F = K.get("focus") or {}
        fl = focus_line(F)
        if fl:
            parts.append(f"🎯 Focus: {fl}")
        for line in (daily_line(K.get("daily"), S), weekly_line(K.get("weekly"), S)):
            if line:
                parts.append(line)
        parts.append(f"⏱️ Kal 9:15–10:15: ~{S.get('first_hour', '78%')} din, din ka high ya low pehle ghante mein banta hai.")
        r = F.get("range1y")
        if r:
            near = "upar (1-year high)" if r["to_high"] < -r["to_low"] else "neeche (1-year low)"
            parts.append(f"📏 1-year range ka {r['pos']:.0f}%: 1-year high {inr(r['high'])} sirf {r['to_high']:+.1f}% door (20 din mein touch ~{r['p_high20']}%). Paas wali badi liquidity {near} — wahan price ka reaction dekho, position khud signal nahi.")
    parts.append("")
    LAB = {"rejection": "trap 🪤", "held": "breakout hold 🚀", "both": "outside opening", "inside": "no trap"}
    for key in ("NIFTY", "BANKNIFTY"):
        K2 = I.get(key)
        c, chg = px(prices, key)
        if K2 and c:
            d = K2.get("daily") or {}
            parts.append(f"<b>{NAMES[key]}</b> {inr(c, 2)} ({chg:+.2f}%) · {LAB.get(d.get('kind'), '-')} · focus {focus_line(K2.get('focus'), short=True)}")
    parts += ["", f'🔗 <a href="{SITE}">Full market map dekho</a>', "<i>Sirf education · koi buy/sell advice ya prediction nahi</i>"]
    send("\n".join(parts))


if __name__ == "__main__":
    main()
