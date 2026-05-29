#!/usr/bin/env python3
"""本地测试：不调API，用模拟数据验证引擎逻辑"""
import sys
import numpy as np
sys.path.insert(0, ".")

from bayesian_engine import BayesianSignalEngine, MarketState


def test_basic():
    """基础测试：费率高+多头证据 => 先验偏空但证据偏多 => 最终反转"""
    engine = BayesianSignalEngine(np.linspace(0.0, 0.5, 100))
    
    # 场景：费率高但多头证据强劲
    state = MarketState(
        funding_rate=0.8,    # 80%年化，极高
        price=100000,
        oi_change=2.5,       # OI暴增 = 多头趋势
        volume_ratio=2.0,    # 放量
        liq_long_ratio=0.2,  # 空头清算远多于多头
    )
    signal = engine.update(state, is_rate_epoch=True)
    print(f"[测试1] 高费率+多头证据")
    print(f"  P(跌)={signal.prob_down:.1%}  P(涨)={signal.prob_up:.1%}")
    print(f"  信号: {signal.action}  置信度: {signal.confidence:.1%}")
    assert signal.prob_up > signal.prob_down, "证据应压倒先验"
    print("  ✅ 通过\n")
    
    return True


def test_skip():
    """测试：不确定性高时应 skip"""
    engine = BayesianSignalEngine(np.array([]))
    
    state = MarketState(
        funding_rate=0.02,   # 中性
        price=100000,
        oi_change=0.1,       # 中性
        volume_ratio=1.0,    # 中性
        liq_long_ratio=1.0,  # 中性
    )
    signal = engine.update(state, is_rate_epoch=True)
    print(f"[测试2] 所有信号中性")
    print(f"  P(跌)={signal.prob_down:.1%}  P(涨)={signal.prob_up:.1%}")
    print(f"  信号: {signal.action}  置信度: {signal.confidence:.1%}")
    assert signal.action == "skip", "中性数据应 skip"
    print("  ✅ 通过\n")
    
    return True


def test_reversal():
    """测试：极度高费率 + 空头证据 => 强烈看跌"""
    engine = BayesianSignalEngine(np.linspace(0.0, 0.3, 100))
    
    state = MarketState(
        funding_rate=1.2,    # 120%年化，极度过热
        price=100000,
        oi_change=0.5,      # OI温和增长
        volume_ratio=0.3,   # 缩量
        liq_long_ratio=4.0, # 多头清算远多于空头
    )
    signal = engine.update(state, is_rate_epoch=True)
    print(f"[测试3] 极度高费率+空头证据")
    print(f"  P(跌)={signal.prob_down:.1%}  P(涨)={signal.prob_up:.1%}")
    print(f"  信号: {signal.action}  置信度: {signal.confidence:.1%}")
    assert signal.action == "short"
    print("  ✅ 通过\n")
    
    return True


if __name__ == "__main__":
    print("🐵 贝叶斯费率引擎 - 单元测试\n")
    tests = [test_basic, test_skip, test_reversal]
    passed = sum(t() for t in tests)
    total = len(tests)
    print(f"{'='*35}")
    print(f"  结果: {passed}/{total} 通过")
    print(f"{'='*35}")
    sys.exit(0 if passed == total else 1)
