---
name: smart-skill-router
description: "智配路由 (SSR) 插件 v0.6.3 — A 层 Embedding 语义匹配 (bge-m3 1024维) + 关键词正则(6条全手动) + B 层 LLM 五后端兜底。v1.5.0: 推荐位置硬编码prepend（删除_ssr_position()，append模式结构性无解）。"
version: 1.5.0
author: L1veSong
license: MIT
metadata:
  hermes:
    tags: [skill-matching, routing, plugin, auto-load]
    related_skills: [writing-skills, test-driven-development, verification-before-completion]
---

# 智配路由 (SSR) — Smart Skill Router v1.5.0

> 插件位置: `~/.hermes/plugins/ssr/__init__.py`
> 配置文件: `~/.hermes/plugins/ssr/a_rules.json`（启动时 auto-gen 动态生成）
> **Embedding 索引**: `~/.hermes/plugins/ssr/embeddings.json`（bge-m3 1024维, 206 skill）
> 规划文件: `~/.hermes/plans/ssr/smart-skill-router/`（诊断 + 修复计划 + 进度）
> **v1.5.0 (2026-06-20)**: 推荐位置硬编码 prepend。删除 `_ssr_position()` 函数和 `post_llm_call` 条件检查。append 模式因结构性截断（回复尾部截断=推荐位置）判定为无解→废弃。12 项测试全通过。plugin.yaml 0.6.3（不变）。
> 运维指南: `ssr-operations` skill
> **Embedding 基准**: `references/embedding-benchmark-2026-06-09.md`
> **重启验证报告**: `references/restart-verification-2026-06-14.md`（text2vec-bge-large-chinese + DeepSeek main B层 = 2/5 GREEN基线，echo格式bug，Reasonix集成通过）
> **Dashboard v3**: [references/dashboard-design-v3.md](references/dashboard-design-v3.md) — 2026-06-10 玻璃特效 + 动画 + i18n 纯化 + 四 skill 组合设计流程
> **GREEN 实时验证**: `references/green-live-verification-2026-06-09.md`（2026-06-09 生产环境 4.5/5）
> **Dashboard 美化**: `references/dashboard-beautification-combo.md`（2026-06-10 实战：四 skill 组合工作流）
> **Dashboard 美化工作流**: `references/dashboard-design-workflow.md`（2026-06-10 四 skill 组合实战）
> **Dashboard 设计**: `references/dashboard-design.md`（Linear 暗色主题 · 设计 token 映射 · 美化流程）
> **降噪计划**: `~/.hermes/plans/ssr/noise-reduction/task_plan.md`（2026-06-13: 删单英文词规则 + Embedding 语义门控 + 中文扩展域匹配度 + GREEN/RED 双基准验证）

## 设计原则

1. **不设限：** 不对推荐数量设上限。匹配多少推多少，LLM 自主判断加载。上限来自"怕推不准烦人"的错误假设——三次纠正推翻（1→3→8→10→不限）。

2. **auto-gen 是冷启动种子，不是主力：** description 提取关键词准确率仅 10%。B 层语义匹配升级到 A 层的规则才是高质量主力——不可被 auto-gen 覆盖。

3. **先分析再动手：** 涉及 SSR 改动时先评估影响链、列出方案优缺点、让用户选择方向——再改代码。

4. **不绑定特定 skill 集：** 规则动态生成，换机器/换 skill 自动适配。

## 当前路线图

| Phase | 内容 | 状态 |
|-------|------|:--:|
| Phase 1 | B 层去上限 + prompt 优化 | ✅ 已完成 |
| Phase 2 | Ollama Embedding 粗筛（nomic-embed-text, 246 skill） | ✅ 已实现 |
| Phase 2b | 中文 Embedding 优化（nomic→bge-m3:q4_k_m 438MB, 1024维） | ✅ 已完成 |
| Phase 3 | Embedding质量提升：描述富化 + 中文增强 + 双阈值过滤 | ✅ 已完成 (2026-06-10) |
| Phase 4 | 生产监控：Dashboard /api/stats + 会话命中日志 | ✅ 已完成 (2026-06-10) |
| Phase 5 | 智能冷却 + 增量索引自动运行 | ✅ 已完成 (2026-06-10) |

详见 `~/.hermes/plans/ssr/precision-upgrade/task_plan.md`

## 核心架构（v0.6.0+ 三层漏斗 + 四项增强 · 2026-06-10）

```
用户消息 → pre_llm_call
  ├── 中文查询增强: _expand_chinese_query() — 14域中英映射追加英文关键词
  ├── A 层：关键词精确匹配（~100条规则，零延迟）
  │   └── 命中 → 收集所有匹配结果（不限数量）
  ├── A 层：Embedding 语义匹配（bge-m3 1024维，296 skill，描述富化）
  │   └── top-30 → 补充关键词未覆盖的 skill
  │        ↑ _get_skill_info() 正文提取（跳过表格/代码块，取前3段散文）
  ├── 合并去重（关键词优先排前面，Embedding 补充排后面）
  │   └── 有结果 → 冷却制去重 → 按阶段分组 → 注入 [SSR] 推荐
  │   └── calls % 10 == 0 → _log_session_stats() 输出命中率日志
  └── B 层：LLM 语义匹配（五后端可选）
      └── A 层无结果时兜底 → 注入 [SSR] 推荐
      └── calls % 10 == 0 → _log_session_stats() 输出命中率日志

Dashboard: GET /api/stats → read_stats() → {intercept_count, error_count, sessions, last_solidify}
          前端 renderStats() → 6格统计卡

> **Embedding 模型：bge-m3**（BAAI 多语言模型，1024维，q4_k_m 量化 438MB）。
> 旧 nomic-embed-text（768维，英文优化）已于 2026-06-09 淘汰——中文语义区分度仅 0.37-0.65 窄带，核心 skill（diagnose/research-paper-writing）排名 100+。

## 配置

```yml
ssr:
  hooks:
    pre_llm_call: true
    post_llm_call: true     # 必须开启。SSR 推荐固定前置到回复开头（末尾模式会因截断丢失）
  a_rules_max: 100
  a_rules_ttl_days: 30
  auto_gen_rules: true       # v0.5.1: false 关闭 auto-gen，仅保留手动规则 + embedding
  b_layer:
    provider: main           # 推荐：零配置，复用 Hermes 主模型（ollama | openai 备选）
    timeout: 30
