# SSR 总状态追踪

> 最后更新: 2026-09-16 | 项目: Smart Skill Router (智配路由) | 当前: v3.0.1（版本面已同步） | 审查: Hermes

---

## 零、设计原则（不可妥协）

| 原则 | 含义 | 反例 |
|------|------|------|
| **零硬编码** | 模型名、端点、阈值、prompt 全部从 config.yaml 读取。换模型不换代码。 | `model = "bge-m3"` ← 死 |
| **可发布** | 对外文件不泄露隐私、不写死个人配置。docstring/README 是给陌生用户看的。 | docstring 写 `Qwen3-Embedding-8B 4096维` |
| **通用** | 我的 deepseek-v4-pro + Qwen3-8B 能用，别人的 ollama + bge-m3 也能用。 | benchmark 硬依赖 API |
| **快速上手** | 新用户装完就能跑。`--quick` 零依赖验证。动态阈值免手动调参。 | "请先配置 5 个参数" |
| **高信号** | 该推的 skill 不漏。信号命中率是核心指标。 | 学术写作 1/2 |
| **低噪音** | 不该推的时候闭嘴。噪音静默率是核心指标。 | gate 放过闲聊 |
| **配置渠道** | 通用配置模板 + model_scores.json 社区贡献。新模型出来后加一行 JSON 即可。 | 每次换模型改 3 处代码 |

---

## 一、当前基线 — v2.1.0

| 组件 | 状态 |
|------|:--:|
| 架构 | 噪音→keyword+embedding→LLM统一决策，1次LLM |
| 噪音过滤 | 17条正则（配置驱动），0 token |
| A层规则 | 101条 v3 格式（keywords动态匹配，不再硬编码skill名）|
| Embedding | Qwen3-Embedding-8B（硅基流动 API），4096维，407 skill |
| LLM独立兜底 | 无候选时 LLM 全量匹配 |
| 死引用 | 归零（v3 天然无硬编码）|
| 门控模型 | qwen3.5:4b (think:false) / DeepSeek v4-pro (thinking:disabled) |
| Dashboard | 三卡配置(B层/门控/Embedding) + 三模式评分测试 |
| 动态阈值 | similarity_floor 根据 embedding 模型得分自动计算 |
| 元对话检测 | _META_CONVO 正则预检 + _TASK_VERBS 安全阀，零 token，已启用 |
| 自循环学习 | boost_skill() API + preferences.json（stub·未接线，已评估不实施，见十二）|

### 架构图（v2.2.0）

```
用户输入
  │
  ├─ 噪音过滤（17 条正则，0 token）
  │     │
  │     └─ 噪音？→ 静默跳过
  │
  ├─ 元对话检测（_META_CONVO 正则，0 token）
  │     │
  │     └─ 元对话？→ 跳过
  │
  ├─ LLM 意图门控（qwen3.5:4b / DeepSeek v4-pro，think=off）
  │     │
  │     └─ 非任务意图？→ 跳过
  │
  ├─ A 层：关键词 + Embedding 语义匹配（0 token）
  │     │
  │     ├─ keyword match（101 条 v3 规则，扫描 SKILL_INDEX，无硬编码）
  │     ├─ embedding cos-sim（Qwen3-Embedding-8B，4096 维，407 skill）
  │     └─ 动态阈值（无极校准公式，按模型得分自动计算 floor）
  │
  ├─ 候选 > 0 → LLM 筛选确认（1 次，~300 token）
  ├─ 候选 = 0 → B 层 LLM 全量匹配（1 次，~400 token）
  │
  └─ 格式化输出：[SSR] 建议加载: [D] skill1, ... | [P] skill2, ... | [B] skill3, ...
       │
       └─ 自循环: boost_skill() → preferences.json
```

**实测准确率：**（✅ v2.2.0 已修复：`similarity_floor` 已从 config.yaml 删除，动态阈值 0.25 生效。A 层在 benchmark 环境 79% 信号召回，生产环境需持续观察。）

