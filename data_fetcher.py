"""
从 Bybit 公开 API 获取数据
无需 API key，纯公开数据，不限地区
"""

import json
import urllib.request
import urllib.error
import numpy as np
from typing import Optional

BYBIT_BASE = "https://api.bybit.com"


def fetch_json(url: str) -> dict:
    """安全的 GET 请求"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [!] 请求失败: {url[:80]}... -> {e}")
        return {}


def get_ticker(symbol: str = "BTCUSDT") -> dict:
    """获取当前ticker：价格、费率、成交量"""
    url = f"{BYBIT_BASE}/v5/market/tickers?category=linear&symbol={symbol}"
    data = fetch_json(url)
    if data.get("retCode") == 0 and data.get("result", {}).get("list"):
        return data["result"]["list"][0]
    return {}


def get_funding_rate(symbol: str = "BTCUSDT") -> float:
    """获取当前资金费率（年化百分比）"""
    ticker = get_ticker(symbol)
    rate_str = ticker.get("fundingRate", "0")
    try:
        rate = float(rate_str)
    except (ValueError, TypeError):
        return 0.0
    # Bybit 资金费率也是每8小时，年化 = 费率 * 3 * 365 * 100
    annualized = rate * 3 * 365 * 100
    return round(annualized, 4)


def get_funding_rate_history(symbol: str = "BTCUSDT", limit: int = 50) -> np.ndarray:
    """获取历史费率用于校准先验"""
    url = f"{BYBIT_BASE}/v5/market/funding/history?category=linear&symbol={symbol}&limit={limit}"
    data = fetch_json(url)
    if data.get("retCode") != 0 or not data.get("result", {}).get("list"):
        return np.array([])
    items = data["result"]["list"]
    rates = [float(item["fundingRate"]) * 3 * 365 * 100 for item in items]
    return np.array(rates)


def get_open_interest_history(symbol: str = "BTCUSDT", limit: int = 50) -> np.ndarray:
    """获取持仓量历史（用于计算变化率）"""
    url = f"{BYBIT_BASE}/v5/market/open-interest?category=linear&symbol={symbol}&intervalTime=5min&limit={limit}"
    data = fetch_json(url)
    if data.get("retCode") != 0 or not data.get("result", {}).get("list"):
        return np.array([])
    items = data["result"]["list"]
    oi_values = [float(item["openInterest"]) for item in items]
    return np.array(oi_values)


def get_recent_trades(symbol: str = "BTCUSDT", limit: int = 100) -> list:
    """获取最近成交（用于估算买卖比例）"""
    url = f"{BYBIT_BASE}/v5/market/recent-trade?category=linear&symbol={symbol}&limit={limit}"
    data = fetch_json(url)
    if data.get("retCode") == 0 and data.get("result", {}).get("list"):
        return data["result"]["list"]
    return []


def compute_oi_zscore(symbol: str = "BTCUSDT") -> float:
    """计算 OI 变化的 Z-score"""
    oi_hist = get_open_interest_history(symbol, 50)
    if len(oi_hist) < 10:
        return 0.0
    current = oi_hist[-1]
    mean_oi = np.mean(oi_hist[:-1])
    std_oi = np.std(oi_hist[:-1])
    if std_oi < 1e-8:
        return 0.0
    return float((current - mean_oi) / std_oi)


def get_mock_data(symbol: str = "BTCUSDT") -> dict:
    """离线调试用：返回模拟数据"""
    mock = {
        "BTCUSDT": {"funding_rate": 0.06, "price": 105000, "oi_change": 1.2, "volume_ratio": 1.8, "liq_long_ratio": 0.4},
        "ETHUSDT": {"funding_rate": 0.04, "price": 3800, "oi_change": 0.8, "volume_ratio": 1.3, "liq_long_ratio": 0.7},
    }
    return mock.get(symbol, mock["BTCUSDT"])


def get_all_data(symbol: str = "BTCUSDT") -> dict:
    """采集全部数据，返回字典"""
    print(f"  [*] 获取 {symbol} 数据 (Bybit)...")
    
    rate = get_funding_rate(symbol)
    print(f"      资金费率: {rate}% 年化")
    
    ticker = get_ticker(symbol)
    price = float(ticker.get("lastPrice", 0))
    volume = float(ticker.get("volume24h", 0))
    turnover = float(ticker.get("turnover24h", 0))
    print(f"      价格: ${price:,.2f}  成交量: {volume:,.0f}")
    
    oi_z = compute_oi_zscore(symbol)
    print(f"      OI Z-score: {oi_z:.3f}")
    
    # 成交量比率
    vol_ratio = 1.0
    if price > 0 and turnover > 0:
        vol_ratio = round(volume / (turnover / price), 2)
    
    # 买卖比例（近似清算比）
    trades = get_recent_trades(symbol, 100)
    if isinstance(trades, list) and len(trades):
        buys = sum(1 for t in trades if t.get("side", "Buy") == "Buy")
        liq_ratio = round(buys / len(trades), 2)
    else:
        liq_ratio = 1.0
    
    return {
        "funding_rate": rate / 100 if price > 0 else None,
        "price": price,
        "oi_change": round(oi_z, 3),
        "volume_ratio": vol_ratio,
        "liq_long_ratio": liq_ratio,
    }