```

**备选 — 本地 Ollama：**

```yaml
  b_layer:
    provider: ollama
    model: qwen2.5:3b
    base_url: http://localhost:11434
    timeout: 30
```

**Embedding 层配置（推荐：本地 bge-m3）：**

```yaml
  embedding:
    provider: ollama          # ollama | siliconflow | openai
    model: bge-m3             # 1024维，中文语义强（q4_k_m 438MB）
    timeout: 15
```

**bge-m3 安装（推荐 hf-mirror 手动下载，ollama pull 太慢）：**

```bash
# 1. 下载 GGUF
curl -L -o ~/Downloads/bge-m3-q4_k_m.gguf \
  "https://hf-mirror.com/groonga/bge-m3-Q4_K_M-GGUF/resolve/main/bge-m3-q4_k_m.gguf"

# 2. 导入 Ollama
cat > /tmp/Modelfile.bge-m3 << 'EOF'
FROM ~/Downloads/bge-m3-q4_k_m.gguf
EOF
ollama create bge-m3 -f /tmp/Modelfile.bge-m3

# 3. 删除旧 nomic 索引 + 重建 bge-m3 索引（重启 Hermes 自动触发）
rm ~/.hermes/plugins/ssr/embeddings.json
```

**旧 nomic-embed-text（不推荐）：**

```yaml
  embedding:
    provider: ollama
    model: nomic-embed-text   # 768维，英文优化，中文区分度极低
    timeout: 15
```

```yaml
  b_layer:
    provider: openai
    model: deepseek-chat
    base_url: https://api.deepseek.com
    api_key: sk-xxx          # ⚠️ 必填，否则静默失败（见坑点 6）
    timeout: 30