| 模式 | 总评分 | 信号命中 | top-3 | 噪音 | 备注 |
|------|--------|---------|-------|------|------|
| total (llm_screen=off) | 47.1 | 25/28 (89%) | 16/28 (57%) | 20/20 (100%) | v2.1.1，50s |
| total 三档评分 | - | 23/28 (82%) | 精准40+相关3=43/46 (93%) | 20/20 (100%) | 新版 benchmark，56s |
| total (llm_screen=on) | 71.4 | 22/28 (79%) | 14/28 (50%) | 20/20 (100%) | 旧默认，180s |
| quick (纯A层) | N/A | 22/28 (79%) | 15/28 (54%) | 未测 | 零LLM，31s |
| bge-large-zh-v1.5 旧基线 | 70.6 | - | - | - | 历史数据 |

**分数真实性分析：** benchmark 54% top-3 低估真实水平。约 1/3 的"miss"实际推了相近 skill（文献综述→nature-figure，降重→paper-spine-rewrite），仅 benchmark 预期太窄。真实烂的只有调试类"函数返回None"（推荐完全不相关）。另有 2 条 benchmark 预期数据本身有误（"Python脚本CSV"预期 subagent-driven-development）。

### 门控修复 (2026-06-22)
- `_call_llm_intent`: ollama 走 `/api/generate` + `think: false`，非 ollama 加 `thinking: disabled`
- 英文 prompt 替代中文（"Does this user message need an AI skill? Answer only YES or NO."）
- `_intent_gate`: 改为 `active` provider 单一选择，不再遍历回退链

### Dashboard (2026-06-22)
- 三张配置卡：B层后端 / 门控模型 / Embedding 模型
- 全部自由输入，Provider 用 datalist 建议
- 评分测试：Run Benchmark 跑三模式全量（total + embedding + gate）
- 门控选 main 自动填主模型名

### Benchmark (2026-06-22)
- `tests/ssr_scoring_benchmark.py`: 50条·3模式·配置驱动·零硬编码
- total = 真实 SSR 管线 (_intent_gate → _match_a_layer → _llm_screen)
- embedding = 纯向量模型对比（换模型用）
- gate = 本地 Ollama 门控测试
- 分类明细 + 跳过未安装 skill

---

## 二、v2.1.0 架构

```
消息
 ↓
噪音过滤(17条配置驱动, 0 token)
 ↓ 未命中
元对话检测(7条正则, 0 token) ← 聊 SSR/CMG/skill 系统时直拦
 ↓ 未命中
intent_gate (LLM 二分类, ~300 token) ← prompt 配置化
 ↓ YES
keyword匹配(101条v3规则, 0 token) → 动态扫描SKILL_INDEX
    +
embedding匹配(Qwen3-Embedding-8B 4096维) → 余弦相似度
    ↓ floor 动态计算（模型得分→阈值映射）
    ↓ 合并去重
  ├── 有候选(>0) → LLM筛选确认(1次, ~300 token)
  └── 无候选(=0) → LLM独立匹配(1次, ~400 token)
    ↓
  推荐 或 静默
    ↓
  自循环: boost_skill() 记录到 preferences.json
```

---

## 三、v2.0.0 变更清单

| 变更 | 位置 |
|------|------|
| a_rules.json v3 格式 | skills硬编码 → keywords动态匹配 |
| _match_a_layer_keyword 重写 | 关键词扫描 SKILL_INDEX |
| _call_llm_screen_direct 新增 | 无候选时 LLM 独立匹配 |
| _pre_llm_call 流改造 | 有候选筛选 / 无候选兜底 |
| 关键词停用词过滤 | 18 个英文泛词清理 |
| regex 修复 | REST API 规则改 lookahead |

### 仍存在的硬伤
| 问题 | 影响 |
|------|------|
| ~~A 层规则硬编码 skill 名~~ | ✅ v2.0.0 已解决（keywords 动态匹配）|
| Embedding 在发布时固化 | 用户安装后向量不变，新增 skill 永远匹配不到 |
| 3 类目无对应 skill（合同/仲裁/失眠） | 永远推不到，需告知用户 |
| ~~a_rules.json 含死引用~~ | ✅ v2.0.0 已解决（v3 格式无硬编码）|

---

## 四、v2.0.0 计划 — 解耦关键词 ✅ 已执行

> 核心：A 层规则从「硬编码 skill 名」改为「关键词 → 运行时匹配」

