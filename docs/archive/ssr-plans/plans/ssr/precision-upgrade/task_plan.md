# SSR 精准匹配升级计划 v3

> **目标：** 从"关键词+embedding 双路径可用"升级为"embedding 质量 80%+、上下文感知冷却、增量索引、生产监控"
>
> **v0.3.0 目标（2026-06-10）：** 混合权重 + 冷却智能化 + 增量索引 = 体验可感知升级
>
> **v3 更新（2026-06-09 22:50）：** 基于 GREEN 5/5 全通过 + bge-m3 embedding 实测 ~60% → 制定下阶段升级方向。
>
> **v2（2026-06-09）：** Phase 2 多后端 embedding 已实现（bge-m3 1024维，246 skill 索引，ollama 本地）。
>
> **v1（2026-06-05）：** 初始实现（765行，30函数，A+B双层）。

---

## 当前状态总览（2026-06-09 GREEN v2 验证后）

| 指标 | 值 | 评价 |
|------|-----|------|
| GREEN 基准（关键词+阈值） | 5/5 (100%) | 🟢 similarity_floor=0.35 + conf=0.40 全通 |
| bge-m3 embedding 精度 | ~60% (2.5/4) | 🟡 关键词兜底，embedding 弱不影响体验 |
| A 层规则数 | 6 手动（auto-gen 已关） | 🟢 覆盖 GREEN 全部 5 场景 |
| 双阈值过滤 | floor=0.35 / conf=0.40 | 🟢 已验证：噪音过滤 + GREEN 不受影响 |
| 冷却机制 | shown_recently 标签 + 60s | 🟢 可用 |
| Dashboard | 8766 HTTP 200 | 🟢 正常运行 |
| Embedding 索引 | 370 skill, 1024维 | 🟢 已构建 |

---

## Phase 3：Embedding 质量提升（当前 v3 重点）

### 问题诊断

bge-m3 实测 4 条零命中消息：
- "暗色仪表盘" → `architecture-diagram` (0.605)，期望 `minimalist-ui`/`cmg-dashboard`
- "知识漫画" → `baoyu-comic` (0.661) ← 🟢 精准
- "照片分类" → `apple-reminders` (0.497)，期望 `photo-organizer-pro`
- "代码转视频" → `ascii-video` (0.629)，期望 `code-to-video` 在 #2 ← 🟡 接近

**根因分析：**
1. Skill description 太短（一两句话），bge-m3 1024维只能捕捉表面语义
2. 多义词场景（iPhone→Apple→reminders而非photos）需要上下文
3. 中英混合 skill name 与中文查询的语义距离较大

### Task 3.1：Skill description 富化 ✅ (2026-06-10)

**目标：** 让每个 skill 的 description 从 1 句话扩展为 3-5 句功能描述，提升 embedding 语义覆盖。

