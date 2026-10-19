# SSR 三方案实测对比 (2026-06-22)

## 测试设置

- 13 条测试消息（3 噪音 + 10 信号）
- 噪音白名单 4 条正则
- bge-large-zh-v1.5 embedding, 387 skill
- LLM: DeepSeek v4-pro

## 三个方案

| # | 方案 | 描述 |
|---|------|------|
| P1 | 当前管线 | embedding 候选 → LLM 语境筛查过滤 |
| P2 | 纯LLM一次 | 218 skill 全塞 prompt，LLM 一次判断意图+匹配 |
| P3 | LLM+emb提示 | embedding 提供 8 个候选上下文 → LLM 一次判断意图+匹配 |

## 逐条结果

| 消息 | 预期 | P1 当前 | P2 纯LLM | P3 LLM+emb |
|------|------|---------|----------|------------|
| 嗯 | noise | NOISE | NOISE | NOISE |
| 好的 | noise | NOISE | NOISE | NOISE |
| 帮我写一篇学术论文 | rec | 0个 | NO_NEED | 5个: academic-paper, research-paper-writing |
| 这段代码有bug帮我修 | rec | 0个 | NO_NEED | 2个: diagnose, systematic-debugging |
| 推荐一只A股 | rec | 0个 | 4个: stock-screen-monitor, tushare-finance | 5个: 同上+technical-analysis |
| 画一个好看的登录页面 | rec | 0个 | 5个: ui-ux-pro-max, brainstorming | 5个: imagegen-frontend-web, frontend-design |
| 帮我部署到Vercel | rec | 0个 | NO_NEED | 3个: deploy-to-vercel, vercel-cli-with-tokens |
| 女朋友生气了怎么办 | rec | 1个: relationship-conflict-analysis | NO_NEED | 5个: relationship-conflict-analysis |
| 今天天气真好啊 | noise | NO_CAND | NO_NEED | NO_NEED |
| 你吃饭了吗 | noise | 0个 | NO_NEED | NO_NEED |
| 做一份PPT | rec | 0个 | 2个: powerpoint | NO_NEED |
| ASCII画一只猫 | rec | 0个 | NO_NEED | NO_NEED |
| 新疆旅游攻略 | rec | 0个 | NO_NEED | 5个: travel-planner, trip-planner-generator |

## 统计

| 方案 | 噪音拦截 | 推荐命中 | 漏过 | 误推 | 噪音误 | 准确率 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| P1 当前管线 | 4/4 | 1/9 | 8 | 0 | 0 | 38% |
| P2 纯LLM一次 | 4/4 | 3/9 | 6 | 0 | 0 | 54% |
| P3 LLM+emb | 4/4 | 7/9 | 2 | 0 | 0 | 85% |

## 分析

**P3 漏过的两个：**
- "做一份PPT" — embedding 找到了 `powerpoint`，LLM 误判 NO_NEED（可改 prompt 修复）
- "ASCII画一只猫" — embedding 无候选，LLM 也无推荐（需补 embedding 或 A 层规则）

**P2 为什么差：** 218 个 skill 描述全塞 prompt → 信息过载 → LLM 频繁判 NO_NEED。不是能力不够，是候选太多无法精准匹配。

**P1 为什么最差：** embedding 先筛 → 筛掉的 skill LLM 没见过 → 大量 NO_CAND。LLM 被降级为候选过滤而非独立匹配。

## 结论

**架构确认：噪音→LLM一次搞定(判断意图+匹配skill)，embedding只提供候选上下文助LLM回忆，不做决策。**
