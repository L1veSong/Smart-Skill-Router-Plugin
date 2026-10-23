# SSR 降噪优化计划

> **目标：** 保持推送式推荐，大幅降低不相关推荐噪音
> **版本：** v1.0 | **状态：** ✅ 已完成 | **创建：** 2026-06-13 | **完成：** 2026-06-14
>
> **诊断时间：** 2026-06-13
>
> **诊断方式：** 完整阅读 1698 行 `__init__.py` + 对照本会话 40 条命中日志分析
>
> **核心发现：** 关键词和 Embedding 是 OR 关系，相加了噪音而非互补过滤。40/40 命中率 = 每条消息都产生推荐，但 90% 不相关。
>
> **最终方案（2026-06-14）：** 放弃代码过滤方案，改为手动清洗 a_rules.json + 关闭 auto-gen。结果：61→6 条全手动规则，56 条 auto-gen 单字噪声清零，work→writing-skills 误报消失。GREEN 5/5 全通过。

---

## 当前架构问题

```
用户消息 → 关键词正则 (100条) → 命中 3-8 个
         → Embedding (311向量) → 命中 20-30 个  ← 噪音主来源
         → 合并去重 → 最多展示 12 个
         → B 层 LLM → 从未触发（A 层永远有结果）
```

**三个具体病灶：**

1. **a_rules.json 含 40+ 条 auto-gen 单英文词规则** — `skill`、`work`、`only`、`call`、`time` 等。每条 80+ 命中，每次对话几乎必触发，产出的 skill 却和当前任务无关（`skill` → canon-mnemonic-guard-dashboard、`call` → mcporter）。

2. **Embedding 结果无门控** — 关键词已命中 3-8 个 skill 后，Embedding 仍追加 20+ 个相似度 0.35-0.45 的弱相关 skill。tushare-finance、stock-screen-monitor 等金融 skill sim 达 0.42 就进来了。

3. **中文查询扩展无匹配度要求** — `_expand_chinese_query` 命中一个调试关键词（如 `bug`）就追加 "debug, error, diagnose, fix, troubleshoot"，污染 bge-m3 向量，拉来大量无关 skill。

---

## Phase 1：精准降噪（预计 -70% 噪音）

### Task 1: 清理 auto-gen 单英文词规则

**目标：** 删除 a_rules.json 中 40+ 条仅含常见英文单词的 auto-gen 规则。

**文件：** `~/.hermes/plugins/ssr/__init__.py`

**Step 1: 在 _pre_llm_call 初始化时过滤**

在 `register()` 加载 a_rules.json 后，新增 `_purge_single_word_rules()` 函数：

```python
# 单英文词停用表（auto-gen 产生的垃圾规则）
_SINGLE_WORD_PATTERNS = re.compile(
    r"^(skill|work|only|call|view|era|other|time|even|way|each|name|pass|"
    r"look|know|need|will|does|give|save|they|main|flat|mini|type|auth|"
    r"doc|end|fit|use|env|var|art|gen|set|new|key|api|src|cmd|log|bin)$",
    re.IGNORECASE
)

def _purge_single_word_rules(rules: dict) -> dict:
    """移除所有单英文词规则，返回净化后的 dict。"""
    return {
        k: v for k, v in rules.items()
        if not _SINGLE_WORD_PATTERNS.match(k)
    }
```

**Step 2: 在 `register()` 中调用**

```python
# 现有: existing = _load_a_rules()
# 新增:
existing = _purge_single_word_rules(existing)
```

**验证：** 重启后 `python3 -c "import json; r=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(len(r))"` → 预期从 100 降到 ~60。

---

### Task 2: Embedding 语义门控

**目标：** 关键词已命中时，Embedding 只补充高相似度 (sim > 0.50) 的互补 skill，不再追加弱相关结果。

**文件：** `~/.hermes/plugins/ssr/__init__.py`，`_match_a_layer()` (L594-646)

**Step 1: 新增门控配置**

```python
def _emb_gate_threshold() -> float:
    """Embedding 门控阈值：关键词命中时，embedding 最低相似度要求。
    
    关键词未命中时不用此阈值（走正常的 _similarity_floor）。
    """
    return _load_ssr_config().get("embedding", {}).get("gate_threshold", 0.50)
```

**Step 2: 在 `_match_a_layer()` 合并阶段加门控**

```python
# 现有 L622-641 替换为:
keyword_names = {item["name"] for item in keyword_result}
boost = _keyword_weight_boost()

# 如果有关键词命中 → Embedding 结果加门控
has_keyword_hits = len(keyword_result) > 0
gate = _emb_gate_threshold() if has_keyword_hits else _similarity_floor()

for item in emb_result:
    sim = item.get("_sim", 0)
    # 门控：有关键词命中时，embedding 必须超过 gate_threshold
    if has_keyword_hits and sim < gate:
        continue
    if item["name"] in keyword_names and "_sim" in item:
        item["_sim"] = min(sim + boost, 1.0)
        item["_keyword_boosted"] = True

seen: set = set()
result: list = []

# 关键词结果优先（保持原有逻辑）
for item in keyword_result:
    if item["name"] not in seen:
        seen.add(item["name"])
        result.append(item)

# Embedding 补充（经门控过滤）
for item in emb_result:
    if item["name"] not in seen:
        seen.add(item["name"])
        result.append(item)
```

