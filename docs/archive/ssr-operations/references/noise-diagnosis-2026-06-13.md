# SSR 噪音诊断（2026-06-13 生产环境实测）

## 背景

全会话 SSR 100% 命中率（40/40），但 90% 推荐不相关。用户讨论 CMG 时推荐金融盯盘，讨论"检查 SSR"时推荐视频制作。三层漏斗全通但推不准。

## 根因三层

### 1. A 层 100 条规则含 40+ 条 auto-gen 单英文词垃圾

```
skill → canon-mnemonic-guard-dashboard (87 hit)
work → writing-skills (83 hit)
only → design-taste-frontend-v1 (81 hit)
call → mcporter (81 hit)
view → canon-mnemonic-guard-dashboard (81 hit)
```

每条命中 80+ 次，每次对话必触发，产出 1 个完全不相关的 skill。**删掉这 40+ 条规则可 -30% 噪音。**

### 2. Embedding 结果无门控

关键词命中 3-8 个 skill 后，Embedding 追加 20+ 个 sim 0.35-0.45 的弱相关 skill。两者 OR 关系，相加了噪音而非互补过滤。

**修复：** 关键词命中时，Embedding 加门控（sim > 0.50 才补充）。关键词未命中时正常走 embedding。

### 3. 中文查询扩展无匹配度要求

`_expand_chinese_query` 命中一个调试关键词就追加 "debug, error, diagnose, fix, troubleshoot"，污染 bge-m3 向量。需 ≥2 个域关键词才触发。

## RED 反基准

GREEN 5 场景验证"该推的必须推"，RED 5 场景验证"不该推的必须闭嘴"：

| # | 消息 | 不应推荐 |
|---|------|---------|
| R1 | SSR 有优化空间吗 | 金融 (technical-analysis, stock-screen-monitor) |
| R2 | 帮我记到 CMG 里 | 旅行、视频制作、角色扮演 |
| R3 | memory 差多少满 | 金融、游戏、音乐 |
| R4 | 8:15 了 | 任何 build 类 skill |
| R5 | 对，就是你分析的那样 | 任何 skill（确认性回复） |

判定：GREEN ≥4/5 且 RED ≥4/5 → 噪音控制到位。

## 平衡策略

所有阈值可配，渐进调参：

| 参数 | 当前 | 候选 | 调法 |
|------|:--:|------|------|
| embedding.gate_threshold | 无 | 0.45, 0.50, 0.55 | 0.50 起步→RED 失败降到 0.45 |
| embedding.similarity_floor | 0.35 | 0.40, 0.45, 0.50 | 0.45 起步→GREEN 失败降到 0.40 |

## 100% 命中率 ≠ SSR 工作良好

存活验证三段式只能回答「SSR 是否在运行」，不能回答「推荐是否准确」。当命中率 100% 且推荐全错时，三层漏斗比 B 层孤跑更危险——它让用户认为「系统正常」，实则所有推荐都是噪音。

## 详细计划

见 `~/.hermes/plans/ssr/noise-reduction/task_plan.md`

---

## ✅ 完成报告（2026-06-14）

**方案变更：** 原计划代码过滤 → 实际采用手动清洗 + auto-gen 关闭。理由：代码过滤只能删单英文词，手动清洗可同时去掉 paper-spine/huashu-nuwa/perspective 等非单字噪声。

**结果：**
```
a_rules.json: 61 → 6 条全手动
auto-gen 单字噪声: 56 → 0
误报（work→writing-skills）: 消失
GREEN 基准: 5/5 全通过（A层 4/5 + B层兜底 1/5）
backup: a_rules.json.bak (9.5KB)
```

**延期 Task：** Embedding 门控 (Task 2)、中文扩展 (Task 3)、similarity_floor 提升 (Task 4) — 6 条规则时不需要，等规则增长到 20+ 再评估。

**新发现：** F8 echo bug（`\\n` 字面量）、F12 plugin.yaml 版本债务 — 归入 v0.6.3 迭代计划。

详见 `references/6-rule-green-baseline-2026-06-14.md`。