### 目标
```
旧: regex → ["ui-ux-pro-max", "brainstorming"]      ← 死引用
新: regex → {keywords: ["ui","design","frontend"], phases: ["BUILD"]}
              ↓
     运行时扫描 SKILL_INDEX，匹配 name/description 含关键词的 skill
              ↓
     boost embedding 排序 → LLM 最终决策
```

### 优势
- 用户 skill 集不同也能用同一套规则
- 新增 skill 无需修改规则
- 死引用自动消亡

### 风险 & 缓解
| 风险 | 缓解 |
|------|------|
| 关键词粗筛不精准 | LLM 是最终决策者，会踢掉不相关的 |
| 关键词太泛匹配太多 | 限制 boost 数量（≤8）+ phases 过滤 |
| 规则迁移工作量大 | 编写转换脚本，一键迁移 108 条 |

### 三层漏斗（改后）
```
keyword(高召回, 0 token) → 拉回 embedding 漏网
    +
embedding(高精准, 0 token) → 相似度排序
    ↓ 合并去重
  LLM(语境理解, 1次) → 判断+匹配
    ↓
  最终推荐
```

### 任务清单
- [x] 设计 a_rules.json v3 格式：keywords + phases + not（负向）
- [x] 迁移脚本：v2(硬编码) → v3(关键词)
- [x] 修改 `_match_a_layer_keyword`：读 keywords 字段动态匹配
- [x] 修改 `_pre_llm_call`：接入 keyword 匹配（嵌入在 embedding 之前）
- [x] 57 条极限重测（补多分类场景）
- [x] 三维评分系统落地 — `tests/ssr_scoring_benchmark.py`（50条·3模式·配置驱动·零硬编码）
- [x] Dashboard 三卡配置（B层/门控/Embedding）
- [x] 门控 think:false + 英文 prompt 修复
- [x] 发布前死引用扫描 + 隐私扫描

---

## 五、v2.1 — Gate 通用化 + 元对话检测 + 自循环 ✅ 已执行

> 2026-06-23 发布 | [详细 plan](./v2.1-self-loop/task_plan.md)

| 方向 | 说明 | 状态 |
|------|------|:--:|
| **gate prompt 配置化** | `_call_llm_intent` 从 `intent_gate.prompt` 读 prompt，空则用默认英文 | ✅ |
| **元对话检测** | `_intent_gate` 内 `meta_detection` 层，7 条正则零 token 预检 | ✅ |
| **自循环学习** | `boost_skill()` API + `preferences.json` + `_SESSION_RECOMMENDED` 追踪 | ✅ stub |
| **config.yaml** | `intent_gate.prompt` + `meta_detection` 段已写入 | ✅ |
| **版本号** | 11 文件全量 v2.0.0 → v2.1.0 | ✅ |

### 实现细节
- gate prompt: `_call_llm_intent(..., gate_prompt)` 参数，空 → `"Does this user message need an AI skill? Answer only YES or NO."`
- 元对话: `meta_detection.enabled: false` 默认关，7 条正则含 SSR/CMG/skill 系统自指。任务动词安全阀复用噪音过滤的 `_TASK_VERBS`
- 自循环: `_format_recommendation` 产出时记录到 `_SESSION_RECOMMENDED`，`boost_skill(name)` 公开 API 可外部调用

### 已淘汰
| 方向 | 原因 |
|------|------|
| ~~嵌入富化（LLM 生成描述）~~ | 实测 85%→55%，反效果 |
| ~~skill 自声明~~ | 需改外部 skill，不可控 |
| ~~embedding 安装时重建~~ | 当前嵌入 85% 信号召回，够用 |
| ~~多 embedding 后端~~ | 后续切 Qwen3-Embedding-8B（API），Ollama bge 作为本地备选 |
| ~~bge-m3~~ | 切换 Qwen3-Embedding-8B（4096维，区分度更高）|

### v2.1 补丁 — 动态阈值 + Embedding 升级 + 审计修复 (2026-06-23)

