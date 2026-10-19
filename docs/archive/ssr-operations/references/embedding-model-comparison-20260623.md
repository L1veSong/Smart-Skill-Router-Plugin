# Embedding 模型对比: bge vs qwen (2026-06-23)

## 测试方法

15 条中文查询，两个模型各自建独立索引（公平对比，不跨模型查询）。每个模型用 403 个 skill description 编码为向量，查询时计算余弦相似度，取 top-5。

## 模型

| 模型 | 维度 | 大小 | 延迟/次 |
|------|:--:|------|:--:|
| bge-large-zh-v1.5 | 1024 | 202MB | ~0.15s |
| qwen3-embedding:0.6b | 1024 | 639MB | ~0.25s |

## 结果

| # | 查询 | 期望 skill | bge rank | qwen rank |
|---|------|------|:--:|:--:|
| 1 | 帮我设计一个暗色仪表盘 | ui-ux-pro-max | 72 ❌ | 27 ❌ |
| 2 | 这段Python代码一直报KeyError | diagnose | 23 ✅ | 322 ❌ |
| 3 | 分析贵州茅台的均线走势 | technical-analysis | 1 ✅ | 1 ✅ |
| 4 | 北京自驾到南昌路线规划 | road-trip-planner | 1 ✅ | 1 ✅ |
| 5 | 帮我写论文的文献综述 | research-paper-writing | 11 ❌ | 1 ✅ |
| 6 | 画一个ASCII猫咪 | creative | 84 ❌ | 10 ❌ |
| 7 | 部署网站到Vercel | deploy-to-vercel | 1 ✅ | 1 ✅ |
| 8 | 生成季度PPT汇报 | pptx | 5 ✅ | 1 ✅ |
| 9 | 画中国地图显示GDP数据 | geographic-visualization | 4 ✅ | 3 ✅ |
| 10 | 发微信给示例用户A | wechat-desktop-send | 1 ✅ | 1 ✅ |
| 11 | 分析这段感情问题 | relationship-conflict-analysis | 1 ✅ | 1 ✅ |
| 12 | 帮我清理Mac磁盘空间 | macos-disk-cleanup | 1 ✅ | 1 ✅ |
| 13 | 写一个Python脚本批量重命名文件 | simplify-code | 72 ❌ | 24 ❌ |
| 14 | 这个SQL查询太慢了怎么优化 | diagnose | 2 ✅ | 260 ❌ |
| 15 | 帮我做一份新疆旅行攻略 | travel-skill | 3 ✅ | 3 ✅ |

## 汇总

| | top-5 | top-3 |
|------|:--:|:--:|
| bge 1024维 202MB | 10/15 (66%) | 8/15 (53%) |
| qwen 1024维 639MB | 10/15 (66%) | 10/15 (66%) |

## 各自强项

**bge 强项：**
- 代码/调试类：SQL优化 rank=2 (qwen rank=260)、KeyError rank=23 (qwen rank=322)
- 专有名词匹配精准：deploy-to-vercel、wechat-desktop-send 都是 rank=1

**qwen 强项：**
- 学术/PPT类：论文 rank=1 (bge rank=11)、PPT rank=1 (bge rank=5)
- top-3 精准度略好：10/15 vs 8/15

## 共同盲区

- ASCII猫咪：bge rank=84, qwen rank=10 — 两个都召回不了
- Python重命名：bge rank=72, qwen rank=24 — 两个都差
- 暗色仪表盘：bge rank=72, qwen rank=27 — 两个都差

这些应该用 A 层关键词补盲，不是靠换 embedding 模型。

## 结论

换 embedding 模型不会显著提升信号召回。bge 和 qwen 在 15 条查询上打成平手，但 bge 体积只有 qwen 的 1/3。瓶颈不在 embedding 模型——在候选池覆盖（rank 72-84 的正确答案进不了 top-30）和 B 层 LLM 筛查精度。