```

## A 层种子规则

存储在 `~/.hermes/plugins/ssr/a_rules.json`，JSON 格式。每条规则含 pattern（正则）、skills（含 phase 标签）、source（manual/auto）、priority。

当前 11 条种子规则覆盖：设计/调试/写代码/论文/ASCII/金融/旅行/代码审查/架构/发布/论文检索。

## B 层五后端

| 后端 | 适用场景 | 配置量 |
|------|---------|------|
| ollama | 有本地 GPU | model + base_url |
| openai | 云端 API | api_key + base_url + model |
| main | 零配置 | 无（复用主模型） |

## 关键功能

- 预热：register() 时 ping Ollama 避免首次 B 层冷启动
- 预过滤：B 层关键词粗筛 296→~20 候选，prompt 从 ~3000→200 token
- 冷却标记（v0.5.1）：同 skill 60s 内再次命中不删除，标记 `shown_recently` → 展示加 `(刚才)`
- 冷启动重试：B 层超时自动 warmup + 重试一次
- B→A 升级：连续 3 次同一匹配自动固化到 A 层
- 结果缓存：B 层结果 60s 内复用
- 残骸检测：启动时报告不可用 skill
- auto-gen 开关（v0.5.1）：`ssr.auto_gen_rules: false` 关闭 auto-gen，仅保留手动规则 + embedding 语义匹配

## 常见坑点

### 坑点 1: A 层规则反复回退/丢失

**症状:** 手动写的 A 层规则重启后消失，或回退到旧版本。扩展的 debug 规则（含 KeyError|Error）反复变回原始短版本。

**多层根因：**
1. `_cleanup_a_rules()` 曾将 `last_hit: ""`（从未命中）误判为过期 → 种子规则被删。修复：`if not last_hit_str: continue`。
2. `_match_a_layer` 每次命中都 `_save_a_rules(_A_RULES)` 全量写盘。多个 Hermes 会话并行时，旧会话的内存副本覆盖刚修好的规则文件。
3. 手动编辑 `a_rules.json` 后被旧会话写盘覆盖。

**修复:** 延迟写盘系统——命中 → `_mark_a_dirty()` → 累计 5 次 → `_flush_a_rules()` 写一次。启动和 B→A 升级也走 dirty 标记。旧会话不再写盘，规则不再回退。

### 坑点 2: B 层 `main` 模式 401 — key 截断

`model.api_key` 在 config.yaml 中是截断 key（含字面 `...`，13 字符），不是完整 35 字符 key。`hermes config set` 会截断含 `...` 的 key → 用 `sed` 或 Python 直接写。

### 坑点 3: B 层 `main` 模式 `hermes_cli` 导入静默失败

`from hermes_cli.config import load_config` 在插件上下文中可能不可用 → 返回 None 无日志。修复：三路径降级——① `yaml.safe_load` 直接读 config.yaml ② 尝试 `hermes_cli` 导入 ③ 降级到 b_layer 配置（openai 凭据）。

### 坑点 4: 会话去重太激进 → 冷却制

同 session 内同一 skill 永不再推荐。修复：冷却制 60s，非永久。

### 坑点 5: 预过滤中文单字匹配太宽

初版单字匹配 → 几乎所有 skill 匹配。修复：双字组合 + skill 名权重 ×3 + A 层命中加权 ×10。

### 坑点 6: B 层硬编码 Ollama → 三后端

初版只支持 Ollama。修复：main / ollama / openai 三后端。`main` 是推荐默认值。

### 坑点 7: openai 后端无 api_key 静默失败

`_match_b_openai()` 检测 api_key 为空 → `return None`，不抛异常。改用 `main` 或填 key。

### 坑点 8: B 层日志误导 — "Ollama调用失败" ≠ Ollama provider

日志 "B 层 Ollama 调用失败" 实际 provider 可能是 main。已改为 `B 层调用失败（%s/%s 降级跳过）` 显示实际 provider 和模型。

### 坑点 9: A 层正则中英混合不匹配 + 文档修复未落地（2026-06-09 复现）

**症状:** "报 KeyError" 不匹配 "报错"。SKILL.md 声称已修复为 `Error|报.*Error|KeyError|Traceback`，但 a_rules.json 实际仍为 `debug|修复|报错|bug|异常|不工作|调试`——文档修复未落地到数据文件。

**根因:** 坑点 1（规则回退）的延迟写盘系统修复后，手动编辑 a_rules.json 的变更可能未被正确保存。或修复写在旧会话中被旧会话内存副本覆盖。

**当前状态:** 2026-06-09 TDD 测试中场景 2 因此失败。

### 坑点 19: Dashboard/UI 美化任务 → SSR 推荐全废（2026-06-10 实战）

**症状:** 用户说"美化 Dashboard"时，SSR 推荐 `mcp-builder`/`huashu-nuwa`/`imagegen-*`/`code-to-video`/`songsee`——和仪表盘美化零关系。A 层正则匹配到"设计/美化/UI"关键词就乱推。

**根因:** SSR 的 A 层按关键词匹配，设计类宽泛词命中太多无关 skill。B 层 bge-m3 也救不回来——"美化 dashboard"的语义向量和实际需要的 design skill 距离太远。

**正确做法:** 设计/美化任务 **不要依赖 SSR 推荐**。手动扫描可用 design skill → 择优加载。详见 `references/dashboard-beautification-combo.md` 的四 skill 组合工作流。

### 坑点 10: SSR 可能完全不工作且无可见症状

A 层 0 命中 + B 层静默失败 = SSR 零产出但对话正常。验证命令见「完整测试流程」Step 1。

## TDD 基准测试（RED→GREEN→REFACTOR）

测试脚本: `tests/ssr_tdd_baseline_test.py` — 一键执行完整 TDD 循环（v0.5.0 含 Embedding 层）。
执行: `python3 ~/.hermes/skills/software-development/smart-skill-router/tests/ssr_tdd_baseline_test.py`

| 阶段 | 规则集 | 得分 | 说明 |
|------|--------|:--:|------|
| 🔴 RED | 空规则集 | 0/5 | 模拟无 SSR，验证 5 场景全部失败 |
| 🟢 GREEN (A 层, 修复后) | 关键词正则 | 5/5 | 补 `报.*Error` + `research-paper-writing` |
| 🟢 GREEN (bge-m3) | Embedding 206 skill | 5/5 | bge-m3 中文区分度远优于 nomic |
| 🟠 nomic (对照) | Embedding 246 skill | 5/5 | 但排名极差（详见 benchmark） |
| 🔵 REFACTOR | — | 无需 | 5/5 满分 |

### 基准场景（v0.5.0+ bge-m3 实测 2026-06-09）

| # | 用户消息 | 期望 skill | A 层 | bge-m3 | bge 排名 | nomic 排名 |
|---|---------|-----------|:--:|:--:|:--:|:--:|
| 1 | 帮我设计一个响应式导航栏 | brainstorming, ui-ux-pro-max, popular-web-designs | ✅ | ✅ | ui-ux #5, pop #29 | >100 |
| 2 | 这段代码一直报 KeyError | diagnose, systematic-debugging | ✅ | ✅ | diag #41, sys #14 | diag #138, sys #86 |
| 3 | 生成一个 ASCII 猫咪图 | ascii-art | ✅ | ✅ | **#1** 🎯 | >100 |
| 4 | 帮我写论文的 Related Work | research-paper-writing, planning-with-files | ✅ | ✅ | rpw #10, pwf #54 | rpw #69, pwf ? |
| 5 | 分析贵州茅台的均线走势 | technical-analysis, tushare-finance | ✅ | ✅ | (A 层全中) | (A 层全中) |

> **2026-06-09 bge-m3 对比 nomic-embed-text：bge-m3 排名提升 6-10x。** ascii-art 直接排 #1，ui-ux-pro-max 排 #5。
> nomic 所有期望 skill 排名 100+，净贡献 0。

## 与其他插件的关系

SSR 负责 skill 推荐，护栏插件负责质量推荐——互补不冲突。禁止擅自关闭其他插件功能。两者都通过 pre_llm_call 注入上下文，Hermes 支持多 hook 并行。

## 完整测试流程（6 步 · 2026-06-05 实战验证）

每次重启 Hermes 或用户要求「测试 SSR」时，按以下顺序执行：

### Step 1: 存活确认

```bash
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
```

预期输出：`可用 skill: N | A 层规则: N | B 层: main/deepseek-chat timeout=30s`

判定：

| A 层规则 | B 层状态 | 实际效果 | 动作 |
|:-------:|---------|---------|------|
| >0 | main/正常 | ✅ 至少 A 层工作 | 进入 Step 2 |
| >0 | main/超时 | ⚠️ B 层不可用 | A 层仍兜底，记备忘 |
| 0 | main/正常 | ⚠️ 仅 B 层兜底 | 可接受，等待 A 层积累 |
| **0** | **超时** | ❌ SSR 形同虚设 | **立即降级为手动匹配** |

### Step 2: TDD 基准测试

```bash
python3 ~/.hermes/skills/software-development/smart-skill-router/tests/ssr_tdd_baseline_test.py
```

- 🔴 RED: 0/5（验证空规则集全部失败）
- 🟢 GREEN: 目标 5/5（v0.5.0+ bge-m3 实测 5/5，含 nomic 对照）
- 🔵 REFACTOR: 有失败项时对比 A 层/bge-m3/nomic 找出缺口

### Step 3: A 层现场命中

```bash
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -10
```

检查：
- 命中规则是否与用户消息语义匹配（不滥推）
- 不同 session 是否都能命中（不挑 session）
- hit count 是否持续增长（规则在训练中）

### Step 4: B 层连通性

```bash
# 查 B 层最近状态
grep -E 'B 层|b_layer' ~/.hermes/logs/agent.log | tail -5
```

关键信号：

| 日志 | 判定 |
|------|------|
| `B 层命中: [...]` | ✅ 正常工作 |
| `401 Authorization` | ❌ API key 失效，需重新配置 |
| `timed out` | ⚠️ 网络/超时，检查 `b_layer.timeout` |
| 无日志 | ⚠️ B 层从未被调用（A 层全拦截或 silent fail） |

### Step 5: 当前 Session 日志

```bash
grep '<session_id>' ~/.hermes/logs/agent.log | grep ssr
```

确认 SSR 在本次会话中是否有产出。如果无产出但消息语义应匹配 → 检查 A 层 pattern 覆盖缺口。

### Step 6: 边界情况

- **无匹配消息**：如「重启了测试ssr」→ 预期无推荐（不滥推）
- **Session 缓存**：同 session 同 skill 不重复推（冷却制 60s）
- **降级路径**：A 层失效 → B 层兜底 → 不影响对话
- **配置漂移**：`b_layer.provider: main` 但日志写「Ollama 调用失败」→ warmup 代码的遗留信息，以 config 为准（见 ssr-integration 坑点 8）

## v0.6.1 测试验证（2026-06-10）

| 步骤 | 检查项 | 结果 |
|:--:|--------|:--:|
| 1 | 存活确认 | ✅ 296 skill · 100 A层 · bge-m3 296 emb · B层 main |
| 2 | TDD 基准 | ✅ 5/5 GREEN (bge-m3) · nomic 5/5 (排名差) |
| 3 | A 层现场命中 | ✅ 最新 session 命中 12 skill |
| 4 | B 层连通性 | ✅ A 层全覆盖，B 层未被调用（正常） |
| 5 | 智能冷却代码 | ✅ `_smart_cooldown()` L181 · `_COOLDOWN_TRACKER` L236 |
| 6 | 增量索引代码 | ✅ `_AUTO_SYNC_INTERVAL=600` L322 · `_check_skills_changed()` L920 |

**结论：v0.6.1 = 当前功能天花板。** 6 Phase 全部闭环，无遗留待办。

## v0.6.1 新增功能（2026-06-10）

两项增强已部署到 `~/.hermes/plugins/ssr/__init__.py`：

### 1. 智能冷却（Phase 5a）

`_smart_cooldown()` 取代原有的 `_phase_cooldown()`，实现自适应冷却：

| 规则 | 条件 | 冷却调整 |
|------|------|:--:|
| 已加载检测 | 用户消息含 skill 名或"用 xxx/加载 xxx" | ×3 |
| 反复推荐未加载 | 同一 skill 推荐 3+ 次未加载 | ×0.5 |
| 明确不需要 | 同一 skill 推荐 5+ 次未加载 | 跳过（-1） |
| 紧急消息 | 用户消息含 快/急/马上/立刻/urgent | ×0.5 |
| 任务切换 | 检测到 另外/换个/还有 等切换词 | 重置全部冷却 |
| 默认 | 以上都不适用 | 使用分阶段冷却 |

**追踪机制：** `_COOLDOWN_TRACKER` 字典：`{session_id: {skill_name: {recs, last_rec, loaded}}}`
- `loaded` 通过正则检测用户消息中的"用/加载/调用 skill名"模式自动标记
- 任务切换 → 清空对应 session 的追踪数据

### 2. 增量索引自动运行（Phase 5b）

两处改进：

**2a. 定时自动全量 sync（`_AUTO_SYNC_INTERVAL = 600`）**

`_pre_llm_call` 中每次调用检查距上次全量 sync 的时间。超过 10 分钟 → 自动触发 `_sync_embeddings()`，检测新增/删除/描述变更并更新 embedding 索引。

**2b. Description 变更检测**

`_check_skills_changed()` 返回值从 `(new, removed)` 扩展为 `(new, removed, changed)`：
- 已有 skill 的 description 变更 → 自动重建 embedding
- 内存中的 `_SKILL_INDEX` 同步更新
- 变更数计入日志：`热更新: +N -M ΔK skill → 索引 X`

四项增强已完成并部署到 `~/.hermes/plugins/ssr/__init__.py`：

### 1. 描述富化（3.1）

`_get_skill_info()` 新增正文提取逻辑（lines 375-424）：
- 定位 SKILL.md frontmatter 后的正文起点（第二个 `---`）
- 跳过代码块（`` ``` ``）、标题行（`#`）、表格行（`|`）、引用行（`>`）、短行（<15字符）
- 收集前 3 段有效散文段落
- 拼接为 `body_desc`（截断 300 字符）
- 如果已有 YAML description 且 body_desc 不重复 → 追加富化 `"{desc}. {body_desc}"`
- 如果无 YAML description → 用 body_desc 兜底