| 变更 | 说明 | 状态 |
|------|------|:--:|
| **动态 similarity_floor** | `_similarity_floor()` 自动读 embedding 模型名 → model_scores.json → 得分映射 floor（5→0.25, 4→0.30, 3→0.35, 2→0.42, 1→0.48）。显式配置优先。 | ✅ |
| **Embedding 升级** | bge-large-zh-v1.5 → Qwen3-Embedding-8B（硅基流动 API），1024→4096维，model_scores.json 得分 5 | ✅ |
| **全量审计** | 7 项修复：README badge、日期统一、docstring 去模型名/维度、config 示例更新、注释路径修正、36 个 bak 清理、a_rules_v3.json 移除 | ✅ |
| **test_ssr.py 修复** | v2→v3 格式适配：skills→keywords、1024 维硬编码→动态检测、旧模型名→配置驱动、GREEN 测试适配 v3 keywords | ✅ |
| **对外发布规范** | __init__.py docstring 零模型名零维度（A 层 Embedding + B 层 LLM，不写 Qwen3/bge/1024/4096） | ✅ |
| **动态阈值 v1（有极）** | 5 档查表映射。局限：手工打分、离散、新模型需手动加条目。 | ✅ |
| **benchmark 三档评分** | 四元组格式 (精准/相关/不相关)。93% 相关度，更贴近真实用户体验。旧 57% top-3 低估了。 | ✅ |
| **llm_screen 开关** | `_pre_llm_call` 内根据 `ssr.llm_screen` 配置跳过 LLM 重排序，默认 false。benchmark 同步跟随配置。top-3 50%→54%，速度 180s→32s。 | ✅ |

### 已知技术债

| 事项 | 说明 | 优先级 |
|------|------|:--:|
| **🔴 explicit floor 锁死 A 层** | config.yaml 第 668 行 `similarity_floor: 0.35` 未删，动态阈值不生效。**导致生产环境 A 层 0% 命中率**（keyword+embedding 完全不产出，全部落到 B 层 LLM）。benchmark 测试环境无此干扰所以数据干净。删除后 Qwen3-8B 自动到 0.25。 | 🔴 P0 |
| **display=false — 成果全浪费** | 93% 相关度的推荐生成了但不展示。用户视角 SSR "不存在"。 | 🟡 |
| **U 盘 v0.6.3 古董版** | 三个阻断：a_rules 格式不兼容 + embeddings 空 + config 指向 Ollama localhost。Phase 2 需从本机 v2.x 全量迁移。 | 🟡 |
| **版本号不一致** | Skill v2.2.0 / 代码 v2.1.0 / plan v2.1.0。三处不同步。 | 🟡 |
| **5 个 bak 残留** | 上次审计清 36 个后仍有 5 个（238 KB）。 | 🟢 |
| **A 层规则缺口** | 3 条 embedding 天花板：Docker部署/正则匹配/解释代码。不是 A 层规则能修的。 | 🟢 |
| **benchmark 过时** | 50 条基准 bge-large-zh-v1.5 时代数据，预期分数需重新标定。2 条预期 skill 明显错误。 | 🟡 |
| **B 层兜底未测** | `_call_llm_screen_direct` 独立准确性未知。 | 🟡 |

---

## 六、之前讨论但未落地的事项

| 事项 | 来源 | 状态 |
|------|------|:--:|
| B 层独立匹配兜底 | 6/22 讨论 | ✅ v2.0.0 已落地 `_call_llm_screen_direct` |
| 意图门控独立 LLM 调用 | 6/22 讨论 | 弃用——embedding 已是零成本门控 |
|| 模型评分系统 | scoring-system 分支 | ✅ 已落地 `tests/ssr_scoring_benchmark.py` (50条·3模式) |
| 多 embedding 后端 | multi-embedding 分支 | 停研，Ollama bge 够用 |
| 精度升级 | precision-upgrade 分支 | 部分落地（本次 A 层补规则） |
| 噪音降噪 | noise-reduction 分支 | 已落地（9 条白名单） |

---

## 八、v2.2 路线图 — 修负优化 + 补缺口

| # | 方向 | 预期效果 | 状态 |
|---|------|---------|:--:|
| 1 | llm_screen 开关 | top-3 50%→54%，速度 180s→32s | ✅ |
| 2 | A 层补调试规则 + benchmark 修正 | 调试 1/3→3/3，信号命中 22→25，top-3 15→16 | ✅ |
| 3 | 删显式 floor | 动态阈值生效 | ✅ 配置已同步（2026-07-03，`similarity_floor` 行已从 config.yaml 删除）|
| 4 | 无极阈值 | 校准脚本 `tests/calibrate_floor.py` + 公式优先查表 | ✅ |
| 5 | 全管道 benchmark | 评估后取消——hook 内部 cooling/display/confidence 不适合 mock | ❌ |

