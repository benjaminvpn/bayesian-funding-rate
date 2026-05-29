"""
从 Hyperliquid 公开 API 获取数据
DEX，不封 IP，GitHub Actions 可用
"""

import json
import urllib.request
import urllib.error
import numpy as np

HL_INFO = "https://api.hyperliquid.xyz/info"


def post_info(body: dict) -> dict:
    """POST 到 /info 接口"""
    data = json.dumps(body).encode()
    req = urllib.request.Request(HL_INFO, data=data,
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()[:100]
        print(f"  [!] HTTP {e.code}: {body} -> {body_text}")
        return {}
    except Exception as e:
        print(f"  [!] 请求失败: -> {e}")
        return {}


def get_funding_rate(symbol: str = "BTC") -> float:
    """获取当前资金费率。Hyperliquid 每小时结算"""
    # allMids 有 latest funding rate
    data = post_info({"type": "allMids"})
    if not data:
        return 0.0

    # 直接用 fundingHistory
    data2 = post_info({"type": "fundingHistory", "coin": symbol})
    if not data2:
        return 0.0
    # 返回 [{time, coin, fundingRate}]，最后一条最新
    rate = float(data2[-1]["fundingRate"]) if data2 else 0.0
    return round(rate * 24 * 365 * 100, 4)


def get_funding_rate_history(symbol: str = "BTC", limit: int = 50) -> np.ndarray:
    """获取历史费率"""
    data = post_info({"type": "fundingHistory", "coin": symbol})
    if not data or not isinstance(data, list):
        return np.array([])
    items = data[-limit:] if len(data) > limit else data
    rates = [float(i["fundingRate"]) * 24 * 365 * 100 for i in items]
    return np.array(rates)


def get_all_data(symbol: str = "BTC", hl_symbol: str = "BTC") -> dict:
    print(f"  [*] 获取 {symbol} 数据 (Hyperliquid)...")

    rate = get_funding_rate(hl_symbol)
    print(f"      资金费率: {rate}% 年化")

    mids = post_info({"type": "allMids"})
    price = float(mids.get(hl_symbol, 0)) if mids else 0
    print(f"      价格: ${price:,.2f}")

    # 获取 recent trades 估算买卖比
    trades = post_info({"type": "recentTrades", "coin": hl_symbol})
    if isinstance(trades, list) and len(trades):
        buys = sum(1 for t in trades if t.get("side", "") == "B")
        sells = sum(1 for t in trades if t.get("side", "") == "A")
        liq_ratio = round(buys / (buys + sells), 2) if (buys + sells) > 0 else 1.0
    else:
        liq_ratio = 1.0

    return {
        "funding_rate": rate / 100,
        "price": price,
        "oi_change": 0.0,
        "volume_ratio": 1.0,
        "liq_long_ratio": liq_ratio,
    }


def get_mock_data(symbol: str = "BTCUSDT") -> dict:
    mock = {
        "BTCUSDT": {"funding_rate": 0.06, "price": 105000, "oi_change": 1.2, "volume_ratio": 1.8, "liq_long_ratio": 0.4},
        "ETHUSDT": {"funding_rate": 0.04, "price": 3800, "oi_change": 0.8, "volume_ratio": 1.3, "liq_long_ratio": 0.7},
    }
    return mock.get(symbol, mock["BTCUSDT"])
