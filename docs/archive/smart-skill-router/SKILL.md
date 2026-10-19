---
name: smart-skill-router
description: "智配路由 (SSR) v3.1.0 — 267条A层规则·47域·覆盖~130 usable skill。P0激活。Golden已永久封死。"
version: 3.1.0
author: L1veSong
license: MIT
metadata:
  hermes:
    tags: [skill-matching, routing, plugin, auto-load]
    related_skills: [verification-before-completion]
---

# 智配路由 (SSR) — Smart Skill Router v3.0.0

> 插件: `~/.hermes/plugins/ssr/__init__.py` | Dashboard: `localhost:8766`
> A层: `a_rules.json` (267条·47域) | MoE路由: `DOMAIN_STEMS` (316词干·手工精选)

## v3.1.0 变更 (2026-07-24)

### 规则库从 182 扩到 199（同会话 12 轮迭代）

本次会话在 v3.0 golden 基线之上新增 17 条规则，涵盖：

| 批次 | 新增域/规则 | 数量 |
|------|-----------|:--:|
| video 域扩充 | hyperframes(11) + remotion(10) + media-use + video-shotcraft | 13 |
| business 域 | dbskill 28 子 skill 全量匹配 | 25 |
| 金融域 | technical-analysis/tushare-finance/finance-news-analyzer | 3 |
| 生图域填坑 | 9 条空壳规则补上 7 个生图 skill | 9 |
| 设计域 | 7 条入口规则覆盖 13 个设计 skill | 7 |
| 其他 | khazix-writer / agent-reach / opencli-browser / bailian-cli 等 | 12 |

### Golden 炸弹永久封死（同会话两次触发·已根治）

第一次（v3.0 升级脚本）：硬编码 `cp golden_bak → a_rules.json` 覆盖 40 条新增规则。
第二次（同日）：17 个 `.bak.*` 备份文件互相踩，读错备份导致规则从 187 掉到 139。

**永久措施：**
- 17 个备份全部删除，只留 `a_rules.json.bak.clean`
- CMG `ban_ssr_golden_restore` 硬规则
- 修改 a_rules.json 走 `patch` 增量，不再 `execute_code` 全量读写
- 备份只保留 2 个轮转（干净快照 + 上一版）

### '装了就入 SSR' 固化为工作流铁则

每装一个新 skill → 立刻补 SSR regex + 测试 3-5 个触发句。禁止 "以后再说"。

### P0：ALL_DOMAINS fallback 删除

`_route_domains()` 的无命中全开兜底删除。无域激活 → 静默。这是 SSR 自发布以来 MoE 路由首次真正工作——v2.4.0 的 DOMAIN_STEMS 只有 6 个错误域名，ALL_DOMAINS 全开掩盖了整条路由从未生效的 bug。

### DOMAIN_STEMS 从正则机械提取 + Golden 验证

v2.4.0 的 6 个手工域名（visual/shortdrama）与 A 层 34 域完全不对齐。v3.0 改为从 `a_rules.json` 正则机械提取词干 + 55 Golden 逐条验证补全，272 词干覆盖 34 域。

### 幽灵 skill 清理

42 个磁盘上不存在的 skill 名从规则中移除，4 个因命名变化而映射到真实 skill。规则本身保留——regex 仍然正常路由域。

### 三层架构接口预留

`__init__.py` 的 `_route_domains()` 返回 `set[domain]`，`_match_a_layer_keyword()` 接受 `domains: set` 参数。当某个域膨胀到 15+ skill 且子方向超过 4 个时，插入第二层子域匹配器无需改接口签名。

## 当前基线

| 指标 | 值 |
|------|-----|
| 规则数 | 295 |
| 域 | 47 |
| 覆盖可路由 skill | ~140 |
| Golden | 55/55 |
| P0 | 启用 |

### 2026-07-25b 会话（工具+Agent安装+SSR非skill匹配）

| 变更 | 详情 |
|------|------|
| **LibTV** | libtv-cli skill v1.1.2 + CLI 全装，SSR 入规则 |
| **橙星梦工厂** | Funai-skill v1.0.6 + Token 全通，SSR 入规则 |
| **InkOS** | @actalk/inkos v1.7.1，SSR +2条 (小说创作/去AI味) |
| **Agent 更新** | Codex 0.145.0, Reasonix 1.17.21, Kimi Code 1.0.11 |
| **视频工具 SSR** | auto-editor/whisperx/losslesscut/shotcut 入 SSR |
| **生活服务 SSR** | 节假日/油价/快递/汇率 → 非skill条目匹配 |
| **设计决策** | 用户明确：SSR 可匹配非skill（CLI工具/脚本/桌面App） |

### 2026-07-25 会话变更

