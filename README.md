# 贝叶斯费率信号引擎 🐵

资金费率 + 贝叶斯推理 = 实时多空信号。

## 思路

把资金费率当作**先验概率**（费率过高→偏空，过低→偏多），再用 OI变化、成交量、清算比等证据做**贝叶斯更新**，输出带置信度的后验信号。

详见：https://github.com/OpenBMB/PilotDeck (大圣的内部分析)

## 跑法

### GitHub Actions（免费，推荐）

1. Fork 或 push 到自己的 GitHub 仓库
2. 自动每6小时跑一次，结果存 `output/` 目录
3. 也可以点 `Actions` → `贝叶斯费率信号` → `Run workflow` 手动触发

### 本地

```bash
pip install numpy
python main.py
```

API 连不上时会自动用模拟数据演示。

## 输出

`output/latest_summary.json`:

```json
{
  "symbols": [{
    "symbol": "BTCUSDT",
    "signal": "long/short/skip",
    "confidence": 0.95,
    "prob_up": 0.95,
    "prob_down": 0.05,
    "funding_rate_annualized_pct": 6.0
  }]
}
```

## License

MIT
