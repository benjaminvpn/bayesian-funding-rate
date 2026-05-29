"""
从 Hyperliquid 公开 API 获取数据
DEX，不封 IP，GitHub Actions 可用
"""

import json
import urllib.request
import urllib.error
import numpy as np

HL_URL = "https://api.hyperliquid.xyz/info"
HL_BASE = "https://api.hyperliquid.xyz"


def post_json(url: str, body: dict) -> dict:
    """POST 请求（Hyperliquid 用 POST）"""
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [!] 请求失败: {url} -> {e}")
        return {}


def get_json(url: str) -> dict:
    """Hyperliquid 部分接口也用 GET"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [!] 请求失败: {url[:60]}... -> {e}")
        return {}


def get_funding_rate(symbol: str = "BTC") -> float:
    """
    获取当前资金费率
    Hyperliquid 每小时结算一次，年化 = 费率 * 24 * 365 * 100
    """
    data = post_json(HL_URL, {"type": "allMids"})
    if not data:
        return 0.0
    # allMids 返回所有币种的最新价和资金
    # 需要单独拿资金费率
    data2 = post_json(HL_URL, {"type": "fundingHistory", "coin": symbol})
    if not data2:
        return 0.0
    # fundingHistory 返回 [{time, coin, fundingRate}]
    rate = float(data2[-1]["fundingRate"]) if data2 else 0.0
    # Hyperliquid 每小时结算，年化 = 费率 * 24 * 365
    return round(rate * 24 * 365 * 100, 4)


def get_funding_rate_history(symbol: str = "BTC", limit: int = 50) -> np.ndarray:
    """获取历史费率"""
    data = post_json(HL_URL, {"type": "fundingHistory", "coin": symbol})
    if not data:
        return np.array([])
    items = data[-limit:] if len(data) > limit else data
    rates = [float(i["fundingRate"]) * 24 * 365 * 100 for i in items]
    return np.array(rates)


def get_all_data(symbol: str = "BTC", hl_symbol: str = "BTC") -> dict:
    """
    采集全部数据
    symbol: 显示用 (BTCUSDT)
    hl_symbol: Hyperliquid 币种名 (BTC)
    """
    print(f"  [*] 获取 {symbol} 数据 (Hyperliquid)...")

    rate = get_funding_rate(hl_symbol)
    print(f"      资金费率: {rate}% 年化")

    # 获取最新价
    mids = post_json(HL_URL, {"type": "allMids"})
    price = float(mids.get(hl_symbol, 0)) if mids else 0
    print(f"      价格: ${price:,.2f}")

    # Hyperliquid 没有公开的 OI 历史 API（需链上数据），用交易量近似
    # 获取最近交易用于估算买卖比
    trades = get_json(f"{HL_BASE}/exchange/trades?coin={hl_symbol}")
    if isinstance(trades, list) and len(trades):
        buys = sum(1 for t in trades if t.get("side", "") == "B")
        sells = sum(1 for t in trades if t.get("side", "") == "A")
        liq_ratio = round(buys / (buys + sells), 2) if (buys + sells) > 0 else 1.0
    else:
        liq_ratio = 1.0

    # 获取 volume（24h）
    data2 = post_json(HL_URL, {"type": "exchangeMeta"})
    vol_ratio = 1.0
    if data2:
        for coin in data2:
            if coin.get("name") == hl_symbol:
                vol_ratio = 1.5  # 标记有数据
                break

    return {
        "funding_rate": rate / 100,
        "price": price,
        "oi_change": 0.0,  # Hyperliquid 无 OI 历史 API
        "volume_ratio": vol_ratio,
        "liq_long_ratio": liq_ratio,
    }


def get_mock_data(symbol: str = "BTCUSDT") -> dict:
    mock = {
        "BTCUSDT": {"funding_rate": 0.06, "price": 105000, "oi_change": 1.2, "volume_ratio": 1.8, "liq_long_ratio": 0.4},
        "ETHUSDT": {"funding_rate": 0.04, "price": 3800, "oi_change": 0.8, "volume_ratio": 1.3, "liq_long_ratio": 0.7},
    }
    return mock.get(symbol, mock["BTCUSDT"])
