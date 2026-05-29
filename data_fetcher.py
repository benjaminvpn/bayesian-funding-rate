"""
从 Binance 公开 API 获取数据
无需 API key，纯公开数据
"""

import json
import urllib.request
import urllib.error
import numpy as np
from typing import Optional


BINANCE_BASE = "https://fapi.binance.com"  # 合约市场


def fetch_json(url: str) -> dict:
    """安全的 GET 请求"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [!] 请求失败: {url[:60]}... -> {e}")
        return {}


def get_funding_rate(symbol: str = "BTCUSDT") -> float:
    """获取当前资金费率（年化）"""
    url = f"{BINANCE_BASE}/fapi/v1/premiumIndex?symbol={symbol}"
    data = fetch_json(url)
    rate = float(data.get("lastFundingRate", 0))
    # 转换为年化：每8小时一次，一年=3*365=1095次
    annualized = rate * 3 * 365 * 100
    return round(annualized, 4)


def get_funding_rate_history(symbol: str = "BTCUSDT", limit: int = 100) -> np.ndarray:
    """获取历史费率用于校准先验"""
    url = f"{BINANCE_BASE}/fapi/v1/fundingRate?symbol={symbol}&limit={limit}"
    data = fetch_json(url)
    if not data:
        return np.array([])
    rates = [float(item["fundingRate"]) * 3 * 365 * 100 for item in data]
    return np.array(rates)


def get_24hr_ticker(symbol: str = "BTCUSDT") -> dict:
    """获取24小时ticker"""
    url = f"{BINANCE_BASE}/fapi/v1/ticker/24hr?symbol={symbol}"
    return fetch_json(url)


def get_open_interest(symbol: str = "BTCUSDT") -> float:
    """获取当前持仓量"""
    url = f"{BINANCE_BASE}/fapi/v1/openInterest?symbol={symbol}"
    data = fetch_json(url)
    return float(data.get("openInterest", 0))


def get_open_interest_history(symbol: str = "BTCUSDT", limit: int = 50) -> np.ndarray:
    """获取持仓量历史（用于计算变化率）"""
    url = f"{BINANCE_BASE}/futures/data/openInterestHist?symbol={symbol}&period=15m&limit={limit}"
    data = fetch_json(url)
    if not data:
        return np.array([])
    oi_values = [float(item["sumOpenInterest"]) for item in data]
    return np.array(oi_values)


def get_recent_trades(symbol: str = "BTCUSDT", limit: int = 50) -> list:
    """获取最近成交（用于估算清算比例）"""
    url = f"{BINANCE_BASE}/fapi/v1/trades?symbol={symbol}&limit={limit}"
    return fetch_json(url)


def compute_oi_zscore(symbol: str = "BTCUSDT") -> float:
    """计算 OI 变化的 Z-score"""
    oi_current = get_open_interest(symbol)
    oi_hist = get_open_interest_history(symbol, 50)
    if len(oi_hist) < 10:
        return 0.0
    mean_oi = np.mean(oi_hist)
    std_oi = np.std(oi_hist)
    if std_oi < 1e-8:
        return 0.0
    return float((oi_current - mean_oi) / std_oi)


def get_mock_data(symbol: str = "BTCUSDT") -> dict:
    """离线调试用：返回模拟数据"""
    import random
    mock = {
        "BTCUSDT": {"funding_rate": 0.06, "price": 105000, "oi_change": 1.2, "volume_ratio": 1.8, "liq_long_ratio": 0.4},
        "ETHUSDT": {"funding_rate": 0.04, "price": 3800, "oi_change": 0.8, "volume_ratio": 1.3, "liq_long_ratio": 0.7},
    }
    return mock.get(symbol, mock["BTCUSDT"])


def get_all_data(symbol: str = "BTCUSDT") -> dict:
    """采集全部数据，返回字典"""
    print(f"  [*] 获取 {symbol} 数据...")
    
    rate = get_funding_rate(symbol)
    print(f"      资金费率: {rate}% 年化")
    
    ticker = get_24hr_ticker(symbol)
    price = float(ticker.get("lastPrice", 0))
    volume = float(ticker.get("volume", 0))
    quote_vol = float(ticker.get("quoteVolume", 0))
    print(f"      价格: ${price:,.2f}  成交量: {float(volume):,.0f}")
    
    oi_z = compute_oi_zscore(symbol)
    print(f"      OI Z-score: {oi_z:.3f}")
    
    # 成交量比率
    vol_ratio = 1.0
    if price > 0 and quote_vol > 0:
        vol_ratio = round(volume / (quote_vol / price), 2)
    
    # 清算比例
    trades = get_recent_trades(symbol, 100)
    if isinstance(trades, list) and len(trades):
        buys = sum(1 for t in trades if not t.get("isBuyerMaker", True))
        liq_ratio = round(buys / len(trades), 2)
    else:
        liq_ratio = 1.0
    
    return {
        "funding_rate": rate / 100 if price > 0 else None,  # 转为小数
        "price": price,
        "oi_change": round(oi_z, 3),
        "volume_ratio": vol_ratio,
        "liq_long_ratio": liq_ratio,
    }
