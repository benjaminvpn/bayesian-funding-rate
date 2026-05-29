"""
从 Bybit 公开 API 获取数据
使用浏览器伪装头避免 403
"""

import json
import urllib.request
import urllib.error
import numpy as np

BYBIT_BASE = "https://api.bybit.com"

# 浏览器级请求头，绕过 CDN 风控
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.bybit.com",
    "Referer": "https://www.bybit.com/",
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  [!] HTTP {e.code}: {url[:60]}...")
        return {}
    except Exception as e:
        print(f"  [!] 请求失败: {url[:60]}... -> {e}")
        return {}


def get_funding_rate(symbol: str = "BTCUSDT") -> float:
    data = fetch_json(f"{BYBIT_BASE}/v5/market/tickers?category=linear&symbol={symbol}")
    ticker = data.get("result", {}).get("list", [{}])[0]
    rate = float(ticker.get("fundingRate", 0))
    return round(rate * 3 * 365 * 100, 4)


def get_funding_rate_history(symbol: str = "BTCUSDT", limit: int = 50) -> np.ndarray:
    data = fetch_json(f"{BYBIT_BASE}/v5/market/funding/history?category=linear&symbol={symbol}&limit={limit}")
    items = data.get("result", {}).get("list", [])
    if not items:
        return np.array([])
    return np.array([float(i["fundingRate"]) * 3 * 365 * 100 for i in items])


def get_all_data(symbol: str = "BTCUSDT") -> dict:
    print(f"  [*] 获取 {symbol} 数据 (Bybit)...")

    rate = get_funding_rate(symbol)
    print(f"      资金费率: {rate}% 年化")

    ticker_data = fetch_json(f"{BYBIT_BASE}/v5/market/tickers?category=linear&symbol={symbol}")
    ticker = ticker_data.get("result", {}).get("list", [{}])[0]
    price = float(ticker.get("lastPrice", 0))
    volume = float(ticker.get("volume24h", 0))
    turnover = float(ticker.get("turnover24h", 0))
    print(f"      价格: ${price:,.2f}  成交量: {volume:,.0f}")

    oi_data = fetch_json(f"{BYBIT_BASE}/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min&limit=50")
    oi_items = oi_data.get("result", {}).get("list", [])
    if len(oi_items) >= 10:
        vals = np.array([float(i["openInterest"]) for i in oi_items])
        oi_z = float((vals[-1] - np.mean(vals[:-1])) / (np.std(vals[:-1]) + 1e-8))
    else:
        oi_z = 0.0
    print(f"      OI Z-score: {oi_z:.3f}")

    vol_ratio = round(volume / (turnover / price), 2) if price > 0 and turnover > 0 else 1.0

    trades = fetch_json(f"{BYBIT_BASE}/v5/market/recent-trade?category=linear&symbol={symbol}&limit=100")
    trade_list = trades.get("result", {}).get("list", [])
    if trade_list:
        buys = sum(1 for t in trade_list if t.get("side", "") == "Buy")
        liq_ratio = round(buys / len(trade_list), 2)
    else:
        liq_ratio = 1.0

    return {
        "funding_rate": rate / 100,
        "price": price,
        "oi_change": round(oi_z, 3),
        "volume_ratio": vol_ratio,
        "liq_long_ratio": liq_ratio,
    }


def get_mock_data(symbol: str = "BTCUSDT") -> dict:
    mock = {
        "BTCUSDT": {"funding_rate": 0.06, "price": 105000, "oi_change": 1.2, "volume_ratio": 1.8, "liq_long_ratio": 0.4},
        "ETHUSDT": {"funding_rate": 0.04, "price": 3800, "oi_change": 0.8, "volume_ratio": 1.3, "liq_long_ratio": 0.7},
    }
    return mock.get(symbol, mock["BTCUSDT"])
