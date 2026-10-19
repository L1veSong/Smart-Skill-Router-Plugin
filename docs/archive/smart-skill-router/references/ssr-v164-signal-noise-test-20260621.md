# SSR v1.6.4 信号/噪音 15 条实测 · 2026-06-21

## 测试环境

- embedding: bge-large-zh-v1.5 (1024维, Ollama)
- A层: 100条 auto-gen 规则
- B层: main (DeepSeek), prompt=新版(相不相关, 非需不需要)
- embedding门控: 已解锁 (v1.6.4 删除 keyword_result and)
- 意图门控: 未部署 (v1.6.4)

## 10 信号

| # | 消息 | 命中? | top skill | 备注 |
|---|------|:--:|------|------|
| 1 | 帮我设计一个暗色仪表盘 | ✅ | design-taste-frontend-v1 | 12 skill, 全设计/UI域 |
| 2 | Python代码报KeyError怎么调试 | ✅ | diagnose | systematic-debugging 同在 |
| 3 | 分析茅台均线走势 | ✅ | technical-analysis | tushare-finance 同在 |
| 4 | 北京自驾到南昌路线规划 | ✅ | road-trip-planner | #1 精准 |
| 5 | 帮我写论文文献综述 | ✅ | research-paper-writing | survey 补充 |
| 6 | 画一个ASCII猫咪 | ⚠️ | gif-search | **回归**: ascii-art 被 embedding 挤出 top-12 (坑点43) |
| 7 | 部署网站到Vercel | ✅ | vercel-optimize | deploy-to-vercel 未进列表 |
| 8 | 生成季度PPT汇报 | ✅ | pptx | paper-spine-build 误匹配 |
| 9 | 画中国地图显示GDP | ✅ | geographic-visualization | #1 精准 |
| 10 | 发微信给示例用户A | ❌ | (低置信跳过) | embedding max=0.382 < floor 0.40 |

**命中: 8/10 (2 partial)、B层调用: 0次**

## 5 噪音

| # | 消息 | 静默? | 日志 | 备注 |
|---|------|:--:|------|------|
| 1 | 嗯嗯 | ✅ | len<5 前置过滤 | 无日志 |
| 2 | 谢谢你的帮助 | ✅ | embedding 0.391 < 0.40 | 置信度不足跳过 |
| 3 | 好的我明白了 | ❌ | 12 skill 全 design/美学 | 误触发 |
| 4 | 你觉得呢 | ❌ | 12 skill 全 perspective | 误触发 |
| 5 | 今天天气怎么样 | ✅ | 无匹配 (A+B层全空) | 首次触发B层调用 |

**静默: 3/5**

## 对比基线

| 指标 | v1.6.3 (旧) | v1.6.4 | 变化 |
|------|:--:|:--:|:--:|
| 信号命中 | 4/10 | 8/10 | +4 ✅ |
| 噪音静默 | 5/5 | 3/5 | -2 ❌ |
| B层"不需要" | 6次 | 0次 | ✅ |
| embedding激活 | 4次 | 10次 | ✅ |
| B→A PROMOTE | 0 | 0 | — |

## 结论

- v1.6.4 信号侧达标 (8/10)
- 噪音侧回归 (3/5) — embedding 门控解锁后短句也能触发
- bge-large-zh-v1.5 无法用数学特征分离信号噪音 (pairwise/norm/spike 全失败)
- v1.7.0 LLM意图门控是解决方案
