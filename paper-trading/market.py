"""Free public market data from Kraken. No API key, read-only."""
import json
import urllib.parse
import urllib.request

BASE = "https://api.kraken.com/0/public"
PAIRS = {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"}
TIMEFRAMES = {"1h": 60, "4h": 240, "1d": 1440}


class MarketDataError(Exception):
    pass


def _get(path, params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = json.load(resp)
    except Exception as e:
        raise MarketDataError(f"Kraken request failed: {e}") from e
    if body.get("error"):
        raise MarketDataError(f"Kraken error: {body['error']}")
    result = body["result"]
    # Result is keyed by Kraken's own pair name (e.g. XXBTZUSD), plus "last".
    return next(v for k, v in result.items() if k != "last")


def pair_for(symbol):
    symbol = symbol.upper()
    if symbol not in PAIRS:
        raise MarketDataError(f"Unknown symbol {symbol!r}; use one of {sorted(PAIRS)}")
    return PAIRS[symbol]


def get_candles(symbol, timeframe="1h", limit=48):
    if timeframe not in TIMEFRAMES:
        raise MarketDataError(f"Unknown timeframe {timeframe!r}; use one of {sorted(TIMEFRAMES)}")
    limit = max(1, min(int(limit), 500))
    rows = _get("OHLC", {"pair": pair_for(symbol), "interval": TIMEFRAMES[timeframe]})
    rows = rows[:-1]  # newest candle is still forming
    return [
        {"time": int(r[0]), "open": float(r[1]), "high": float(r[2]),
         "low": float(r[3]), "close": float(r[4]), "volume": float(r[6])}
        for r in rows[-limit:]
    ]


def latest_price(symbol):
    """Last traded price from the public ticker. Used for fills and marking to market."""
    ticker = _get("Ticker", {"pair": pair_for(symbol)})
    return float(ticker["c"][0])
