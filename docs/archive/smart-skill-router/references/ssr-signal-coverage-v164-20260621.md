# SSR v1.6.4 信号覆盖实测 — 2026-06-21

## 测试环境

- Session: 20260621_194640_a1a800
- SSR: v1.6.4 (embedding 门控解除 + B 层去二元门控 + 删除 NO 判定)
- Embedding: bge-large-zh-v1.5 (1024维, 202MB)
- A层: 100 rules (auto-gen)
- Skill: 388 installed
- Similarity floor: 0.40

## 10 信号 + 5 噪音逐条实测

### 信号测试 (10条)

| # | 消息 | 命中 | 方式 | 关键 skill | 备注 |
|---|------|:--:|------|-----------|------|
| 1 | 帮我设计一个暗色仪表盘 | ✅ | A层 | stock-screen-monitor, frontend-design, ui-ux-pro-max, agent-gui-shell | 仪表盘+dashboard 关键词匹配 |
| 2 | Python代码报KeyError怎么调试 | ✅ | A层 | diagnose, systematic-debugging | 调试/报错 关键词匹配 |
| 3 | 分析茅台均线走势 | ✅ | A层 | technical-analysis(#1), tushare-finance(#2) | 金融/均线 关键词匹配 |
| 4 | 北京自驾到南昌路线规划 | ✅ | A层 | road-trip-planner(#1) | 自驾/旅行 关键词精准匹配 |
| 5 | 帮我写论文文献综述 | ✅ | A层 | research-paper-writing, survey | 论文/文献 关键词匹配 |
| 6 | 画一个ASCII猫咪 | ⚠️ | A层 | ascii-art 被 embedding 挤出列表 | 坑点 43: 排序截断吞掉关键词精准命中 |
| 7 | 部署网站到Vercel | ✅ | A层 | vercel-react-view-transitions, vercel-optimize | 4 Vercel skill 命中，缺 deploy-to-vercel |
| 8 | 生成季度PPT汇报 | ✅ | A层 | pptx(#5) | 季度.*汇报 关键词匹配 |
| 9 | 画中国地图显示GDP | ✅ | A层 | geographic-visualization(#1), svg-geo-map(#5) | geographic 嵌入排名 #1 |
| 10 | 发微信给示例用户A | ❌ | — | 低置信跳过 (0.382 < 0.40) | wechat-desktop-send 不在 388 skill 中或嵌入相似度不足 |

### 噪音测试 (仅完成 1/5)

| # | 消息 | 结果 | 备注 |
|---|------|:--:|------|
| 1 | 嗯嗯 | ✅ 静默 | 2字符，前置过滤，零日志 |
| 2 | 谢谢你的帮助 | ⏸️ 未完成 | |
| 3 | 好的我明白了 | ⏸️ 未完成 | |
| 4 | 你觉得呢 | ⏸️ 未完成 | |
| 5 | 嗯嗯 | ⏸️ 未完成 | |

## 结论

| 指标 | 改前(v1.6.3) | 目标 | 实测(v1.6.4) |
|------|:--:|:--:|:--:|
| 信号命中 | 4/10 | 7+/10 | **8/10** ✅ |
| B 层"不需要 skill" | 6次 | 0次 | **0次** ✅ |
| embedding 激活 | 4次 | 10次 | **10次** ✅ |
| 噪音静默 | 5/5 | 5/5 | 1/1 (未测完) |

### 剩余缺口

1. **坑点 43 — 排序截断**: 关键词精准命中(ascii-art)无 `_sim` 分数 → 排序末尾 → 被 embedding 结果挤出。需 `_sim=0.8` 优先级。
2. **微信 embedding floor**: "发微信给示例用户A" 与 wechat-desktop-send 余弦相似度 0.382 < 0.40。中文口语与英文 skill description 语义鸿沟。
3. **deploy-to-vercel 排名偏低**: Vercel 相关 4 skill 命中但精准部署 skill 不在 top-12。