**v2.2 目标：** 代码侧全部达成。配置侧已同步（2026-07-03）。技术债 8 条（1🔴P0 + 4🟡 + 3🟢）。

### v2.2.0 实施记录（2026-07-03）

| # | 事项 | 变更 | 验收 |
|---|------|------|------|
| 1 | llm_screen 开关 | 代码已含，config 默认 off | top-3 50%→54%，速度 180s→32s ✅ |
| 2 | A 层补调试规则 + benchmark | a_rules.json +3 条调试规则，benchmark 修正 | 信号命中 22→25，top-3 15→16 ✅ |
| 3 | 删显式 floor | config.yaml 删除 `similarity_floor: 0.35` | `grep similarity_floor config.yaml` → 0 ✅ |
| 4 | 无极阈值 | calibrate_floor.py + calibrated_floor 0.58 (model_scores.json) | ✅ 噪声 P95=0.60 → 0.58 砍 95% 噪声。0.25 等于无 floor |
| 5 | 全管道 benchmark | 取消（hook 内部不适合 mock） | N/A ❌ |
| 6 | A 层可观测 | `_match_a_layer()` 加 info 日志（kw/emb 计数 + top-5） | ✅ 重启后 grep "A 层命中" 验证 |

**v2.2.0 结论：** 5/6 完成。代码侧全部达成 + 可观测，配置侧已同步。calibrated_floor 0.58 待重启后 benchmark 验证噪声静默率。

---

## 当前待办（2026-07-02 交叉审查后）

> 按优先级排序。每步可独立执行、可 grep 验证。

| # | 做什么 | 验收 |
|---|------|------|
| 🔴 1 | **删 explicit floor** — config.yaml 删除 `similarity_floor: 0.35` 行 | ✅ 已删，动态阈值 0.25 生效 |
| 🔴 2 | **U 盘 SSR 迁移** — 本机 v2.2.0 → U 盘（替 v0.6.3），含 __init__.py、a_rules.json、embeddings.json | ⏳ Phase 2 |
| 🟡 3 | **开 display** — config.yaml `ssr.display: false` → `true` | ✅ `display: true` 已设 |
| 🟡 4 | **版本号同步** — __init__.py v2.1.0 → v2.2.0（与 Skill 对齐） | ✅ 本步执行中 |
| 🟢 5 | **删 bak 文件** — plugins/ssr/ 下 5 个 .bak 残留 | ✅ 已清 |

---

## 十、v2.3 路线图 — 覆盖率冲刺（2026-07-22）

> 触发: 用户问「不确定就不推，只要推就一定有用？」→ 诊断发现 A 层仅 12 条规则，覆盖率 12%。B 层 embedding 有噪声（nature-citation+storage-analyzer 绑定）。策略正确（保守优先）但覆盖率是硬伤。

### 当前基线（2026-07-22 实测）

| 指标 | 值 |
|------|-----|
| A 层规则数 | 12 条（a_rules.json 实际文件），覆盖 25/200+ skill |
| B 层 embedding | Qwen3-Embedding-8B（硅基流动），benchmark 55% |
| B 层近期命中 | 28 次，0 失败超时 |
| confidence_threshold | 0.62 |
| auto_gen_rules | false（用户曾关闭） |
| display | true |
| 元对话检测 | 正常（本次会话触发静默） |
| 已知噪声 | nature-citation + storage-analyzer embedding 盲绑定（出现 3 次） |

### P0 — auto_gen_rules 开启（立即）

**做什么：** `hermes config set ssr.auto_gen_rules true`

**预期效果：** A 层从 12 条→自动覆盖全量 skill description。规则 source 标记 auto-gen，与 manual 规则隔离。

**验证：**
```bash
grep 'auto-gen' ~/.hermes/logs/agent.log | tail -5  # 确认规则生成
python3 -c "import json; d=json.load(open('~/.hermes/plugins/ssr/a_rules.json')); print(len(d))"  # 规则数变化
```

**回滚：** `hermes config set ssr.auto_gen_rules false` + 重启，auto-gen 规则不持久化。

