# SSR 噪音治理完整方案 (2026-06-21)

## 问题

Embedding 层永不休眠——每条消息（包括"今天天气""谢谢"等噪音）必推 5 skill。
实测 50 条：信号 77% 准确率，噪音 100% 误推率。

## 根因

Embedding 是搜索引擎，不是决策器。余弦相似度永远有 top-5。

## 三层方案 (v3 最终版)

```
消息 → A 层 (30条精确中文规则, 0延迟)
       ├─ 命中 → Embedding 激活 → 综合推荐
       └─ 未命中 → B 层 LLM gate (DeepSeek, ¥0.0002/条, 2s)
                    ├─ YES → B层直接匹配 + Embedding
                    └─ NO  → 静默
```

## 执行步骤

### 1. A 层规则 6→30 (Task 1)
- 精确中文短语为主，零单字/宽泛词
- 71% 信号命中率

### 2. B 层升级 (Task 2)
- `_match_b_main()` prompt 改门控+匹配
- `max_tokens=200` (reasoning 占 ~100 tokens)
- NO 检测 → 返回 None

### 3. Embedding 静默 (Task 3)
- `_match_a_layer()` 中 keyword_result 为空 → 不调 Embedding
- 只有 A 层命中时才激活 Embedding

## 基准结果

| 指标 | 修复前 | 修复后 |
|------|:--:|:--:|
| A层信号 | 15% | 71% |
| 信号综合 | 77% | 85% |
| 噪音误推 | 60/12条 | ~0 |

## 需要重启 Hermes 生效