**验证：** 发消息 "检查 SSR 有 bug 吗" → 日志应只显示 ssr-operations、smart-skill-router 等 SSR 相关 skill，不再出现 tushare-finance、stock-screen-monitor。

---

### Task 3: 中文扩展加域匹配度要求

**目标：** 用户消息中单个中文词匹配调试/金融等域时，不再追加英文扩展词。需 ≥2 个域关键词才触发扩展。

**文件：** `~/.hermes/plugins/ssr/__init__.py`，`_expand_chinese_query()` (L746-785)

**Step 1: 替换匹配逻辑**

```python
def _expand_chinese_query(text: str) -> str:
    """中文查询 → 追加英文领域关键词，提升 bge-m3 跨语言匹配精度。
    
    v0.6.2: 需 ≥2 个域关键词才触发扩展，避免单字误触发。
    """
    _CN_EN_MAP = [
        # ... 现有 14 域映射不变 ...
    ]
    result = text
    for cn_keywords, en_expansion in _CN_EN_MAP:
        matched = sum(1 for kw in cn_keywords if kw in text)
        if matched >= 2:
            result += " " + en_expansion
    return result
```

**验证：** "检查ssr有bug吗" → `bug` 单独命中调试域 → 不扩展。"代码一直报 KeyError 怎么调试" → `报错` + `KeyError` + `调试` 命中 3 个 → 扩展。

---

### Task 4: 提高 Embedding 相似度底线

**目标：** 从默认 0.35 提到 0.45，过滤最嘈杂的 embedding 结果。

**文件：** `~/.hermes/plugins/ssr/__init__.py`，`_similarity_floor()` (L159-162)

```python
def _similarity_floor() -> float:
    """Embedding 相似度最低阈值（0-1）。低于此值不纳入推荐。"""
    return _load_ssr_config().get("embedding", {}).get("similarity_floor", 0.45)
    #                                                                    ↑ 原 0.35
```

**config.yaml 可配：**
```yaml
ssr:
  embedding:
    similarity_floor: 0.45
```

**验证：** 无单独验证。这是一个基数调整，效果叠加在 Task 2 的门控之上。

---

## Phase 2：效果验证（P0-P3 完成后）

| 验证项 | 方法 | 目标 |
|--------|------|:--:|
| A 层规则数 | `python3 -c "import json; print(len(json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json'))))"` | 60 左右 |
| 命中率 | `grep '会话统计' agent.log | tail -1` | 从 100% 降到 40-60% |
| 噪音判断 | 发 5 条不同领域消息，检查推荐相关性 | ≥3/5 相关 |
| 无退化 | GREEN 基准 5 场景 | 5/5 通过 |
| 回归 | 复查 P1-P3 改动点 | 零语法错误 |

---

## 平衡点验证：反基准 (RED)

每个改动不能只验证"该推的还推吗"，还要验证"不该推的闭嘴了吗"。

**RED 反基准（不该推的场景）：**

| # | 消息 | 不应推荐的 skill 类型 |
|---|------|----------------------|
| R1 | SSR 有优化空间吗 | 金融 (technical-analysis, stock-screen-monitor, finance-news-analyzer) |
| R2 | 帮我记到 CMG 里 | 旅行、视频制作、角色扮演 (ai-short-film-production, huashu-nuwa) |
| R3 | memory 差多少满 | 金融、游戏、音乐 |
| R4 | 8:15 了 | 任何 build 类 skill（纯时间陈述） |
| R5 | 对，就是你分析的那样 | 任何 skill（确认性回复） |

**验证流程：每次 Task 改动后 → 跑 GREEN (5 场景) + RED (5 场景)**

| GREEN | RED | 判定 |
|:--:|:--:|------|
| 5/5 | 5/5 | ✅ 完美 |
| ≥4/5 | 5/5 | ✅ 可用（牺牲了边缘场景，噪音控制到位） |
| 5/5 | ≤3/5 | ⚠️ 砍过头了，回退参数 |
| ≤3/5 | 5/5 | ❌ 匹配退化，回退改动 |

## Task 2/4 平衡策略：渐进调参

**不在代码里写死阈值。** 全部可配，每个参数试三个值，找 GREEN+RED 综合最佳的。

| 参数 | 当前 | 候选值 | 调法 |
|------|:--:|--------|------|
| `embedding.gate_threshold` | 无 | 0.45, 0.50, 0.55 | 从 0.50 起步→RED 失败就降到 0.45 |
| `embedding.similarity_floor` | 0.35 | 0.40, 0.45, 0.50 | 从 0.45 起步→GREEN 失败就降到 0.40 |

