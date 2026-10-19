# SSR Embedding 模型对比基准（2026-06-23）

## 测试方法

15条中文信号查询，同组 skill description 文本，三个模型独立建索引，同样的余弦相似度计算。

## 查询集

| # | 查询 | 期望 skill |
|---|------|-----------|
| 1 | 帮我设计一个暗色仪表盘 | ui-ux-pro-max |
| 2 | 这段Python代码一直报KeyError | diagnose |
| 3 | 分析贵州茅台的均线走势 | technical-analysis |
| 4 | 北京自驾到南昌路线规划 | road-trip-planner |
| 5 | 帮我写论文的文献综述 | research-paper-writing |
| 6 | 画一个ASCII猫咪 | creative |
| 7 | 部署网站到Vercel | deploy-to-vercel |
| 8 | 生成季度PPT汇报 | pptx |
| 9 | 画中国地图显示GDP数据 | geographic-visualization |
| 10 | 发微信给示例用户A | wechat-desktop-send |
| 11 | 分析这段感情问题 | relationship-conflict-analysis |
| 12 | 帮我清理Mac磁盘空间 | macos-disk-cleanup |
| 13 | 写一个Python脚本批量重命名文件 | simplify-code |
| 14 | 这个SQL查询太慢了怎么优化 | diagnose |
| 15 | 帮我做一份新疆旅行攻略 | travel-skill |

## 结果

### bge-large-zh-v1.5（本地 Ollama，1024维，202MB）

| # | 命中 | rank | top-3 候选 |
|---|:--:|:--:|------|
| 1 | ❌ | 72 | dashboard, neon, gradient |
| 2 | ❌ | 23 | python-debugpy, jupyter-live-kernel, test-driven-development |
| 3 | ✅ | 1 | technical-analysis, short-term-trader, stock-screen-monitor |
| 4 | ✅ | 1 | road-trip-planner, travel-skill, travel-data-apis |
| 5 | ❌ | 11 | academic-paper-reviewer, nature-academic-search, deep-research |
| 6 | ❌ | 84 | canvas-design, high-end-visual-design, slack-gif-creator |
| 7 | ✅ | 1 | deploy-to-vercel, vercel-optimize, vercel-cli-with-tokens |
| 8 | ✅ | 5 | nature-paper2ppt, paper-spine-build, html-presentation |
| 9 | ✅ | 4 | geographic-viz, geojson-svg-map, svg-geo-map |
| 10 | ✅ | 1 | wechat-desktop-send, zhangxuefeng, yuanbao |
| 11 | ✅ | 1 | relationship-conflict-analysis, tong-jincheng, short-term-trader |
| 12 | ✅ | 1 | macos-disk-cleanup, storage-analyzer, macos-computer-use |
| 13 | ❌ | 72 | jupyter-live-kernel, python-debugpy, setup-matt-pocock |
| 14 | ✅ | 2 | benchmark, diagnose, agent-reach |
| 15 | ✅ | 3 | xinjiang-food-curation, travel-planner, travel-skill |

**top-5: 10/15 (66%) | top-3: 8/15 (53%)**

### qwen3-embedding:0.6b（本地 Ollama，1024维，639MB）

| # | 命中 | rank | top-3 候选 |
|---|:--:|:--:|------|
| 1 | ❌ | 27 | design-html, shadcn, canvas-design |
| 2 | ❌ | 322 | python-debugpy, codex, jupyter-live-kernel |
| 3 | ✅ | 1 | technical-analysis, tushare-finance, finance-news-analyzer |
| 4 | ✅ | 1 | road-trip-planner, sun-yuchen, travel-planner |
| 5 | ✅ | 1 | research-paper-writing, education-paper-writing, academic-paper |
| 6 | ❌ | 10 | sketch, algorithmic-art, doodle |
| 7 | ✅ | 1 | deploy-to-vercel, vercel-cli-with-tokens, vercel-optimize |
| 8 | ✅ | 1 | pptx, powerpoint, html-presentation |
| 9 | ✅ | 3 | svg-geo-map, geographic-viz, geographic-visualization |
| 10 | ✅ | 1 | wechat-desktop-send, imessage, github-auth |
| 11 | ✅ | 1 | relationship-conflict-analysis, zhangxuefeng, zhang-yiming |
| 12 | ✅ | 1 | macos-disk-cleanup, macos-computer-use, apple-notes |
| 13 | ❌ | 24 | planning-with-files, paper-spine-rewrite, redesign-existing |
| 14 | ❌ | 260 | hermes-memory-optimization, skill-optimization-workflow, darwin |
| 15 | ✅ | 3 | xinjiang-food-curation, travel-food-guide, travel-skill |

**top-5: 10/15 (66%) | top-3: 10/15 (66%)**

### Qwen3-Embedding-8B（硅基 API，4096维）

| # | 命中 | rank | top-3 候选 |
|---|:--:|:--:|------|
| 1 | ❌ | 20 | dashboard, canvas-design, cmg-dashboard |
| 2 | ❌ | 126 | requesting-code-review, systematic-debugging, receiving-code-review |
| 3 | ✅ | 2 | tushare-finance, technical-analysis, yuanbao |
| 4 | ✅ | 2 | autoplan, road-trip-planner, travel-plan-request |
| 5 | ✅ | 1 | research-paper-writing, academic-paper-reviewer, academic-paper |
| 6 | ❌ | 66 | doodle, sketch, canvas-design |
| 7 | ✅ | 1 | deploy-to-vercel, vercel-cli-with-tokens, vercel-composition-patterns |
| 8 | ✅ | 1 | pptx, powerpoint, nature-paper2ppt |
| 9 | ✅ | 2 | svg-geo-map, geographic-visualization, geographic-viz |
| 10 | ✅ | 1 | wechat-desktop-send, yuanbao, slack-gif-creator |
| 11 | ✅ | 1 | relationship-conflict-analysis, to-issues, heartmula |
| 12 | ✅ | 1 | macos-disk-cleanup, clean, macos-computer-use |
| 13 | ❌ | 92 | planning-with-files, xlsx, paper-spine-rewrite |
| 14 | ❌ | 142 | plan-tune, executing-plans, skill-optimization-workflow |
| 15 | ❌ | 9 | travel-plan-request, xinjiang-food-curation, travel-plan-html-editor |

**top-5: 9/15 (60%) | top-3: 9/15 (60%)**

## 结论

| 模型 | top-5 | top-3 | 延迟 | 成本 |
|------|:--:|:--:|:--:|------|
| bge-local-1024 | 66% | 53% | <0.1s/query | 零 |
| qwen-local-1024 | 66% | 66% | <0.3s/query | 零 |
| qwen-api-4096 | 60% | 60% | ~1s/query | API |

- **4096维比1024维差 6pp** — 维度翻4倍，命中率反降
- qwen3:0.6b 和 bge 本地持平（都是66%），但 639MB vs 202MB → bge 性价比更高
- Qwen3-Embedding-8B 代码/调试类退化严重（KeyError rank=126, SQL rank=142）
- **瓶颈不在 embedding 模型 — 在 B层 LLM 筛查和 A层关键词补盲**
