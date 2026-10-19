# v1.8.0 信号/噪音测试基准

> 2026-06-21 · SSR 四段式架构验证

## 架构

```
白名单(10条正则,0 token) → LLM门控(二分类,~50 token) → A层(关键词+embedding) → LLM筛查(~200 token) → 推荐/静默
```

## 信号 10 条

| # | 消息 | v1.7.0 D档 | v1.8.0 期望 |
|:--:|------|:--:|------|
| 1 | 帮我设计一个暗色仪表盘 | 🟡 P档 | D档: brainstorming, ui-ux-pro-max |
| 2 | Python代码报KeyError怎么调试 | 🟡 2/5 | D档: diagnose, systematic-debugging |
| 3 | 分析茅台均线走势 | 🟢 4/4 | D档: technical-analysis, tushare-finance |
| 4 | 北京自驾到南昌路线规划 | 🟡 P档 | D档: road-trip-planner |
| 5 | 帮我写论文文献综述 | 🟢 7/8 | D档: research-paper-writing, survey |
| 6 | 画一个ASCII猫咪 | ⚠️ 技能缺口 | 静默(无已装skill) |
| 7 | 部署网站到Vercel | 🔴 0/3 | D档: deploy-to-vercel |
| 8 | 生成季度PPT汇报 | 🔴 pptx卡P档 | D档: pptx |
| 9 | 画中国地图显示GDP | 🟢 2/2 | D档: geographic-visualization |
| 10 | 发微信给朋友说晚点到 | 🔴 P/B档 | D档: wechat-desktop-send, imessage |

## 噪音 5 条（v1.7.0 门控 0/5 全漏）

| # | 消息 | v1.7.0 | v1.8.0 期望 |
|:--:|------|:--:|:--:|
| 1 | 嗯嗯 | ❌ 漏过 | ✅ 白名单(len<4)直拦 |
| 2 | 谢谢你的帮助 | ❌ 漏过 | ✅ 白名单(谢谢)直拦 |
| 3 | 好的我明白了 | ❌ 漏过 | ✅ 白名单(好的)直拦 |
| 4 | 你觉得呢 | ❌ 漏过 | ✅ 白名单(反问)直拦 |
| 5 | 今天天气怎么样 | ❌ 漏过 | ✅ 白名单(天气)直拦 |

## 元讨论

| 消息 | v1.7.0 | v1.8.0 期望 |
|------|:--:|------|
| 极大的退步。分析原因 | ❌ paper-spine-*洪水 | 静默或极少 |
| 回退是优化吗？ | ❌ 推荐 smart-skill-router 等 | 静默或极少 |
