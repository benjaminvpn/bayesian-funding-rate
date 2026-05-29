"""
贝叶斯 + 资金费率信号引擎
核心逻辑：用资金费率构建先验，用OI/价格/清算等证据更新后验
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MarketState:
    """单次采样的市场数据"""
    funding_rate: float       # 年化百分比，0.8 = 80%
    price: float
    oi_change: float          # OI变化 Z-score
    volume_ratio: float       # 成交量相对24h中位数的倍数
    liq_long_ratio: float     # 多/空清算量比


@dataclass
class Signal:
    action: str        # "long" / "short" / "skip"
    confidence: float  # 0.5-1.0
    prob_up: float
    prob_down: float
    evidence_log: list  # 各证据的贡献记录


class PriorBuilder:
    """根据资金费率构建方向先验分布"""
    
    def __init__(self, history: np.ndarray):
        self.mean = np.mean(history) if len(history) else 0.0
        self.std = np.std(history) if len(history) else 0.5
    
    def compute_prior(self, current_rate: float) -> Dict[str, float]:
        z = (current_rate - self.mean) / (self.std + 1e-8)
        
        # sigmoid：费率过高 => P(下跌)高；费率过低 => P(上涨)高
        p_down = 1.0 / (1.0 + np.exp(-(z - 1.5)))
        p_up = 1.0 / (1.0 + np.exp(-(-z - 1.5)))
        
        total = p_up + p_down
        return {
            "up": float(p_up / total),
            "neutral": 0.0,
            "down": float(p_down / total),
        }


class LikelihoodEngine:
    """
    似然模型：P(证据 | 方向)
    使用核密度估计(KDE)拟合历史中每个证据在各方向下的分布
    """
    
    def __init__(self):
        # 简化版：使用经验阈值，不依赖离线训练
        # 后续可替换为从历史数据拟合的KDE模型
        self.evidence_weights = {
            "oi_change": {
                "up": {"mean": 0.5, "std": 1.0},
                "down": {"mean": -0.5, "std": 1.0},
            },
            "volume_ratio": {
                "up": {"mean": 1.2, "std": 0.3},
                "down": {"mean": 0.8, "std": 0.3},
            },
            "liq_long_ratio": {
                "up": {"mean": 0.3, "std": 0.5},   # 空头清算多 => 看涨
                "down": {"mean": 1.7, "std": 0.5},  # 多头清算多 => 看跌
            },
        }
    
    def likelihood(self, evidence_name: str, value: float, direction: str) -> float:
        """返回 P(evidence_value | direction) 的密度值"""
        params = self.evidence_weights.get(evidence_name, {}).get(direction)
        if params is None:
            return 1.0  # 无数据时不贡献
        
        # 用正态分布近似概率密度
        pdf = (1.0 / (params["std"] * np.sqrt(2 * np.pi))) * \
              np.exp(-0.5 * ((value - params["mean"]) / params["std"]) ** 2)
        return float(pdf + 1e-8)  # 加平滑避免零概率


class BayesianSignalEngine:
    """贝叶斯信号引擎主类"""
    
    def __init__(self, rate_history: Optional[np.ndarray] = None):
        if rate_history is None:
            rate_history = np.array([])
        self.prior_builder = PriorBuilder(rate_history)
        self.likelihood = LikelihoodEngine()
        self.posterior = {"up": 1/3, "down": 1/3, "neutral": 1/3}
    
    def update(self, state: MarketState, is_rate_epoch: bool = False) -> Signal:
        """
        用当前市场状态更新后验概率
        is_rate_epoch: 是否到了费率更新周期（重置先验）
        """
        evidence_log = []
        
        # 1. 重置先验（费率更新时）
        if is_rate_epoch:
            prior = self.prior_builder.compute_prior(state.funding_rate)
            self.posterior = prior
        
        # 2. 收集证据
        evidences = {
            "oi_change": state.oi_change,
            "volume_ratio": state.volume_ratio,
            "liq_long_ratio": state.liq_long_ratio,
        }
        
        # 3. 贝叶斯更新
        for direction in ["up", "down"]:
            p_evidence_given_dir = 1.0
            for ev_name, ev_value in evidences.items():
                p = self.likelihood.likelihood(ev_name, ev_value, direction)
                p_evidence_given_dir *= p
                evidence_log.append({
                    "evidence": ev_name,
                    "value": ev_value,
                    "direction": direction,
                    "likelihood": p,
                })
            
            self.posterior[direction] *= p_evidence_given_dir
        
        # 4. 归一化
        total = sum(self.posterior.values())
        for k in self.posterior:
            self.posterior[k] /= total
        
        # 5. 生成信号
        max_dir = max(self.posterior, key=lambda k: self.posterior[k])
        confidence = self.posterior[max_dir]
        
        if confidence < 0.55:
            action = "skip"
        else:
            action = "long" if max_dir == "up" else "short"
        
        return Signal(
            action=action,
            confidence=round(confidence, 4),
            prob_up=round(self.posterior["up"], 4),
            prob_down=round(self.posterior["down"], 4),
            evidence_log=evidence_log[-6:],  # 只保留最新几条
        )
