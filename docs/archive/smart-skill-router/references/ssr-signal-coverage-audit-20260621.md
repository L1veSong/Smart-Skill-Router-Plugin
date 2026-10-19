# SSR v1.6.3 信号覆盖审计 — 2026-06-21

> **v1.6.4 实测见**: `references/ssr-signal-coverage-v164-20260621.md`

## 改前基线 (v1.6.3)

> 10 信号 + 5 噪音逐条测试，A 层 + B 层 + Embedding 三层漏斗行为记录。

## 测试环境

| 项目 | 值 |
|------|-----|
| Skill 数 | 388 |
| A 层规则 | 100 条 (a_rules.json) |
| Embedding 模型 | bge-large-zh-v1.5 (1024维, Ollama) |
| B 层后端 | main (DeepSeek v4-pro) |
| display 模式 | false (SILENT) |

## 信号测试 (10条)

| # | 消息 | A 层 | B 层 | 推荐结果 | 判定 |
|:-:|------|:--:|:--:|------|:--:|
| 1 | 帮我设计一个暗色仪表盘 | ❌ | ❌ | 无匹配 | ❌ 漏推 |
| 2 | Python代码报KeyError怎么调试 | ✅ | — | diagnose, systematic-debugging | ✅ |
| 3 | 分析茅台均线走势 | ✅ | — | stock-screen-monitor, technical-analysis, tushare-finance | ✅ |
| 4 | 北京自驾到南昌路线规划 | ✅ | — | road-trip-planner, travel-skill ×6 | ✅ |
| 5 | 帮我写论文文献综述 | ✅ | — | research-paper-writing, survey ×10 | ✅ |
| 6 | 画一个ASCII猫咪 | ✅⚠️ | — | 12个design skill，无 ascii-art | ❌ BUG |
| 7 | 部署网站到Vercel | ❌ | ❌ | 无匹配 | ❌ 漏推 |
| 8 | 生成季度PPT汇报 | ❌ | ❌ | 无匹配 | ❌ 漏推 |
| 9 | 画中国地图显示GDP | ❌ | ❌ | 无匹配 | ❌ 漏推 |
| 10 | 发微信给示例用户A | ❌ | ❌ | 无匹配 | ❌ 漏推 |

**命中率: 4/10 (40%)**

## 噪音测试 (5条)

| # | 消息 | 结果 |
|:-:|------|:--:|
| 1 | 今天天气怎么样 | 无匹配 ✅ |
| 2 | 谢谢你的帮助 | 无匹配 ✅ |
| 3 | 好的我明白了 | 无匹配 ✅ |
| 4 | 你觉得呢 | 无匹配 ✅ |
| 5 | 嗯嗯 | 无匹配 ✅ |

**静默率: 5/5 (100%)**

## 根因分层

### 第一层：A 层关键词缺口 (5条)

正则覆盖盲区：

| 场景 | 缺失正则 | 应推荐 skill |
|------|---------|-------------|
| 设计-仪表盘 | `仪表盘|dashboard` | brainstorming, ui-ux-pro-max, frontend-design |
| 部署Vercel | `deploy|部署|Vercel` | deploy-to-vercel |
| PPT | `PPT|pptx|演示` | pptx |
| 地图 | `地图|geo|GIS` | geographic-visualization, svg-geo-map |
| 微信 | `微信|wechat|WeChat` | wechat-desktop-send |

### 第二层：B 层过于保守 (6条全漏)

日志: `B 层判断: 不需要 skill`

DeepSeek prompt 以"是否需要 skill"为判断标准 → 简单任务判定为"不需要" → 返回空。

### 第三层：Embedding 触发条件限制

`_match_a_layer` L626: `if keyword_result and _EMBEDDING_INDEX:` — A 层空时 embedding 也不跑。

### 第四层：排序截断 BUG (信号6)

`ascii-art` 作为关键词命中（无 `_sim` 字段）→ 排序时排末尾 → 被 12 个 embedding 结果挤出。

## 修复执行状态 (2026-06-21)

| 优先级 | 措施 | 状态 |
|:--:|------|:--:|
| P0 | 补 5 条 A 层正则 | ⏳ 未执行 — 用户决定通过 B→A 自学习填充 |
| P1 | 修排序截断 BUG | ⏳ 计划中 |
| P2 | 调 B 层 prompt + 删 NO 门控 | ✅ 已执行 — `__init__.py` line 1345+1359 |
| P3 | Embedding 门控放宽 | ✅ 已执行 — `__init__.py` line 626 `keyword_result and` → 删除 |
| — | 备份 | ✅ `__init__.py.bak.06211942` |

**执行内容:** 见 `~/.hermes/plans/ssr/b-layer-embedding-fix_plan.md`
**重启要求:** 完全退出 Hermes 再启动（非 /new）

## 验证命令

```bash
# 全量测试
grep -E 'A 层命中|B 层命中|无匹配|B 层判断' ~/.hermes/logs/agent.log | tail -20

# 会话统计
grep '会话统计' ~/.hermes/logs/agent.log | tail -1
```
