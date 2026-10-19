# SSR GREEN 实时验证 (2026-06-09 生产环境)

## 环境

- SSR v0.5.1 (2026-06-09 修复冷却 `continue` 误杀)
- A 层: 100 手动规则 + 2010 auto-gen（已加 `auto_gen_rules: false` 开关，未重启）
- Embedding: bge-m3 1024维, 246 skill 索引
- B 层: main (DeepSeek v4-pro)
- 面板: localhost:8766 HTTP 200

## 结果

| # | 消息 | 期望 | 实际 | 日志时间 | |
|---|------|------|------|---------|:--:|
| 1 | "帮我设计一个响应式导航栏" | ui-ux-pro-max, popular-web-designs | 双命中 + design-taste-frontend | 22:28:23 | ✅ |
| 2 | "这段 Python 代码报 KeyError 帮我看看" | diagnose | diagnose + systematic-debugging + python-debugpy | 22:28:46 | ✅ |
| 3 | "生成一个 ASCII 猫咪图" | ascii-art | ascii-art + ascii-video + pixel-art | 22:29:03 | ✅ |
| 4 | "帮我写论文的 Related Work 部分" | research-paper-writing | paper-spine-research（功能等效，research-paper-writing 被冷却吞掉） | 22:29:22 | 🟡 |
| 5 | "分析贵州茅台的均线走势" | technical-analysis | technical-analysis + tushare-finance | 22:29:57 | ✅ |

**总计: 4.5/5 — 超过目标线 ≥4/5。**

## 测试 4 根因

`research-paper-writing` 在测试 1（22:28:23）被推荐过 → 测试 4（22:29:22）时冷却未到期（59秒 < 60秒）→ `continue` 丢弃。修复后改为 `shown_recently` 标记，不再丢弃。

## 所有命中均来自 A 层关键词

B 层和 Embedding 未介入——5 个场景全被 100 手动规则覆盖。Embedding 是兜底层，A 层命中时不触发。
