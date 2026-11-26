"""Morning Trap Watch alert (~10:45 IST). Sends only when a first-hour trap or held breakout forms (FORCE=1 always sends)."""
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



def main():
    T = load("traps.json", {}) or {}
    S = T.get("stats") or {}
    today = datetime.now(IST).strftime("%Y-%m-%d")
    force = bool(os.environ.get("FORCE"))
    lines, hit = [], False
    for key in ("SENSEX", "NIFTY", "BANKNIFTY"):
        d = ((T.get("instruments") or {}).get(key) or {}).get("daily") or {}
        if d.get("date") != today and not force:
            continue
        side = "high" if d.get("side") == "PDH" else "low"
        rng = f"first hour {inr(d.get('fh_low'))}–{inr(d.get('fh_high'))}" if d.get("fh_high") else "first hour pending"
        k = d.get("kind")
        if k == "rejection":
            hit = True
            lines.append(f"🪤 <b>{NAMES[key]}</b>: kal ka {side} {inr(d.get('level'))} sweep hua aur pehla ghanta wapas andar close hua — <b>trap</b> ({rng})")
        elif k == "held":
            hit = True
            lines.append(f"🚀 <b>{NAMES[key]}</b>: kal ka {side} {inr(d.get('level'))} toota aur beyond hold kiya — trap nahi ({rng})")
        elif force:
            lines.append(f"• <b>{NAMES[key]}</b>: {'koi opening sweep nahi' if k == 'inside' else (k or 'no data')} ({rng})")
    if not hit and not force:
        print("No first-hour trap today - nothing sent.")
        return
    msg = [f"🪤 <b>Trap Watch</b> · {datetime.now(IST):%d %b %H:%M}", ""] + (lines or ["Aaj ka first-hour data abhi available nahi."]) + [
        "",
        f"Data (2 saal): rejection ke baad {S.get('daily_rej', '71%')} din range ke andar close hua; breakout hold par sirf {S.get('daily_brk', '26%')}.",
        f"~{S.get('first_hour', '78%')} din, din ka high ya low pehle ghante mein ban chuka hota hai.",
        f'🔗 <a href="{SITE}">Trap Watch dekho</a>',
        "<i>Sirf education · koi buy/sell advice nahi</i>"]
    send("\n".join(msg))


if __name__ == "__main__":
    main()
