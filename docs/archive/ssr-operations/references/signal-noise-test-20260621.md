# SSR v1.7.0 信号/噪音测试 2026-06-21

## 环境

- SSR: v1.7.0 (intent_gate enabled, providers: ollama→main→pass)
- Embedding: bge-large-zh-v1.5 / 1024维 / 387 skill
- A层: 100条规则, auto_gen_rules: false
- B层: main (DeepSeek v4-pro), model: qwen3.5:9b
- 阈值: similarity_floor=0.35, confidence=0.4

## 10 信号测试

| # | 消息 | D档精准 | 评价 | 问题 |
|:--:|------|:--:|------|------|
| 1 | 帮我设计一个暗色仪表盘 | 0/1+ | 🟡 P档有方向 | D档 `skill-installation-guide` 误匹配; `ui-ux-pro-max` 在P档 |
| 2 | Python代码报KeyError怎么调试 | 2/5 | 🟡 可接受 | `diagnose`/`systematic-debugging` ✅; 3条A层噪音 |
| 3 | 分析茅台均线走势 | 4/4 | 🟢 最佳 | `stock-screen-monitor`/`technical-analysis`/`tushare-finance`/`agent-reach` 全中 |
| 4 | 北京自驾到南昌路线规划 | 0/1 | 🟡 P档救援 | D档仅 `brainstorming`; `road-trip-planner` 在P档 |
| 5 | 帮我写论文文献综述 | 7/8 | 🟢 最佳 | paper-spine全家桶全中; `planning-with-files` 略偏 |
| 6 | 画一个ASCII猫咪 | 0/0 | ⚠️ 技能缺口 | ascii-art未安装; P档全视觉设计噪音 |
| 7 | 部署网站到Vercel | 0/3 | 🔴 deploy-to-vercel失踪 | A层 `actions` 规则误匹配; deploy-to-vercel在embedding但未进任何档 |
| 8 | 生成季度PPT汇报 | 0/1 | 🔴 pptx在P档 | A层规则 `they`/`will` 等无意义单词未匹配"PPT"; D档被paper-spine误占 |
| 9 | 画中国地图显示GDP | 2/2 | 🟢 精准 | `geographic-visualization`+`tushare-finance` ✅; P档6条视觉噪音 |
| 10 | 发微信给朋友说晚点到 | 0/1 | 🔴 imessage在B档 | A层零微信规则; D档tong-jincheng-perspective噪音; 正确答案在B档被confidence卡 |

**综合: 2🟢 + 3🟡 + 3🔴 + 1⚠️**

## 系统级问题

1. **auto-gen 规则质量差**: `they`/`will`/`actions`/`updating` 等无意义单词作为A层pattern — 从不匹配实际用户消息
2. **微信/消息类零 A 层覆盖**: `imessage`/`wechat-desktop-send` 全靠embedding, 但相似度不够高
3. **视觉关键词污染**: "画"/"设计"触发 design-taste 全家桶, P档被视觉skill淹没
4. **金融/学术规则最成熟**: 这是两个唯一 D档高命中率的类别
5. **deploy-to-vercel 匹配异常**: 在embedding索引中, description精准, 但未被推荐 — 需排查相似度打分

## 5 噪音测试 (pending)

| # | 消息 | 期望 |
|---|------|------|
| 1 | 嗯嗯 | 静默 |
| 2 | 谢谢你的帮助 | 静默 |
| 3 | 好的我明白了 | 静默 |
| 4 | 你觉得呢 | 静默 |
| 5 | 今天天气怎么样 | 静默 |
