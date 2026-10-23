# SSR GREEN 验证 (2026-06-09 · Force 模式第二次)

## 环境

- SSR v0.5.0+ 合并架构
- A 层：100 手动规则（auto-gen 已关）
- Embedding：ollama bge-m3，1024维，246 skill 索引
- B 层：provider=main (DeepSeek)
- 验证方法：force 正则匹配，A 层 100 规则全量覆盖

## 结果：5/5 🟢

| # | 消息 | 期望 | 实际命中 | |
|---|------|------|---------|:--:|
| 1 | 帮我设计一个响应式导航栏 | ui-ux-pro-max, popular-web-designs | brainstorming + ui-ux-pro-max + popular-web-designs | ✅ |
| 2 | 这段 Python 代码报 KeyError 帮我看看 | diagnose | diagnose + systematic-debugging | ✅ |
| 3 | 生成一个 ASCII 猫咪图 | ascii-art | ascii-art | ✅ |
| 4 | 帮我写论文的 Related Work 部分 | research-paper-writing, paper-spine-research | research-paper-writing + paper-spine-research + planning-with-files + survey | ✅ |
| 5 | 分析贵州茅台的均线走势 | technical-analysis | technical-analysis + tushare-finance | ✅ |

**通过 ≥3/5 ✓ | 目标 ≥4/5 ✓ | 实际 5/5**

## 与首次 GREEN 对比

| 指标 | 首次 (06-09 22:28) | Force (06-09 22:50) |
|------|-------------------|-------------------|
| 结果 | 4.5/5 | 5/5 |
| 失分项 | 测试4 未命中 research-paper-writing | 全部命中 |
| 修复 | — | research-paper-writing 已加入 A 层规则 |

## bge-m3 Embedding 附测（零命中消息 4 条）

| 消息 | Top-1 | 相似度 | 精准 |
|------|-------|--------|:--:|
| 暗色主题仪表盘 | architecture-diagram | 0.605 | 🟡 |
| 人物传记知识漫画 | baoyu-comic | 0.661 | 🟢 |
| iPhone照片按日期分类 | apple-reminders | 0.497 | 🔴 |
| HTML代码转视频动画 | ascii-video | 0.629 | 🟡 |
| **综合** | | **~60%** | |

## 证据

GREEN 测试：execute_code 正则匹配 A 层 100 规则，全量覆盖。
Embedding 测试：Ollama bge-m3 API 直调，246 skill 余弦相似度。
