"""Evening Market Pulse brief: descriptive map + proven facts only."""
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


ST = {"above": "above prior high", "below": "below prior low", "inside": "inside"}


def lv(K, name):
    for x in K.get("levels", []):
        if x["name"] == name:
            return inr(x["price"])
    return "-"


def daily_line(d, S):
    if not d or d.get("kind") in (None, "pending"):
        return None
    side = "high" if d.get("side") == "PDH" else "low"
    k = d["kind"]
    if k == "rejection":
        res = "range ke andar close ✓" if d.get("back_inside") else "beyond close ✗"
        return f"🪤 Daily trap: pehle ghante ne kal ka {side} {inr(d['level'])} sweep karke wapas andar close kiya → aaj {res} (historically {S['daily_rej']})"
    if k == "held":
        res = "wapas andar close" if d.get("back_inside") else "beyond close"
        return f"🚀 Opening breakout hold: kal ka {side} {inr(d['level'])} toot ke hold hua (trap nahi) → aaj {res}"
    if k == "both":
        return "↔️ Outside opening: pehle ghante ne kal ka high aur low dono tode"
    return "Daily: koi opening trap nahi (pehla ghanta kal ki range ke andar raha)"


def weekly_line(w, S):
    if not w or w.get("kind") in (None, "pending"):
        return None
    side = "high" if w.get("side") == "PWH" else "low"
    k = w["kind"]
    if k == "rejection":
        now = "andar" if w.get("back_inside") else "bahar"
        return f"🪤 Weekly trap active: week ke pehle din ne last week ka {side} {inr(w['level'])} sweep karke wapas close kiya → historically {S['weekly_rej']} week range ke andar close (abhi price range ke {now})"
    if k == "held":
        return f"🚀 Weekly breakout hold: last week ka {side} {inr(w['level'])} toot ke hold hua (trap nahi; historically sirf {S['weekly_brk']} wapas andar)"
    if k == "both":
        return "↔️ Week ke pehle din ne last week ka high aur low dono tode"
    return "Weekly: koi trap nahi (week ka pehla din last week ki range ke andar)"


def px(prices, key):
    rows = ((prices.get("series") or {}).get(key) or {}).get("rows", [])
    if len(rows) < 2:
        return None, None
    return rows[-1]["c"], (rows[-1]["c"] / rows[-2]["c"] - 1) * 100


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
        st = K.get("structure", {})
        parts.append("Structure: " + " · ".join(f"{k} {ST[v['state']]}" for k, v in st.items() if k in ("Daily", "Weekly", "Monthly")))
        parts.append(f"🗺️ Kal ke key levels: aaj ka high {lv(K, 'Today high')} · aaj ka low {lv(K, 'Today low')} · week high {lv(K, 'This week high')} · week low {lv(K, 'This week low')}")
        for line in (daily_line(K.get("daily"), S), weekly_line(K.get("weekly"), S)):
            if line:
                parts.append(line)
        parts.append(f"⏱️ Kal 9:15–10:15 pe dhyan: ~{S.get('first_hour', '78%')} din, din ka high ya low pehle ghante mein banta hai.")
        b, r3 = S.get("base", {}), K.get("range3y", {})
        pos = r3.get("pos", 50)
        zone = "Premium zone" if pos >= 75 else "upper half" if pos >= 50 else "lower half" if pos >= 25 else "Discount zone"
        if b.get("12"):
            parts.append(f"🔭 Big picture: since {b['since']}, 12 months baad Sensex {b['12']['up']}% time upar (avg {b['12']['avg']:+.1f}%). Abhi price 3-year range ke {pos:.0f}% pe ({zone}) — sirf position, prediction nahi.")
    parts.append("")
    LAB = {"rejection": "daily trap 🪤", "held": "breakout hold 🚀", "both": "outside opening", "inside": "no trap"}
    for key in ("NIFTY", "BANKNIFTY"):
        K2 = I.get(key)
        c, chg = px(prices, key)
        if K2 and c:
            d = K2.get("daily") or {}
            parts.append(f"<b>{NAMES[key]}</b> {inr(c, 2)} ({chg:+.2f}%) · {LAB.get(d.get('kind'), '-')}")
    parts += ["", f'🔗 <a href="{SITE}">Full market map dekho</a>', "<i>Sirf education · koi buy/sell advice ya prediction nahi</i>"]
    send("\n".join(parts))


if __name__ == "__main__":
    main()