**效果**: Embedding 索引不再仅靠一句 YAML description，而是有 2-3 段实际功能描述作为语义载体。bge-m3 匹配质量提升。

### 2. 中文查询增强（3.2）

`_expand_chinese_query()` 新增 14 域中英映射（lines 652-692）：
- 设计/UI → `design, UI, interface, frontend, layout, CSS`
- 调试/报错 → `debug, error, diagnose, fix, troubleshoot`
- 金融/股票 → `finance, stock, trading, market, technical analysis`
- 论文/学术 → `academic, paper, research, writing, journal, citation`
- 旅行/旅游 → `travel, trip, itinerary, tour, hotel, road trip`
- 部署/上线 → `deploy, release, production, server, CI/CD, DevOps`
- 数据/分析 → `data analysis, statistics, visualization, chart, dashboard`
- 音乐/音频 → `music, audio, song, composition, sound`
- 视频/剪辑 → `video, animation, render, edit, media, encoding`
- AI/模型 → `AI, model, training, inference, LLM, machine learning, neural network`
- API/后端 → `API, backend, server, REST, HTTP, database, SQL`
- 安全/加密 → `security, encryption, authentication, firewall, vulnerability`
- 漫画/艺术 → `art, illustration, drawing, pixel, ASCII, creative`
- 游戏/玩法 → `game, gameplay, design, level, character, RPG, simulation`

**效果**: 用户输入中文查询时自动追加英文领域关键词，提升 bge-m3 跨语言 Embedding 匹配精度。覆盖 bge-m3 已知中文领域术语盲区（金融、UI、调试等）。

### 3. 会话命中日志（4.2）

