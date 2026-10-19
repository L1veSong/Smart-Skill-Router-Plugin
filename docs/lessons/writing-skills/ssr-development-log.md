# SSR 开发进度（终版）

> 2026-06-04 ~ 2026-06-05

## 阶段回顾

| 阶段 | 状态 | 说明 |
|------|:---:|------|
| 需求分析 | ✅ | 3 张截图 + GitHub #4589 → 确认痛点 |
| 方案设计 | ✅ | A+B 混合方案，IF 逼问 8 轮 |
| 代码实现 | ✅ | 638 行，22 函数 |
| 配置集成 | ✅ | config.yaml + hermes plugins enable |
| RED 基线 | ✅ | 0/5 通过 |
| GREEN 验证 | ✅ | A 层命中 + B 层匹配（timeout 修复后） |
| Bug 修复 | ✅ | last_hit 空值 + 去重冷却 + 任务切换 |
| 规则固化 | ✅ | CMG ban #60 + ban_act_before_verify 扩充 |
| Skill 库更新 | ✅ | writing-skills + adapt-skill-to-hermes |

## 本轮修复清单

| # | Bug | 修复 |
|---|-----|------|
| 1 | A 层种子规则启动时被清空 | `last_hit=""` → `continue` 不标记过期 |
| 2 | B 层每次超时 | timeout 5→15→30s |
| 3 | 同 session 永不重复推荐 | 永久去重 → 60s 冷却制 |
| 4 | 任务切换检测太窄 | 短消息（≤15 字）也触发切换 |
| 5 | 擅自关 CMG task_recommendations | 恢复 + CMG ban 规则防再犯 |

## 关键数据

- SSR 代码: 638 行
- A 层规则: 10 条种子（24 个 skill 引用）
- B 层索引: 223 个 skill
- CMG ban 规则: 60 条（新增 ban_no_disable_without_confirm）
- Skill 库更新: writing-skills + adapt-skill-to-hermes