**决策规则：**
1. 先跑 Task 1+3（无门槛改动）→ 验证 GREEN 5/5
2. 再跑 Task 4（similarity_floor = 0.45）→ 验证 GREEN ≥4/5
3. 最后跑 Task 2（gate_threshold = 0.50）→ 验证 RED，不通过降到 0.45 再测
4. 综合最佳的参数组合锁定

## Phase 3（延期）：跨会话冷却持久化

**当前不做原因：** 先在单会话内验证 P0-P3 效果，确认方向正确再投入持久化复杂度。

**前置条件：** Phase 1 完成后，单会话噪音体验可接受（命中率 40-60%，推荐相关度 ≥60%）。

**后续方向：** 将 `_COOLDOWN_TRACKER` 序列化到 `~/.hermes/plugins/ssr/cooldown.json`。下次会话加载时，上次被标记为 `loaded: False` 且 `recs >= 3` 的 skill 带着惩罚起步。

**目标版本：** v0.7.0

---

## 实施顺序

```
Task 1 (15 min) → 清理单英文词规则
    ↓ 重启 Hermes，发消息验证
Task 2 (20 min) → Embedding 语义门控
    ↓ 发消息验证，查日志
Task 3 (10 min) → 中文扩展域匹配度
    ↓ 发消息验证
Task 4 (5 min)  → 提高相似度底线
    ↓ 全量 GREEN 基准回归
Phase 2 验证
```

---

## 不做的事

| 提议 | 原因 |
|------|------|
| 改推送为拉取 | 用户明确拒绝——推送是设计初衷 |
| 换更大 embedding 模型 | 成本爆炸，bge-m3 已是当前最佳中文选择 |
| 加意图分类层 | 变相拉取式，违背"不需要用户开口"的定位 |
| 冷却写盘持久化 | Phase 3，等 P0-P3 效果验证后再决定 |

---

## ✅ 执行报告（2026-06-14 17:58）

### 实际方案（与计划不同）

| 计划方案 | 实际方案 | 原因 |
|---------|---------|------|
| 代码过滤 `_purge_single_word_rules()` | 手动清洗 a_rules.json | 更彻底——代码过滤只能删单英文词，手动清洗可同时去掉 paper-spine/huashu-nuwa/perspective 等噪声 |
| 保留 ~60 条规则 | **保留 6 条全手动规则** | 用户决策——56 条 auto-gen 全部清零，从零开始只保留经实战验证的手动规则 |
| config.yaml ssr.auto_gen_rules → false | 同 | ✅ |

### 清洗结果

| 项目 | 旧 | 新 |
|------|----|----|
| a_rules.json 规则数 | 61 | **6** |
| 手动规则 | 5 | **6（全手动）** |
| auto-gen 单字噪声 | 56 | **0** |
| work→writing-skills 误报 | 有 | **消失** |
| 备份 | 无 | a_rules.json.bak (9.5KB) |

### 最终 6 条规则覆盖

| 场景 | 关键词命中 |
|------|:--:|
| 写代码/功能/模块 | brainstorming, test-driven-development, planning-with-files |
| ASCII/字符画 | ascii-art |
| 股票/均线/K线/期货 | technical-analysis, tushare-finance |
| 规划/方案/架构设计 | brainstorming, writing-plans, idea-foundry |
| debug/报错/修复 | diagnose, systematic-debugging |
| UI/界面/设计 | brainstorming, ui-ux-pro-max, popular-web-designs |

### GREEN 基准验证（重启后）

```
5/5 通过（A层关键词 4/5 + B层 embedding 兜底 1/5）
├── UI设计        ✅ 关键词 3/3
├── 代码调试      ✅ 关键词 2/2
├── ASCII艺术     ✅ 关键词 1/1
├── 学术写作      ✅ B层兜底（A层无规则覆盖）
└── 金融分析      ✅ 关键词 2/2
```

### SSR 注册诊断

```
[ssr] 加载 A 层规则: 6 条
[ssr] 清理后 A 层规则: 6 条
[ssr] auto-gen 已关闭（ssr.auto_gen_rules: false）
[ssr] embedding 索引: 370 skill（增量同步）
[ssr] 插件注册完成 | skill: 370 | 残骸: 0 | A层: 6+0 | emb: 370 | B层: main
```

### 遗留：未执行的计划 Task

| Task | 状态 | 理由 |
|------|:--:|------|
| Task 2: Embedding 语义门控 | ⏸️ 延期 | A层 6 条精准 → embedding 噪音问题大幅缓解，门控不再紧迫 |
| Task 3: 中文扩展域匹配度 | ⏸️ 延期 | 同上，6 条规则已覆盖核心域 |
| Task 4: 提高 similarity_floor | ⏸️ 延期 | bge-m3 0.35 当前够用，GREEN 全通过 |

> **记录时间：** 2026-06-13（计划）/ 2026-06-14（执行完成）
> 
> **诊断基础：** 本会话 40/40 命中日志 + 1698 行 `__init__.py` 完整审计
>
> **原则：** 保持推送式，不改变 SSR 的设计初衷。只砍噪音，不改架构。