`_SESSION_STATS` 统计字典 + `_STATS_LOG_INTERVAL = 10`（lines 1177-1198）：
- 每 session 跟踪: `calls`（总调用）、`hits_a`（A层命中）、`hits_b`（B层命中）、`misses`（无匹配）、`skipped_low_conf`（低置信跳过）
- A 层命中后 `calls % 10 == 0` → 触发 `_log_session_stats()` 输出日志
- B 层命中同理
- 日志格式: `[ssr] 会话统计 | session=xxx | 调用=N | A层命中=N | B层命中=N | 无匹配=N | 低置信跳过=N | 命中率=N%`

### 4. Dashboard 统计面板（4.1）

Dashboard (`~/.hermes/dashboard/server.py`) 新增 `/api/stats` 端点：
- `read_stats()` 返回: `intercept_count`、`error_count`、`sessions`、`last_solidify`
- 前端 `renderStats()` 渲染 6 格统计卡: 规则总数（ban/gap/lazy/meta 分类）、累计命中、拦截次数、错误记录、高误报规则、陈旧规则
- 切换语言时自动 refres 统计数据

---

## 当前状态

**v1.5.0** (2026-06-20): 推荐位置硬编码 prepend（前置推荐到开头）。删除 `_ssr_position()` 函数和 `post_llm_call` 条件检查——append 模式结构性无解（截断从尾部来=推荐位置）。`post_llm_call` 必须开启。SKILL.md 配置节无 position 字段。

**Embedding 模型**: bge-m3 (1024维, q4_k_m 438MB)。改模型时排查: `ollama list` vs `ssr.embedding.model` 一致性。切换后必须 `rm embeddings.json` + 重启。

**配置**: `ssr.embedding.provider: ollama` + `ssr.embedding.model: bge-m3`
**A 层**: 6 条全手动规则, auto_gen_rules: false
**计划**: `~/.hermes/plans/ssr/noise-reduction/` (✅已完成) + `~/.hermes/plans/ssr/smart-skill-router/`

### 坑点 23: 空 a_rules.json ≠ SSR 干净 — 诊断陷阱（2026-06-14 实战）

**症状:** 重启 Hermes 后 a_rules.json 为空（2 bytes, `{}`），embeddings.json 已重建（8MB），但 SSR 推荐仍充斥 huashu-nuwa、paper-spine-rewrite、design-taste-frontend-v1 等与当前 CMG/SSR 话题完全无关的 skill。

**根因:** a_rules.json 清空只影响 A 层关键词匹配。B 层 bge-m3 embedding 是独立搜索——embeddings.json 重建后仍包含所有 296 skill 向量。用户消息的语义向量与无关 skill 的余弦相似度可能仍然较高（bge-m3 中文领域术语盲区，坑点 20）。

**正确诊断流程:**
1. ❌ 不要看 a_rules.json 是空的就断定「SSR 干净」
2. ✅ 必须查看用户消息中 [SSR] 块的实际推荐内容
3. ✅ 判断推荐是否与当前话题相关 → 不相关 = B 层仍在产噪声
4. ✅ 此时 a_rules.json 清空是正确的，但没有 A 层兜底，B 层裸奔

**当前缓解：** 接受 B 层噪声作为已知限制。a_rules.json 清空后等待 A 层规则从用户行为中重新积累。不要指望「删了文件重启」能根治 bge-m3 的语义匹配质量。

**长期方向：** 换 embedding 模型。2026-06-14 已执行切换：bge-m3 → text2vec-bge-large-chinese (nn200433, 1024维纯中文, 207MB)。详见 `references/chinese-embedding-alternatives.md`。切换后需重启 Hermes 让 register() 重建索引。验证方法：对比 `ollama list` 和 `ssr.embedding.model` 确保一致（见坑点 24）。

### 坑点 14: nomic-embed-text 中文区分度极低 + bge-m3 方案（2026-06-09 实测）

**症状:** 5 个 TDD 场景中，nomic Embedding 层 top-5 结果大量重叠——`universal-tool-dispatcher` 和 `ai-short-film-production` 出现在 4/5 场景的 top-5 中。`diagnose` 在"KeyError 调试"查询中排 138/246 (sim=0.42)，`research-paper-writing` 在"论文 Related Work"查询中排 69/246 (sim=0.46)。

**根因:** nomic-embed-text 是为英文优化的模型。中英文混合的 skill description 导致 embedding 向量区分度极低——所有 skill 相似度挤在 0.37-0.65 窄带内。768维向量无法区分中文语义。

**解决方案: 换 bge-m3 (BAAI 多语言模型, 1024维)**

```bash
# 下载 + 导入（ollama pull 太慢，用 hf-mirror 手动下载）
curl -L -o ~/Downloads/bge-m3-q4_k_m.gguf \
  "https://hf-mirror.com/groonga/bge-m3-Q4_K_M-GGUF/resolve/main/bge-m3-q4_k_m.gguf"
ollama create bge-m3 -f <(echo "FROM ~/Downloads/bge-m3-q4_k_m.gguf")

# 改 config
hermes config set ssr.embedding.provider ollama
hermes config set ssr.embedding.model bge-m3

# 删旧索引，重启后自动重建
rm ~/.hermes/plugins/ssr/embeddings.json
```

**bge-m3 效果:** ascii-art 排 #1/206 (sim=0.52)，ui-ux-pro-max 排 #5 (sim=0.54)，research-paper-writing 排 #10 (sim=0.52)。区分度从 nomic 的 0.1 提升到可用级别。

### 坑点 15: Embedding 维度不兼容静默覆盖（2026-06-09）

**症状:** 换 bge-m3 (1024维) 后忘记删 nomic 索引 (768维)。旧向量与新查询维度不同 → 余弦相似度计算报错或返回 0。

**修复:** 换 embedding 模型后必须删除旧索引文件，让重启时 `_sync_embeddings()` 全量重建。`rm ~/.hermes/plugins/ssr/embeddings.json`

### 坑点 24: config 中的 embedding 模型未实际安装（2026-06-14 实战）