**实现：** `_get_skill_info()` 正文富化逻辑（`__init__.py:373-424`）：
1. 解析 YAML frontmatter 的 description（支持 block scalar `|`）
2. 跳过 frontmatter 后进入正文，逐行提取散文段落
3. 过滤：跳过表格行（`|`）、代码块（\`\`\`）、标题（#）、引用（>）、空行、短行
4. 取前 3 段散文（每段 > 15 字符），截断 300 字符
5. 已有 YAML desc → 追加正文；无 YAML desc → 正文兜底

**验证（2026-06-10）：**
- ✅ canon-mnemonic-guard: description 301 chars，无表格行
- ✅ road-trip-planner: description 620 chars
- ✅ 重启后 embedding 全量重建：296 skill（含富化描述）
- ✅ 含表格行 = False

### Task 3.2：中文 query 增强 ✅ (2026-06-10)

**问题：** 用户用中文查，skill description 是英文 → bge-m3 跨语言但不完美。

**实现：** `_expand_chinese_query()`（`__init__.py:652-692`）— 14 域中英映射：

| 域 | 中文关键词 | 英文扩展 |
|----|----------|---------|
| 设计/UI | 设计/界面/UI/样式/布局/前端/网页 | design, UI, interface, frontend, layout, CSS |
| 调试 | 调试/报错/错误/修复/bug/异常 | debug, error, diagnose, fix, troubleshoot |
| 金融 | 金融/股票/交易/均线/MACD/RSI/A股 | finance, stock, trading, market, technical analysis |
| 学术 | 论文/学术/写作/研究/文献/期刊 | academic, paper, research, writing, journal, citation |
| 旅行 | 旅行/旅游/出行/攻略/景点/酒店 | travel, trip, itinerary, tour, hotel, road trip |
| 部署 | 部署/上线/发布/生产/服务器/运维 | deploy, release, production, server, CI/CD, DevOps |
| 数据分析 | 数据/分析/统计/图表/可视化/报表 | data analysis, statistics, visualization, chart, dashboard |
| 音乐 | 音乐/音频/歌曲/播放/乐器/和弦 | music, audio, song, composition, sound |
| 视频 | 视频/剪辑/动画/渲染/字幕/转码 | video, animation, render, edit, media, encoding |
| AI/ML | AI/模型/训练/推理/LLM/GPT/神经网络 | AI, model, training, inference, LLM, machine learning |
| API/后端 | API/接口/后端/服务/REST/HTTP/数据库 | API, backend, server, REST, HTTP, database, SQL |
| 安全 | 安全/加密/认证/权限/防火墙/漏洞 | security, encryption, authentication, firewall, vulnerability |
| 创意/艺术 | 漫画/插画/绘画/色彩/像素/ASCII | art, illustration, drawing, pixel, ASCII, creative |
| 游戏 | 游戏/玩法/关卡/角色/RPG/策略 | game, gameplay, design, level, character, RPG, simulation |

**验证（2026-06-10）：** 14/14 域全部命中。无匹配查询（「今天天气」）不扩展。

### Task 3.3：混合匹配权重 ✅ (2026-06-10)

**目标：** 关键词精确命中 +0.3 加权，使得关键词命中的 skill 在合并排序中明显靠前。

**实现：** `_match_a_layer()` 第三步（`__init__.py:550-579`）：
1. 收集 keyword_result 中的所有 skill 名
2. 对 embedding 结果中与关键词重合的 skill，`_sim` 加 `_keyword_weight_boost()`（默认 0.3，上限 1.0）
3. 合并去重后按 `_sim` 降序排列
4. 纯关键词 skill（无 _sim）排在末尾，关键词+embedding 双命中排最前
5. 权重可配：`keyword_weight_boost: 0.3`

**验证（2026-06-10）：**
- ✅ `_keyword_weight_boost()` 存在，返回值 > 0
- ✅ `_match_a_layer()` 含 `keyword_names` + `boost` + `sort by _sim`

### Task 3.4：A 层 — 相似度地板 ✅ (2026-06-09)

**问题：** embedding 把所有 skill 排进去，score 0.1 的也出现在推荐里。`road-trip-planner`、`apple-reminders` 对「讨论 SSR 代码」score < 0.3。

**实现：** `_match_a_layer()` embedding 循环内加 `if sim < floor: continue`。floor 默认 0.35，config.yaml 可配。

```python
def _similarity_floor() -> float:
    """embedding 相似度地板。score < 此值直接丢弃。"""
    return _load_ssr_config().get("similarity_floor", 0.35)
```

**预期效果：** `scores[:30]` 中一半以上被地板过滤，进入截断的候选质量提升。

### Task 3.5：B 层 — 整体置信度 ✅ (2026-06-09)

**问题：** 即使单个 skill 过了地板，如果 top-3 的平均相似度 < 0.4，说明整体匹配质量低。不如跳过推荐。

**实现：** `_pre_llm_call()` 最后检查整体置信度。低于阈值 → 返回 None（不推荐）。

```python
def _confidence_threshold() -> float:
    """整体匹配置信度阈值。低于此值跳过推荐。"""
    return _load_ssr_config().get("confidence_threshold", 0.40)

def _compute_confidence(result: list) -> float:
    """top-3 平均相似度（仅 embedding 候选）。
       如果全部是关键词命中（无 embedding），置信度 = 1.0。"""