**风险：** auto-gen 规则质量参差不齐。观察一轮噪声率再决定保留。

### P1 — 换 bge-m3 embedding（P0 之后）

**做什么：** 修改 config.yaml embedding 段，切到 bge-m3。

**为什么：** bge-m3 对中文领域术语盲区更小，benchmark 数据更好。Qwen3-Embedding-8B 55%→bge-m3 预期 70%+。

**前置验证：** 确认硅基流动有 bge-m3 端点。

**风险：** 需重建 embeddings.json（38.7MB），API 调用一次。

### P2 — 收紧 confidence_threshold（P0+P1 之后）

**做什么：** 0.62→0.65/0.68

**为什么：** P0+P1 提升 A/B 层质量后，收紧阈值才有意义——之前收紧只会漏更多。

### P3 — A 层规则维护（持续）

- 解绑 nature-citation + storage-analyzer 噪声对
- 补盲区：从实际使用中发现未覆盖的领域
- review auto-gen 规则质量

### P4 — 架构升级（长期，不急）

- reranker 二次排序
- 用户反馈闭环
- multi-embedding ensemble

### 执行顺序

```
备份 → P0(auto_gen) → 观察噪声 → 
  ├─ 可接受 → P1(bge-m3) → P2(阈值) → P3(维护)
  └─ 噪声过高 → 关 auto_gen → 手写 A 层规则 → P1
```

---

## 十一、发布清单（每次发布前）

- [ ] `grep -rn 'sk-' a_rules.json` 零隐私泄漏
- [ ] `grep -rn 'v[0-9]\.[0-9]\.[0-9]' __init__.py plugin.yaml` 版本号一致
- [ ] 死引用扫描：遍历 a_rules.json keywords[]，确认无残留 v2 skills 字段
- [ ] 极限测试 ≥ 80% 准确率
- [ ] CHANGELOG 更新
- [ ] 备份旧版

---

## 十二、已评估 · 不实施（防重复提案）

| 事项 | 评估日期 | 结论 |
|------|:--:|------|
| 采纳环接线（boost_skill 实装调用 + preferences 回读排序） | 2026-09-15 | ❌ 不实施。①推荐质量主杠杆在 A 层规则覆盖（调试 1/3、学术 1/2、法律/医学等 6+ 域零覆盖），排序微调改不了漏推；②个人任务量下采纳信号样本太小，噪声大于信号；③二次干预有负优化先例（LLM 二次筛选 top-3 61%→50%）。观察「推荐有没有被用」用零成本替代（AI 汇报 + agent.log 命中统计）。stub 保持现状。 |

---

## 十三、版本面同步记录（2026-09-16）

| 项 | 处理 |
|---|---|
| plugin.yaml | 2.3.0 → 3.0.1（描述同步：MoE 域路由、去旧计数） |
| __init__.py | docstring → v3.0.1 + 版本历史补 v3.0.1 行 |
| CHANGELOG.md | 补记 v2.4.0–v3.0.1 四条（来源=代码内注释与归档计划，见补记说明） |
| README.md | badge → 3.0.1 + 版本历史表补五行 |
| dashboard.py / test_ssr.py | 版本字符串 → 3.0.1 |
| you-hong 副本 | 同批同步（文件级一致） |
| GitHub | 已发布 v3.0.1（2026-09-16；见 §十四） |
| 备份 | 全部同步文件均有 .bak 备份（0916093x 系列） |


---

## 十四、GitHub 发布记录（2026-09-16）

- 仓库: `L1veSong/Smart-Skill-Router-Plugin` · tag `v3.0.1` · commit `975fa8a`（远端 main 已一致）
- 范围: 13 文件（+7456 / −2572）——插件 v3.0.1 全套 + 回归测试套件（4 个）+ dashboard 更新 + SKILL.md 重写
- Release: https://github.com/L1veSong/Smart-Skill-Router-Plugin/releases/tag/v3.0.1 · 资产 `Smart-Skill-Router-Plugin-v3.0.1.zip`（123KB，33 文件）
- 排除项: `embeddings.json`（生成物）/ `a_rules.local.json`（个人覆盖）/ `SSR_FIX_LOG.md` / `.bak`
- 隐私终扫: 零命中（路径 / 姓名 / 公司 / 凭证）