**症状:** `ssr.embedding.model` 写的是 `bge-m3`，但 `ollama list` 只显示 `nomic-embed-text` 和 `qwen2.5:3b`——bge-m3 根本没装。SSR 推荐质量极差（全是不相关的 huashu-nuwa、paper-spine、design 类 skill），但无任何错误日志。a_rules.json 清空后 B 层裸奔，噪声更明显。

**根因:** config 和实际安装是两套系统——改了 config 不等于模型在 Ollama 里。SSR 的 embedding 构建被 try/except 包裹，若模型缺失可能静默降级到旧索引或空索引。

**诊断:**
```bash
# 对比期望 vs 实际
grep 'embedding:' -A 3 ~/.hermes/config.yaml
ollama list | grep -i embed
```

### 坑点 25: _pre_llm_call miss 路径无日志 → 假性沉默（2026-06-14 实战）

**症状:** SSR 注册成功，a_rules.json 为空（2 bytes），agent.log 无 `[ssr]` 输出——看起来像 hook 未触发。实际是 A 层空 + B 层 miss → `_pre_llm_call` 第 1588-1589 行 `stats["misses"] += 1; return None` 无任何 logger 调用。对比：A/B 命中、置信不足、异常全都有 logger.info/warning。唯独 miss 路径零输出。

**修复 (v0.6.2):** 补 `logger.info("[ssr] 无匹配（A层 %d 条 + B层 %s, 本轮第 %d 次）", len(_A_RULES), _b_provider(), stats["calls"])`。

详见 `ssr-operations` 的 [`references/silent-miss-path.md`](../devops/ssr-operations/references/silent-miss-path.md)。

### 坑点 26: a_rules.json 空覆盖导致规则永久丢失（2026-06-14 实战 · v0.6.2 修复）

**症状:** 重启后 a_rules.json 从有规则变为 2 字节 `{}`，所有 A 层规则永久消失。

**根因:** v0.6.1 `_save_a_rules()` 无空覆盖保护。`_flush_a_rules()` 每 5 次命中写盘一次——若此时 `_A_RULES` 全局 dict 被异常重置为空（模块热重载、内存异常），则 `json.dumps({})` → 2 字节 `{}` → 所有规则永久丢失。2026-06-14 实战确认：主 session 内存规则完好，但文件已被覆写，新 session 加载 0 条。

**修复 (v0.6.2):**
1. **写前备份:** `_save_a_rules` 检测空覆盖 → 自动备份到 `a_rules.json.bak`
2. **损坏备份:** `_load_a_rules` 解析失败 → 自动备份到 `a_rules.json.corrupted`
3. **诊断日志:** `register()` 加 3 行 logger.info（`加载 A 层规则: N条 → 清理后: N条 → 单字净化后: N条`）定位清空步骤

**恢复步骤:** 详见 `references/a_rules-recovery.md`。
快速恢复：`cp ~/.hermes/plugins/ssr/a_rules.json.bak ~/.hermes/plugins/ssr/a_rules.json` + 重启。

### 坑点 27: SSR echo 输出格式截断 — `[SSR] 建议加载:\n` skill 名不显示（2026-06-14 确认根因+修复）

**症状:** 用户看到 `[SSR] 建议加载:\n` 字面量反斜杠-n，skill 名不显示。

**根因（已确认）:** `__init__.py` L1424-1427，Python 字符串转义过度：
```python
# ❌ L1424: "\\n" = 两个字面字符（反斜杠+n）
body = "\\n".join(lines)
# ❌ L1427: f-string 中 \\\\n = 字面量 \n
return f"{prefix}\\\\n{body}"
```
`"\\n"` 是两个字面字符，`"\n"` 才是换行。f-string 同理——`\\\\n` = 字面量。

**修复 (v0.6.3):**
```python
# ✅ L1424: 实际换行拼接
body = "\n".join(lines)
# ✅ L1427: 实际换行分隔
return f"{prefix}\n{body}"
```
L1426 enforce 模式同修。共 3 处改动，影响 `__init__.py` L1424/1426/1427。

**修复:**
1. 如果 config 写的模型不在 ollama list 中 → `ollama pull <模型名>`
2. `rm ~/.hermes/plugins/ssr/embeddings.json`
3. 重启 Hermes（完全退出再开，非 /new）
4. 发消息验证 [SSR] 推荐是否与当前话题相关

**设计启示:** SSR embedding 层是语言无关的可插拔架构。中文用户用中文模型（text2vec-bge-large-chinese），英文用户用英文模型。维数不是决定性因素——领域专注度 > 维数。

**症状:** 发现格式不兼容后直接 `rm a_rules.json`，B 层 3 次累积升级的 10+ 条规则消失。auto-gen 粗糙关键词准确率 10%，完全无法替代。

**修复:** `cp a_rules.json a_rules.json.bak.$(date +%Y%m%d)` 永远先备份。格式问题优先修复而非清空。

### 坑点 12: 三次纠正修改上限仍未去上限（2026-06-09）

用户说"不设限"后，AI 每次都只放宽而非去除：1→3→8→10。根因：替用户做筛选判断——"太多怕不准"。用户明确要的是"全推，我自己判断"。

**正确做法:** 上限不是设计参数——是错误假设。匹配多少推多少。精准度由漏斗保证，数量由匹配度决定。

### 坑点 16: 合并去重时 `seen.add(item)` 而非 `seen.add(item["name"])`（2026-06-09）

**症状:** `_match_a_layer` 合并关键词和 Embedding 结果时，`seen.add(item)` 把 dict 当 key → `TypeError: unhashable type: 'dict'`。关键词结果先插入（`seen.add(item["name"])`），Embedding 段漏了 `["name"]`。

**根因:** 代码 review 漏了 Embedding 合并段。两段代码结构相同但第二段少写了 `["name"]`。

**修复:** `seen.add(item)` → `seen.add(item["name"])`。这类对称代码段写完后必须逐句对照。

**教训:** 合并循环写两遍一模一样的逻辑时，第二遍最容易漏细节。写完后 diff 两个循环逐行对一遍。

### 坑点 19: 全量 write_file 重写丢功能 + i18n 混语言（2026-06-10 Dashboard v3 实战）

