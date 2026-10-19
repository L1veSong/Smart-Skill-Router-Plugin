# SSR 命中率近似度量（2026-07-22 实战）

## 背景

"SSR 命中率"无法精确计算——没有人工标注的 ground truth（每条消息"应该"推荐哪些 skill）。但可以用代理指标近似衡量。

## 方法：推荐→加载转化率

统计 `A 层命中` + `B 层命中` 的总触发次数，对比同期 `skill_view` 调用次数。

```python
from hermes_tools import terminal
import re

log_path = "/Users/holiday_home/.hermes/logs/agent.log"

a_hits = b_hits = skill_views = 0
with open(log_path) as f:
    for line in f:
        if 'A 层命中' in line:
            a_hits += 1
        if 'B 层命中' in line:
            b_hits += 1
        if 'skill_view' in line and 'tool skill_view' in line:
            skill_views += 1

total_recs = a_hits + b_hits
rate = skill_views / total_recs * 100 if total_recs else 0
print(f"SSR 推荐: {total_recs} | skill_view: {skill_views} | 转化率: {rate:.1f}%")
```

## 解读

| 转化率 | 含义 |
|--------|------|
| >70% | 推荐高度相关，AI 频繁按推荐加载 skill |
| 40-70% | 正常——部分推荐被忽略（不相关/不需要） |
| <40% | 推荐噪声过多或 AI 不信任推荐 |

## 注意事项

1. **skill_view 不全是 SSR 驱动的** — CMG 强制加载（canon-mnemonic-guard/caveman）也算在内。真实 SSR 驱动的转化率偏低 10-20%。
2. **A 层每轮必触发** — A 层覆盖率 100%，所以"触发率"无意义。有意义的是"触发了有没有用"。
3. **只统计有意义的会话** — 纯闲聊/元对话会话中 SSR 可能静默（meta convo 检测），不应计入。
