#!/usr/bin/env python3
"""
贝叶斯费率信号引擎 - 入口
每次运行：获取数据 → 贝叶斯更新 → 输出信号到文件
"""

import sys
import json
import os
import numpy as np
from datetime import datetime

from data_fetcher import get_all_data, get_mock_data, get_funding_rate_history, get_funding_rate
from bayesian_engine import BayesianSignalEngine, MarketState


SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# Hyperliquid 币种映射: 显示名 -> Hyperliquid币种名
HL_SYMBOLS = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
}


def run(symbol: str = "BTCUSDT") -> dict:
    print(f"\n{'='*50}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {symbol}")
    print(f"{'='*50}")
    
    # 1. 获取历史费率校准先验
    hl_symbol = HL_SYMBOLS.get(symbol, symbol)
    print("[1/4] 获取历史费率...")
    rate_history = get_funding_rate_history(hl_symbol, 50)
    print(f"       共 {len(rate_history)} 条历史数据")
    if len(rate_history):
        print(f"       均值: {np.mean(rate_history):.4f}%  标准差: {np.std(rate_history):.4f}%")
    
    # 2. 初始化引擎
    print("[2/4] 初始化贝叶斯引擎...")
    engine = BayesianSignalEngine(rate_history)
    
    # 3. 获取当前市场数据
    print("[3/4] 获取当前市场数据...")
    raw = get_all_data(symbol, hl_symbol)
    if raw.get("funding_rate") is None or raw.get("price", 0) == 0:
        print("  [!] API 不可用，使用模拟数据")
        raw = get_mock_data(symbol)
    
    state = MarketState(
        funding_rate=raw["funding_rate"],
        price=raw["price"],
        oi_change=raw["oi_change"],
        volume_ratio=raw["volume_ratio"],
        liq_long_ratio=raw["liq_long_ratio"],
    )
    
    # 4. 贝叶斯更新
    print("[4/4] 贝叶斯推理...")
    signal = engine.update(state, is_rate_epoch=True)
    
    # 5. 输出结果
    print(f"\n{'─'*35}")
    print(f"  信号: {signal.action.upper():>6}")
    print(f"  置信度: {signal.confidence:.1%}")
    print(f"  P(上涨): {signal.prob_up:.1%}")
    print(f"  P(下跌): {signal.prob_down:.1%}")
    print(f"{'─'*35}")
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "price": state.price,
        "funding_rate_annualized_pct": round(state.funding_rate * 100, 4),
        "oi_zscore": state.oi_change,
        "volume_ratio": state.volume_ratio,
        "liq_ratio": state.liq_long_ratio,
        "signal": signal.action,
        "confidence": signal.confidence,
        "prob_up": signal.prob_up,
        "prob_down": signal.prob_down,
    }
    
    # 写入结果文件
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"signal_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n  ✅ 结果已保存: {output_file}")
    
    return result


def main():
    print("🐵 贝叶斯费率信号引擎 v1.0")
    print(f"   运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   目标: {', '.join(SYMBOLS)}")
    
    all_results = []
    for symbol in SYMBOLS:
        result = run(symbol)
        all_results.append(result)
    
    # 写入汇总
    summary = {
        "run_time": datetime.now().isoformat(),
        "symbols": all_results,
    }
    os.makedirs("output", exist_ok=True)
    with open("output/latest_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  ✅ 汇总已保存: output/latest_summary.json")
    
    # 输出简单摘要用于actions log
    print(f"\n{'='*50}")
    print(f"📊 摘要")
    print(f"{'='*50}")
    for r in all_results:
        emoji = {"long": "🟢", "short": "🔴", "skip": "⚪"}.get(r["signal"], "⚪")
        print(f"  {emoji} {r['symbol']}: {r['signal'].upper():>6}  "
              f"(置信度 {r['confidence']:.1%}, "
              f"费率 {r['funding_rate_annualized_pct']:+.3f}%)")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