**症状:** 两次全量重写 `dashboard.html` → 主题切换按钮消失 + i18n 中英混（`zh.col-skills: "Skill"`）。

**根因:** `write_file` 覆盖整个文件时不 diff 旧版，依赖自我感觉"都保留了"。

**修复:**
1. 重写后必须从旧版 diff 逐项核对功能清单
2. i18n 对象 zh 和 en 独立定义，不复制粘贴混编
3. 表头/按钮/模态 全部走 `data-lang` + `t()` 动态翻译，不硬编码

（v0.5.1 修复 · 2026-06-09 实战）

**症状:** GREEN 测试 4（"帮我写论文的 Related Work 部分"）期望命中 `research-paper-writing`，但 A 层结果中缺失。实际在 59 秒前的测试 1（"设计响应式导航栏"）中该 skill 已被推荐——冷却未到期，`continue` 直接丢弃。

**根因:** 冷却制以前用 `continue` 跳过命中的 skill（不进入 `fresh` 列表）。但冷却不区分上下文——同一 skill 在不同消息中完全不同的语义需求，被冷却一刀切吞掉。

**修复 (v0.5.1):**
```python
# ❌ 旧：丢弃
if now - last_t < COOLDOWN:
    continue

# ✅ 新：标记，保留
if now - last_t < COOLDOWN:
    s["shown_recently"] = True
```
展示层追加 `(刚才)` 标记，AI 自行判断是否加载。`if not fresh: return None` 也移除了——不再因为全部在冷却而返回空。

**教训:** 冷却作用于展示层（"刚才推过了，别重复显示"），不应作用于匹配层（"命中了就是命中了"）。

### 坑点 20: bge-m3 中文设计/UI 查询大面积漏推（2026-06-10 实战确认）\n\n**症状：** 用户连续多次说「美化仪表盘」「dashboard美化」，SSR 推荐结果：\n- `code-to-video`、`manim-video`、`songsee`（视频/音频类，完全无关）\n- `mcp-builder`、`huashu-nuwa`（工具/角色类，完全无关）\n- `redesign-existing-projects`（偶尔正确，但不稳定）\n\n正确的 skill（`frontend-design`、`high-end-visual-design`、`popular-web-designs`、`ui-ux-pro-max`）从未被 A 层关键词命中，bge-m3 embedding 也推不出来。\n\n**根因：** `_expand_chinese_query()` 为「设计」追加了 `design, UI, interface, frontend, layout, CSS`，但 bge-m3 的 1024 维向量对这些词的语义区分度不足——\"design\" 同时命中 `code-to-video`（video design）、`manim-video`（animation design）、`algorithmic-art`（art design）。14 域映射的英文关键词暴增了 noise。\n\n**缓解（当前）：** AI 看到垃圾推荐后必须自行忽略，手动扫描 skills 列表加载正确的技能。\n\n**根除方向（v0.7.0+）：**\n1. A 层手动规则优先——为「美化/仪表盘/UI」添加精确正则（如 `美化|重设计|UI.*改|仪表盘.*美` → frontend-design, high-end-visual-design）\n2. Embedding 候选加负向过滤——排除 video/audio/3D 领域的 skill\n3. 中文查询增强改为上下文感知——检测到「仪表盘/dashboard」时不追加泛化的 design/UI 关键词\n\n**验证方法：**\n```bash\n# 检查当前 A 层是否有设计类规则\ngrep -i '美化\\|仪表盘\\|设计.*UI\\|redesign' ~/.hermes/plugins/ssr/a_rules.json\n# 查看 bge-m3 top-10 对「美化仪表盘」的匹配\npython3 -c \"\nimport json, numpy as np\nwith open('$HOME/.hermes/plugins/ssr/embeddings.json') as f:\n    emb = json.load(f)\n# 手动跑 embedding 查询看 top-10\n\"\n```\n\n### 坑点 19: Dashboard 新增 API 路由后必须重启服务器（2026-06-10）

**症状：** dashboard.py 新增 `/api/stats` 路由，修改后浏览器刷新 404。代码已写入但旧进程仍在运行。

**修复：**
```bash
lsof -ti:8766 | xargs kill -9
cd ~/.hermes/plugins/ssr && python3 dashboard.py &
```
确认：`curl http://localhost:8766/api/stats`

### 坑点 18: auto-gen 噪音可通过配置关闭（v0.5.1 · 2026-06-09）

**症状:** auto-gen 生成 2010 条规则，准确率仅 10%。日志声称 2009 条但 a_rules.json 实际仅 10 条（cleanup 秒删）。垃圾规则淹了精确定制的手动规则。

**修复:** `ssr.auto_gen_rules: false` 关闭 auto-gen。代码新增 `_auto_gen_enabled()` 函数读取此配置，默认 true（向后兼容）。关闭后仅保留 100 条手动规则 + bge-m3 embedding 语义匹配。

**配置:** `hermes config set ssr.auto_gen_rules false`

### 坑点 28: 手动改 `__init__.py` 时函数误入模块 docstring（2026-06-20 实战）

**症状：** 在 `__init__.py` 顶部手动插入 `_ssr_position()` 函数，恰好落在模块 docstring 的 `"""`...`"""` 之间。Python 把函数定义当作文档字符串内容 → 后续裸文字变成非法语句 → 插件无法加载。

**检测：** `python3 -c "compile(open('$HOME/.hermes/plugins/ssr/__init__.py').read(), '__init__.py', 'exec')"` 

**正确做法：**
1. 函数必须放在 docstring 闭合 `"""` 之后
2. 必须放在 `from __future__ import annotations` 之后
3. 安全位置：常量区（`A_RULES_PATH`）之后、配置区之前
4. 改后立即 `python3 -c compile(...)` 验证

### 坑点 29: 全角标点（`：` `（）`）触发 Python 3.12 SyntaxError（2026-06-20 实战）

**症状：** docstring 中含全角冒号 `：` (U+FF1A) → `SyntaxError: invalid character '：' (U+FF1A)`。

**修复：** 代码（含 docstring）用半角标点。全角标点只用于面向用户的消息字符串。

### 坑点 31: 改代码后必须测试再声称完成（2026-06-20 实战）