| 变更 | 详情 |
|------|------|
| **writing 域扩展** | 网文/小说/扫榜/去AI味/连载等 → 5 新规则路由 claude-code, +22 词干, 规则 5→10, 词干 13→35 |
| **OriginKit MCP** | 设计域新增 originkit 规则, +4 设计域词干。MCP 工具自动注入，无需 skill 加载 |
| **CC 网文生态** | oh-story-claudecode + chinese-novelist-skill + webnovel-writer → ~/.claude/skills/, Hermes 通过 claude-code 委派 |
| **llm_screen 安全网** | LLM 筛查返回 [] 但 A 层 ≥5 命中 → 信任 A 层 |
| **display 静默反馈** | `display: true` 时静默也注入原因（意图门控/LLM 筛查） |
| **webnovel-writer 依赖** | watchdog/fastapi/uvicorn/aiohttp/filelock/pydantic 全部就绪 |

### 2026-07-24 会话变更

| 变更 | 详情 |
|------|------|
| **business 域新增** | dbskill 28 子 skill 全部入 rule |
| **video 域扩充** | hyperframes 11 + remotion 10 + media-use + video-shotcraft |
| **生图域填坑** | 9 条空壳规则补上 7 个生图 skill；新增人像摄影规则 |
| **macOS 域修正** | find-nearby → leisure；apple regex 窄化 |
| **写作域** | khazix-writer |
| **金融域** | technical-analysis/tushare-finance/finance-news-analyzer |
| **agent 域** | agent-reach / opencli-browser |
| **百炼 CLI** | bailian-cli 规则 |
| **阮捷 API** | GPT Image RMB 通道（待验证） |

## 坑点

### Golden 恢复覆盖全量规则（2026-07-24 实战 · 同一会话两次触发）

**症状：** 第一次：SSR v3.0 升级脚本中的 `cp golden_bak → a_rules.json` 覆盖了本会话新增的 ~40 条规则。同一天第二次：17 个 `.bak.*` 备份文件互相踩，某次操作读错备份导致规则从 187 掉到 139。

**根因：** 1) 升级脚本硬编码了 golden baseline 恢复逻辑；2) 每次修改规则前 `shutil.copy(rules_path, rules_path + '.bak.xxx')` 积累了 17 个备份文件，某次操作误读了旧备份。

**永久修复（2026-07-24）：** 
1. 找到最大的备份文件（51.5KB）恢复最优版本（175 条规则）
2. **删除全部 17 个备份文件**——只留一个 `a_rules.json.bak.clean`
3. CMG 添加 `ban_ssr_golden_restore` 硬规则禁止覆盖 a_rules.json
4. **修改 a_rules.json 走增量路径（python dict update），不再全量备份**——用 `patch` 工具增量改，不用 `execute_code` 全量读写
5. golden backup 只作人工手动恢复用，AI 绝不执行 `cp backup → live`

### 域分类铁则：跨平台功能禁入 OS 专属域

**触发：** 用户质疑"这些都是专属于mac的吗？"（2026-07-24）

`find-nearby`（找附近餐厅）被归入 `macos` 域——它是通用功能，Windows/Linux 同样适用。只有 Apple 独占的 skill（findmy、apple-notes、apple-reminders）才入 `macos`。

**标注前三问：** 1) 只能 macOS 用？2) Windows 能用？3) Linux 能用？→ 任一通用即禁入 OS 专属域。

详见 `references/domain-classification-rules-20260724.md`

### A 层 regex 不可过宽

`提醒` 会命中所有含"提醒"的句子——"提醒我明天开会"不是 Apple Reminders 触发。窄化为 `apple.*提醒|siri.*提醒|icloud.*提醒`，通用场景由 productivity 类 skill 覆盖。

### 幽灵 skill 导致空中推荐

`skills` 数组指向磁盘上已删除的 skill → SSR 路由到域，但推荐结果为空。规则本身保留（regex 正确路由域），但需定期 `grep` 验证 skill 名是否实际存在。

## 关键设计决策

### 59% 而不是 97%

分母排除被动技能（三省引擎/sentinel/skill-autoload 等 55 个）和内部实验脚本（23 个）。剩 203 个可路由技能，SSR 覆盖 119 个。不虚报。

### P0 就是 P0

无域激活→不推。旧行为（ALL_DOMAINS 全开→183 条 brute force）是 0 真阳性 100%噪声。P0 的正确结果就是有些短语无声——比噪声推荐好。

### 两层够用

183 条 regex 本身就是子域匹配器。等量级翻倍（300+ 规则、40+ 域）再加第三层。接口已预留。

## 域分布（按 skill 数）

| 域 | skill数 | 规则数 | 词干数 |
|---|---|---|---|
| 学术 | 16 | 11 | 11 |
| ml | 12 | 11 | 10 |
| 设计 | 11 | 10 | 9 |
| 部署 | 10 | 9 | 9 |
| system | 10 | 9 | 8 |
| 生图 | 10 | 10 | 15 |
| code-quality | 9 | 8 | 13 |
| 视频 | 8 | 6 | 13 |
| github | 8 | 7 | 11 |
| 金融 | 7 | 6 | 11 |
| docs | 7 | 7 | 9 |
| travel | 6 | 9 | 17 |
| agent | 5 | 4 | 8 |
| planning | 5 | 3 | 6 |
| project | 4 | 4 | 13 |
| writing | 5 | 10 | 35 |
| social | 4 | 4 | 5 |
| macos | 4 | 4 | 14 |
| 通讯 | 4 | 4 | 9 |
| media | 3 | 4 | 6 |
| 音乐 | 3 | 3 | 8 |
| collab | 3 | 3 | 3 |
| storage | 2 | 2 | 9 |
| china-services | 2 | 2 | 7 |
| cli | 2 | 2 | 4 |
| gaming | 2 | 2 | 6 |
| obsidian | 2 | 2 | 4 |
| security | 2 | 2 | 5 |
| lifestyle | 2 | 2 | 6 |
| dev-tools | 2 | 2 | 3 |
| llm-screen | 1 | 1 | 1 |
| map | 1 | 1 | 4 |
| search | 1 | 1 | 4 |
| smarthome | 1 | 1 | 4 |
| messaging | 1 | 1 | 2 |

