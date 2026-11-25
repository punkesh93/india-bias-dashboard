"""Daily OHLC from Yahoo Finance (unofficial). Keeps old data if a ticker fails."""
import sys

import yfinance as yf

from common import load, now_ist, save

TICKERS = {
    "NIFTY": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK", "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "USDINR": "INR=X", "INDIAVIX": "^INDIAVIX",
    "DXY": "DX-Y.NYB", "US10Y": "^TNX",
}


def main():
    old = (load("prices.json", {}) or {}).get("series", {})
    out = {"updated": now_ist(), "series": dict(old)}
    ok = 0
    for key, t in TICKERS.items():
        try:
            df = yf.Ticker(t).history(period="6y", interval="1d", auto_adjust=False)
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            if df.empty:
                raise ValueError("empty")
        except Exception as e:
            print(f"FAILED {key} ({t}): {e} - keeping previous data")
            continue
        out["series"][key] = {"ticker": t, "rows": [
            {"t": i.strftime("%Y-%m-%d"), "o": round(float(r.Open), 4),
             "h": round(float(r.High), 4), "l": round(float(r.Low), 4),
             "c": round(float(r.Close), 4)}
            for i, r in df.iterrows()]}
        ok += 1
        print(f"{key:9} {df.index[-1]:%Y-%m-%d} close {df.Close.iloc[-1]:,.2f}")
    if not out["series"]:
        sys.exit("no price data at all")
    save("prices.json", out)
    print(f"{ok}/{len(TICKERS)} tickers refreshed")


if __name__ == "__main__":
    main()