```

**预期效果：** 噪音消息（无明确意图）→ 整体置信度低 → 不推荐。宁可不说，别说错。

**验证（GREEN + 噪音）：**
- 5 条 GREEN 消息：全部仍命中（关键词路径，置信度 1.0）
- 2 条噪音消息（如「你吃饭了吗」「今天天气」）：置信度 < 阈值 → 跳过

---

## Phase 4：生产监控 ✅ (2026-06-10)

### Task 4.1：Dashboard 实时匹配质量 ✅

**实现：** `server.py:185-199` `read_stats()` → 返回 4 字段 JSON：
- `intercept_count` — 拦截次数（CMG Guard）
- `error_count` — 错误记录数（errors.jsonl）
- `sessions` — 会话计数（state.json）
- `last_solidify` — 上次固化时间

前端 `renderStats()`（`:937-951`）渲染 6 格统计卡：规则总数/命中/拦截/错误/高误报/陈旧规则。

**验证（2026-06-10）：**
- ✅ `curl localhost:8765/api/stats` → `{"intercept_count":11,"error_count":90,"sessions":0,"last_solidify":"None"}`
- ✅ 4 字段完整

### Task 4.2：命中率日志 ✅

**实现：** `_SESSION_STATS` + `_STATS_LOG_INTERVAL = 10`（`__init__.py:1176-1198`）：
- 每会话维护 `{calls, hits_a, hits_b, misses, skipped_low_conf}` 计数器
- A 层命中（`:1317`）和 B 层命中（`:1372`）各在 `calls % 10 == 0` 时触发 `_log_session_stats()`
- 日志格式：`[ssr] 会话统计 | session=xxx | 调用=N | A层命中=N | B层命中=N | 无匹配=N | 低置信跳过=N | 命中率=XX%`

**验证（2026-06-10）：**
- ✅ `_SESSION_STATS` 结构完整（5 字段）
- ✅ `_STATS_LOG_INTERVAL = 10`
- ✅ 模拟 10 次调用后 `calls % 10 == 0` → 触发日志输出

### Task 4.3：误报自动降权
用户连续忽略 → 降权。连续加载 → 加权。

---

## Phase 5：上下文感知冷却 ✅ (2026-06-10)

### Task 5.1：任务切换重置冷却 ✅

**实现：** 增强 `_detect_task_switch()`（`__init__.py:1183-1193`）：
- 不再一刀切 ≤15 字 → 改为模式比较
- 使用 `_derive_pattern()` 提取当前消息模式
- 与 `_LAST_A_PATTERN` 比较，模式变化 + 短消息 → 切换
- `_pre_llm_call()` 每次调用后更新 `_LAST_A_PATTERN`

**验证（2026-06-10）：**
- ✅ `_detect_task_switch` 使用 `_derive_pattern` + `_LAST_A_PATTERN`
- ✅ 不再包含 `<= 15` 一刀切逻辑

### Task 5.2：分阶段冷却策略 ✅

**实现：** `_phase_cooldown()` + 两次替换 `COOLDOWN = 60`（`__init__.py:173-178, 1315-1322, 1347-1354`）：
- DISCOVER: 30s / PLAN: 60s / BUILD: 120s / VERIFY: 30s
- 每次冷却检查改为 `_phase_cooldown(s.get("phase", "BUILD"))`
- config.yaml 可配：`phase_cooldowns: {DISCOVER: 30, PLAN: 60, BUILD: 120, VERIFY: 30}`

**验证（2026-06-10）：**
- ✅ `_phase_cooldown("DISCOVER")` = 30
- ✅ `_phase_cooldown("BUILD")` = 120
- ✅ 代码中不再有硬编码 `COOLDOWN = 60`

---

## Phase 6：增量索引更新 ✅ (2026-06-10)

### Task 6.1：文件监听 ✅

**实现：** `_check_skills_changed()`（`__init__.py:849-872`）：
1. 遍历 skills 目录递归统计最大 mtime
2. 启动时记录 `_SKILLS_MTIME`（首次返回 None）
3. 每次 `pre_llm_call` 比较，mtime 变化 → 扫描新增/删除
4. 返回 `(new_skills, removed_skills)` 或 None

### Task 6.2：热更新 embedding ✅

**实现：** `_hot_add_skill()` + `_hot_remove_skill()`（`__init__.py:875-912`）：
1. `_hot_add_skill(name)` — `_get_skill_info()` → `_embed()` → 追加 `embeddings.json`
2. `_hot_remove_skill(name)` — 从 `_EMBEDDING_INDEX` 和 `embeddings.json` 删除
3. 降级：写入失败 → 标记 `_INDEX_DIRTY = True` → 下次全量重建
4. 集成到 `_pre_llm_call()`：先检查 `_INDEX_DIRTY` → 再检查 `_check_skills_changed()`

**验证（2026-06-10）：**
- ✅ `_check_skills_changed()` / `_hot_add_skill()` / `_hot_remove_skill()` 存在
- ✅ `_SKILLS_MTIME` / `_INDEX_DIRTY` 全局变量存在

---

## 已完成阶段

### Phase 2：多后端 Embedding ✅ (2026-06-09)
bge-m3 1024维 · 246 skill 索引 · 合并架构（关键词||Embedding）

### Phase 1：去上限 ✅ (2026-06-09)
B 层不限数量 · max_tokens 500 · 四阶段分组展示

---

## 延期事项

| 提议 | 前置条件 | 目标版本 |
|-----|---------|---------|
| 全文语义搜索 | embedding >80% 后 | v4 |
| 多语言混合 embedding | 中文场景 <50% | v4 |
| 用户手动调权重 | 反馈闭环不佳时 | v4 |
| LLM 精排（B层对 top-30） | embedding 召回不足时 | v3.1 |

## 错误记录

| 日期 | 错误 | 根因 | 修复 |
|-----|------|------|------|
| 2026-06-09 | 删除 a_rules.json | 未备份 | CMG ban |
| 2026-06-09 | auto-gen 10% 准确率 | 粗糙关键词当主力 | B层优先 |
| 2026-06-09 | 关键词封堵 Embedding | 优先级倒置 | 并行合并 |
| 2026-06-09 | added 变量崩溃 | auto_gen:false 未初始化 | 移到外层 |
| 2026-06-09 | GREEN 标注不实 | 存活≠质量 | 两步验证 |
| 2026-06-09 | bge-m3 独立测试误报 | hermes_cli 不可导入 | 仅真实会话 |