## 关键参考文件

- [v3 层级 MoE 架构设计](references/ssr-v3-hierarchical-moe-design.md) — 域→子域→regex 三层路由图纸、接口预留方案、与 Switch Transformer/Mixtral 的对照
- [跨域污染修复记录 2026-07-23](references/cross-domain-contamination-fixes-20260723.md) — 本会话所有污染案例的根因+修复+回归验证
- [DOMAIN_STEMS 死锁根因](references/domain-stems-deadlock-pitfall.md) — v2.4.0 MoE 路由从未工作的技术分析
- [A 层规则设计方法](references/a-rule-design-methodology.md) — 粗中有细、互斥设计、逐场景测试
- [重启验证清单](references/restart-verification-checklist.md) — 三指标验证 + 域覆盖检查 + 全量测试用例
- [域分类铁则](references/domain-classification-rules-20260724.md) — 跨平台功能禁入 OS 专属域、regex 窄化、标注前三问。2026-07-24 实战纠正 find-nearby 误入 macos
- [生图 Skill 选择指南](references/cinema-skills-comparison.md) — cinema-dna vs zy-cinematic-realism vs Kōda 对比 + FANTASY×6+ZY×1 全量分类。2026-07-24

## 配置

```yaml
ssr:
  enabled: true
  mode: suggest
  display: false
  b_layer: {provider: main, timeout: 30}
  embedding: {provider: xxx, model: xxx}
  intent_gate: {enabled: true, active: main}
  noise_filter: {enabled: true}
```

## 诊断

```bash
# 重启验证三指标
grep 'SSR.*registered' ~/.hermes/logs/agent.log | tail -1  # 加载确认
grep 'SSR P0' ~/.hermes/logs/agent.log | tail -5           # P0 触发情况

# Golden 基准
python3 ~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py --mode total --quick
```

## 装了就入 SSR（工作流铁则）

**用户原意（2026-07-24 多次验证）：** 每装一个新 skill/工具 → 立刻补 SSR 规则。不是"以后再说"——装完就该能被匹配到。

**标准流程：**
1. 安装 skill/工具
2. 立刻向 `a_rules.json` 追加 regex + skills 映射（用 `patch` 增量，**不用 `execute_code` 全量读写**）
3. 逐条测试 3-5 个典型触发句验证命中
4. **禁止** `shutil.copy(rules_path, rules_path + '.bak.xxx')`——备份只保留一个 `a_rules.json.bak.clean`

**反面案例（本会话）：** 装了 hyperframes/remotion/dbskill 等 70+ skill，SSR 匹配全空——因为规则没跟上。用户追问"都能匹配到吗？"才补。不是技术问题，是流程问题。

## 生图 Skill 选择参考

7 个生图 skill 的对比、配合方式、与 Kōda 的关系，详见 `references/cinema-skills-comparison.md`。

## 已知风险

1. **P0 主动激进** — 词干缺失 → 无声。这是正确的（降噪优先于召回），但真实召回率未经盲测验证
2. **生图空壳已修复** — 2026-07-24 9 条空 rules 全部填入实际 skill。后续新增域时需自检：规则有 regex 但 skills 为空 = 死节点
3. **"搭"词干同时命中 gaming 和 project** — 这是正确的跨域行为，由 A 层 regex 最终裁决
4. **khazix-writer 正则过宽 (2026-07-26)** — `帮我写.*(文章|...|小说|故事|...)` 把「帮我写小说」也路由到 khazix（公众号长文）。小说应走 claude-code 委派。从 khazix 规则 alternation 中移除「小说」「故事」。详见 `references/novel-writing-routing-gap.md`
5. **意图门控误杀询问句 (2026-07-26)** — 「还有写小说的skill吗」被门控判为非任务请求 → P0 整轮静默。询问性问句应放行——用户问能力范围是合理任务
6. **静默≠不存在——Agent 不得以 SSR 静默为据声称「没有」 (2026-07-26)** — 用户问「还有写小说的skill吗？」SSR 意图门控静默整轮。Agent 未翻查 `a_rules.json` 也未搜索 CC skills / npm 全局包，直接回复「没有写小说的 skill」。用户当场纠正——3 套 CC 网文系统 + InkOS CLI 全在。教训：SSR 静默时，Agent 必须手动 grep a_rules.json + 搜索 `~/.claude/skills/` + `npm list -g` + `which` 交叉验证，不得以静默为唯一证据。