**症状：** 完成位置修复后直接说"搞定"。用户纠正：「测试了吗？通过测试再说」。

**正确流程：**
1. 编译验证：`python3 -c "compile(...)"` 
2. 函数行为测试：默认值、边界条件（无 session_id、cache miss）
3. 配置文件一致性：plugin.yaml hooks 声明、SKILL.md 配置节
4. 全绿后再声称完成

### 坑点 30: append 模式结构性无解——截断从尾部来=推荐在尾部（2026-06-20 最终确认）

**症状：** `position: append`（旧默认）下 SSR 推荐通过 `pre_llm_call` 注入到回复末尾。长回复末尾被 Hermes 截断 → SSR 推荐不可见。`prepend` 模式作为规避方案存在但需手动配置。

**根因：** 不是 bug，是物理限制。Hermes 回复截断从尾部开始，append 模式把推荐放在尾部——两者在同一位置，截断必中。**这不是可以通过调整参数修复的问题，append 和截断是互斥的。**

**修复（v1.5.0，已落地）：** 硬编码 prepend。
- 删除 `_ssr_position()` 函数——不再读取配置
- 删除 `post_llm_call` 中的条件检查——始终前置
- SKILL.md 配置节移除 `position` 字段
- `post_llm_call` hook 必须开启（`ssr.hooks.post_llm_call: true`）

**正确做法：**
1. 识别结构性限制 vs 可配置 tradeoff——append 是前者，不是后者
2. 不要提供"注定失败"的选项——假灵活性比硬编码更差
3. 被人质疑时坚持分析结论，不是谁的口气大听谁的

**本会话教训：** AI 两次摇摆——先硬编码→用户问"硬编码是对的吗"→AI 回退到可配置→用户纠正"所以你一开始是对的为什么不坚持"→最终确认硬编码。如果第一次就站稳分析，省了两轮往返。

### 坑点 19: README 不得暴露隐私信息（2026-06-10 用户纠正）

**症状:** README badge 写了 `skill count 296`、`A rules 100`，暴露用户已安装 skill 数量和规则数量。README 还列出了 Dashboard 美化用到的 4 个设计 skill 名称（redesign-existing-projects 等），暴露用户开发工具链。用户纠正：「我都说不要包含隐私，这些包括skill数量和设计系统都算隐私」。

**修复:** README badge 只保留 version/license/platform。Dashboard 章节只描述面向用户的功能（亮暗切换/中英文），不描述开发过程的「驱动 skill」「设计系统」「Double-Bezel 架构」。Embedding 对比表去掉具体 skill 排名数据（如 ascii-art#1）。CMG 引用全部删除。

**原则:** 对外文档 = 用户看到的功能。开发过程、工具选择、系统统计数据 = 内部信息，不入 README。

### 坑点 20: i18n 必须纯语言——zh 不含英文、en 不含中文（2026-06-10 实战）

**症状:** zh 版 i18n 数据中 `col-skills` 值为 `"Skill"`（英文）、`save` 值为 `"保存（重启生效）"` 但 en 版中 `col-skills` 又是 `"Skills"`。切语言时出现「匹配技能」变「Skills」但按钮 title 仍硬编码中文 `"编辑"/"删除"`。用户说「中文版有英文，英文版有中文」。

**修复:**
1. i18n 对象逐条审计——zh 所有 value 必须是纯中文、en 所有 value 必须是纯英文
2. 动态渲染内容（如 `render()` 中的按钮 title）必须通过 `t("btn-edit")` 走 i18n，不可硬编码
3. `toggleLang()` 必须同时调用 `render()` 和 `loadStats()` 以刷新动态内容
4. 统计卡 label（如 "命中率"）不能用拼接（`t("col-hits")+"率"`），必须独立 key（`"hit-rate"`）

### 坑点 22: 空索引零告警——embeddings.json 和 a_rules.json 同时为空（2026-06-12 生产环境确认）

**症状：** SSR 注册日志正常（"插件注册完成"），但所有推荐全由 B 层 LLM 产出。查 embeddings.json 含 0 skill（非文件缺失，是内容为 `{"skills":{}}`），a_rules.json 含 0 条规则。bge-m3 Ollama 端点完全可用。用户全程收到的推荐全部跑偏（本会话连续 10+ 条 SSR 建议与当前话题无关）。

**根因：** `register()` 中索引构建被 try/except 包裹。若构建中途任何瞬态错误（Ollama 超时、config 加载失败、维度不匹配），异常被静默吞掉——插件标记"已注册"，但两层索引全空。B 层成为唯一工作层，推荐质量从三层漏斗跌至 LLM 盲猜。

**检测：**
```bash
# embeddings.json 含 0 skill（不是文件缺失）
python3 -c "import json; d=json.load(open('$HOME/.hermes/plugins/ssr/embeddings.json')); print(len(d.get('skills',{})))"
# a_rules.json 含 0 条
python3 -c "import json; r=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(len(r if isinstance(r,list) else r.get('rules',[])))"
```

**修复：** `rm` 两个文件 + 重启 Hermes（完整重启，非 /new）→ `register()` 重建全部索引。
详见 `ssr-operations` skill 的对应坑点。

**症状:** 重写 CSS 变量时去掉了 `[data-theme="light"]` 规则和 `toggleTheme()` 函数。用户立即指出「黑白切换没有了」。

**修复:** Dashboard 重设计时必须保留三个要素：① `[data-theme="light"]` CSS 变量覆盖 ② `toggleTheme()` JS 函数 ③ `localStorage` 持久化恢复。重写后逐功能验证——加载→切亮色→检查背景色→刷新→确认保持。

用户问"可不可行"、AI 直接动手改代码。用户纠正："你别着急写啊，我问你可不可行哪个好。你别无脑按着我的做。先分析啊"

**正确做法:** 涉及 SSR 改动前 → 先分析可行性/方案对比/影响链 → 让用户选方向 → 再动手。

详见 `references/green-baseline-results.md`。

## 外部工具集成

SSR 可在编程意图时推荐 Reasonix 作为子 Agent。详见 `references/reasonix-integration.md`。
"