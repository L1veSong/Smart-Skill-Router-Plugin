# bge-m3 Embedding 语义匹配准确率实测

> 2026-06-09 · SSR v0.5.0+ 合并架构 · bge-m3 1024维 · 246 skill 索引

## 测试目的

量化 bge-m3 embedding 在 A 层关键词零命中时的语义匹配质量。与 auto-gen 关键词（10%）对比。

## 测试方法

1. 构造 4 条**不命中任何 A 层关键词规则**的消息
2. 通过 Ollama bge-m3 API 获取消息 embedding
3. 与 `embeddings.json` 中 246 个 skill 的 embedding 计算余弦相似度
4. 取 top-5 判定是否命中期望 skill

## 结果

| # | 消息 | 期望 skill | Top-1 命中 | 相似度 | 判定 |
|---|------|-----------|-----------|--------|:--:|
| 1 | 帮我弄个暗色主题的仪表盘页面 | ui-ux-pro-max / dashboard | architecture-diagram | 0.605 | ⚠️ 勉强 |
| 2 | 给我做一个人物传记的知识漫画 | baoyu-comic | baoyu-comic | 0.661 | 🟢 精准 |
| 3 | 帮我整理 iPhone 拍的照片按日期分类 | photo-organizer-pro | apple-reminders | 0.497 | ❌ 跑偏 |
| 4 | 我想把这段 HTML 代码转成视频动画 | code-to-video | ascii-video | 0.629 | 🟡 接近(#2 code-to-video 0.619) |

**命中率：2.5/4 (~63%)**

## 分析

- **强项**：语义精确场景（"知识漫画"→baoyu-comic）。中文语义区分度好。
- **弱项**：多义词场景（"iPhone 照片整理"→误匹配到 reminders 而非 photos）。描述粒度粗时相似度分散（0.46-0.50 区间，区分度低）。
- **对比 auto-gen**：auto-gen 关键词匹配只有 10%，bge-m3 的 63% 是 6x 提升。但仍不如手动关键词规则（100%）。

## 架构定位

bge-m3 embedding 在三级兜底中处于中间层：

```
关键词精确匹配（100条手动规则，零延迟，~100%准确）  ← 第一优先
  → 零命中时
Embedding 语义匹配（bge-m3 1024维，top-30，~63%准确）  ← 语义兜底
  → 仍无合适结果时
B 层 LLM 语义匹配（DeepSeek/Ollama，最慢但最灵活）      ← 最终兜底
```

**结论**：embedding 不是替代关键词，而是补充。对常见场景关键词足够；对冷门/变形表达，embedding 提供 63% 的兜底。两者互补。
