---
name: ssr-operations
description: SSR 插件运维 — 存活验证、重启验证、空skills规则诊断、B层诊断、日志排查、基准测试、Dashboard。v2.4.0，gate日志INFO级别。llm_screen安全网+静默反馈。
version: 2.3.5
author: L1veSong
license: MIT
platforms: [macos, linux]
---
# SSR 运维操作 v2.3.3

### 自动学习垃圾规则泛滥（2026-07-22 · 同日两次复现）✅ 代码已修复

> **修复状态：已实施（2026-07-22）** — `_auto_gen_a_rules()` 重写为两遍扫描 + 频率过滤，line 881-925。修复后 auto_gen 产出的所有规则均带 `skills` 字段，`MAX_SKILLS_PER_KW=5` 过滤泛词。
>
> 完整分析 + 修复代码 + 验证步骤：→ `references/auto-gen-vs-promote-threshold.md`
>
> 命中率近似度量（推荐→加载转化率）：→ `references/hit-rate-measurement.md`
>
> A 层日志搜索坑点（grep 关键词错误导致假阴性）：→ `references/verification-pitfalls.md` 坑点 4

> auto_gen 重启触发，从 skill description 提取单英文词生成空 skills 规则 → a_rules.json 膨胀到 7267 条 (642KB)。PROMOTE_THRESHOLD = 999999 只阻断运行时 promote 路径，不阻断 auto_gen 启动路径。
>
> `~/.agents/skills/` 嵌入索引缺口 + B 层幻觉风险：→ `references/agents-skills-embedding-gap.md`

> 完整架构分析 + 代码 Bug 定位 + 修复方案：→ `references/auto-gen-vs-promote-threshold.md`

**代码 Bug 定位（`__init__.py` 第 907-910 行）：**

```python
# ❌ 当前代码 — 缺 skills 字段
for kw in keywords:
    pattern = _re.escape(kw)
    rules[pattern] = {
        "keywords": [kw],
        "source": "auto-gen",
    }

# ✅ 设计意图（见 references/auto-gen-architecture.md）— 应包含 skills
for kw in keywords:
    pattern = _re.escape(kw)
    rules[pattern] = {
        "keywords": [kw],
        "skills": [name],        # ← 缺失！导致 7264 条规则全废
        "source": "auto-gen",
    }
```

**文档 vs 代码不一致：** `references/auto-gen-architecture.md` 第 56 行写的是 `{"skills": [name], "source": "auto-gen"}`，实际 L907 写的是 `{"keywords": [kw], "source": "auto-gen"}`。设计文档和代码分叉了。

**正确停用方法（两处都要改）**：**
1. `PROMOTE_THRESHOLD = 999999`（运行时升级阻断 — 已做）
2. 还需定位 auto_gen 启动触发路径并加同样门禁（待做）

**重启后必做验证（防再次洪水）：**
```bash
python3 -c "
import json
with open('a_rules.json') as f:
    rules = json.load(f)
empty = sum(1 for v in rules.values() if not v.get('skills'))
print(f'总规则: {len(rules)}, 空 skills: {empty}')
assert empty == 0, f'垃圾规则洪水: {empty} 条空 skills!'
assert len(rules) < 100, f'规则异常增长: {len(rules)} 条!'
print('OK')
"
```

> 完整事件记录见 `references/auto-gen-7267-flood-20260722.md`

**清理 + 手工规则：** 清空 a_rules.json，写 12 条手工规则，每条 `skills` 字段指向实际存在的 skill 名（如 `["storage-analyzer"]`），`source: "manual"`。模板：
```json
{
  "清理.*磁盘|存储.*分析|磁盘.*满": {
    "keywords": ["storage", "disk", "清理"],
    "skills": ["storage-analyzer"],
    "source": "manual"
  }
}
```

**验证：** 重启 Hermes → 说"帮我看看存储" → 应出现 `[SSR] [D] storage-analyzer`。不出现则 grep agent.log 查 A 层命中。

---

### auto_gen_rules 触发条件（2026-07-22 实战）

**症状：** `hermes config set ssr.auto_gen_rules true` 后发"你好"，auto-gen 不执行。日志无 auto-gen 条目。

**根因：** auto_gen 代码在 `_pre_llm_call()` 深层，位于意图门控（intent_gate）**之后**。"你好"类纯问候被门控拦截，提前 return，永远走不到 auto_gen。

**正确做法：** 改 auto_gen 后必须发一条带实际任务的消息（如"帮我查天气"），门控才会放行到 auto_gen 代码路径。

**验证：** `grep 'auto.gen.*生成\|auto-gen.*启用' agent.log` — 有输出才行。没输出说明从未触发。

### A 层实际覆盖率 vs master-status 声称（2026-07-22）

**坑点：** master-status.md 声称「101 条 v3 格式」，实际 `a_rules.json` 只有 12 条。在 F10（6条→手工清洗）后陆续加了 6 条但从未更新 master-status。

**教训：** 查 A 层规则数必须读文件实测，不信 plan 文档：
```bash
python3 -c "import json; d=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(len(d))"
```

### Embedding 噪声：nature-citation + storage-analyzer 盲绑定（2026-07-22）

**症状：** 7月3日日志同一组合出现3次。Qwen3-Embedding-8B 把两个零语义相关的 skill 算出了高余弦相似度。

**影响：** B 层 false positive。`confidence_threshold: 0.62` 过滤了大部分但无法根除。

**缓解：** P1 切 bge-m3（中文盲区更小）。详见 `~/.hermes/plans/ssr/master-status.md` 第十章 v2.3 路线图。

### v2.3 升级路线（2026-07-22）

优先级递减：
- **P0**: `auto_gen_rules: true`（12→200+条A层规则，需任务消息触发）
- **P1**: 换 bge-m3 embedding（55%→70%+）
- **P2**: confidence_threshold 0.62→0.65
- **P3**: A层规则维护（解绑噪声对）
- **P4**: 架构升级（reranker/反馈闭环）

详见 `plans/ssr/master-status.md` 第十章。

---

### 修复前的强制检查顺序（不可违反）

发现 SSR 无推荐或有 Error 时，**按此顺序检查，不要先修解析器**：

1. 管道是否跑到 B 层：`grep '\[ssr\]' agent.log | tail -20` 看停在哪一节
2. 配置：`b_layer.provider` / `api_key` / `timeout` / `display` / `similarity_floor`
3. Ollama 连通性：手动跑一次 `/api/chat` 看真实输出和耗时
4. 模型的 JSON 输出格式：先抓 raw content，再决定解析策略
5. 最后才修 JSON 解析器

违反此顺序的代价：2026-07-05 会话白修 6 轮解析器。详见 `references/ssr-b-layer-troubleshooting.md`。

SSR (Smart Skill Router Plugin) v2.1.1 的日常运维：存活验证、Benchmark 三档相关度评分（精准/相关/不相关）、--quick 零 LLM 模式、动态阈值（无极优先+有极兜底）、LLM 筛选开关、元对话检测、Dashboard v2.1 设置卡片、对外发布审计、全量 grep 审计、calibrate_floor 无极校准。

**当前基线（2026-06-24）：** 相关度 93% (Qwen3-Embedding-8B 4096维) | 噪音 100% | llm_screen 默认关 | meta_detection 已移除（收益忽略不计）| 无显式 similarity_floor（动态阈值自动计算）| benchmark 三档评分（精准/相关/不相关）| Dashboard 纯平设计（已去玻璃效果/AI 味）。

**SSR 自指诊断包（2026-07-04 实战）→**
- `references/ssr-display-cache-write-before-check.md` — display 双重门：缓存在检查前写入
- `references/ssr-meta-convo-regex-audit.md` — 元对话正则盲区：信号/命中率/benchmark 等词缺失
- `references/ssr-silent-short-circuit.md` — 极短噪音沉默拦截：len<4 无日志
**Phantom embedding 诊断 →** `references/ssr-phantom-embedding-diagnosis.md`（2026-07-04 实战：desc=N/A 条目→随机余弦相似度→伪匹配修复）
**Ollama B 层集成 →** `references/ollama-b-layer-integration-pitfalls.md`（2026-07-05 实战修复：6 坑位——推理模型 content 为空/配置不一致/冷启动超时/format:json 空白行/单引号 JSON/pyc 缓存）

**a_rules.json 直接编辑被覆盖（2026-07-25）→** `references/flush-overwrite-pitfall.md` — SSR 内存 `_A_RULES` 每 5 次 A 层命中刷新到磁盘，覆盖手动编辑。解决方案：改完重启 Hermes。

## 设计原则（不可妥协）

| 原则 | 含义 | 反例 |
|------|------|------|
| **零硬编码** | 模型名、端点、阈值、prompt 全部从 config.yaml 读取。换模型不换代码。 | `model = "bge-m3"` ← 死 |
| **可发布** | 对外文件不泄露隐私、不写死个人配置。docstring/README 是给陌生用户看的。 | docstring 写 `Qwen3-Embedding-8B 4096维` |
| **通用** | deepseek-v4-pro + Qwen3-8B 能用，别人的 ollama + bge-m3 也能用。 | benchmark 硬依赖 API |
| **快速上手** | 新用户装完就能跑。`--quick` 零依赖验证。动态阈值免手动调参。 | "请先配置 5 个参数" |
| **高信号** | 该推的 skill 不漏。信号命中率是核心指标。 | 学术写作 1/2 |
| **低噪音** | 不该推的时候闭嘴。噪音静默率是核心指标。 | gate 放过闲聊 |
| **配置渠道** | 通用配置模板 + model_scores.json 社区贡献。新模型出来后加一行 JSON 即可。 | 每次换模型改 3 处代码 |

## 触发条件

- 用户说"SSR dashboard""打开 SSR""测试 SSR""SSR 加载了吗""SSR 怎么没推荐""SSR 为什么一直在展示""SSR 为什么在最后"
- 怀疑 skill 自动匹配没工作、或推荐噪音过多、或 display 未关闭
- 跑 SSR 基准测试

### 坑点：`hermes config set` 把 JSON 数组存成字符串 → 代码迭代崩（2026-06-23 v2.1 实战）

**症状：** 用 `hermes config set ssr.meta_detection.patterns '["...", "..."]'` 设置 YAML 列表，写入后 patterns 变成单行 JSON 字符串 `"[\"ssr.*...\", \"智配路由\", ...]"` 而非 YAML 列表。代码 `for pat in patterns:` 迭代字符串 → 逐字符匹配 → 永远不命中。

**根因：** `hermes config set` 对复杂值（含 `[` `]` `,` `"`）按字面量存储，不做 YAML 解析。JSON 数组被当作普通字符串写入。

**正确做法：**
```python
# 用 execute_code 直接写 YAML，不走 hermes config set
import yaml
config_path = os.path.expanduser("~/.hermes/config.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)
# 修：如果 patterns 是字符串，解析为列表
import json
if isinstance(config['ssr']['meta_detection']['patterns'], str):
    config['ssr']['meta_detection']['patterns'] = json.loads(config['ssr']['meta_detection']['patterns'])
# 写入
with open(config_path, 'w') as f:
    yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
```

**验证：** `grep -A 3 'meta_detection:' ~/.hermes/config.yaml` 确认 patterns 条目以 `- ` 开头（YAML 列表格式），不是 `patterns: "[..."`（字符串格式）。

## 第零步：Web Dashboard（优先）

SSR 自带 Web 管理界面（`dashboard.py` + `dashboard.html`），单文件零依赖，Python 内置 http.server 直出。

```bash
cd ~/.hermes/plugins/ssr && python3 dashboard.py
# → http://localhost:8766
```

### Dashboard 设计规范（v2.1.1 重写 · 2026-06-24）

- 纯平设计——不用 glass/blur/backdrop-filter，不用 AI 暗色仪表盘套路
- 绿色单强调色（#10b981），暗/亮双主题
- Geist 字体，Geist Mono 等宽数字
- 统计卡片数值右对齐（`.stat-outer { text-align: right; }`），标签左对齐
- 表格 hits 列右对齐
- 行为设置卡片：LLM 二次筛选 + 显示推荐结果（meta_detection 已移除）
- 中英双语（`applyLang()` 初始化应用，`toggleLang()` 按钮翻转）

### 坑点：Dashboard 改前必须备份（再犯 2026-06-24）

每次 write_file/patch dashboard.html 前 `cp dashboard.html dashboard.html.bak.$(date +%m%d%H%M)`。2026-06-24 重构 CSS 时未备份，write_file 丢失全部 HTML/JS，手写重建耗时 10+ 分钟。CMG ban 规则 `ban_no_backup_before_write` 已覆盖。

### 坑点：$() 函数 # 前缀 bug

`function $(id){return document.getElementById(id)}` 不处理 `#` 前缀。所有调用写 `$("#search")` → `getElementById("#search")` → null。修复：`id.replace(/^#/,"")`。更彻底：用 `el()` 替代 `$()`，参数不带 `#`。

### 坑点：init 中调 toggleLang 导致每次刷新语言翻转

`toggleLang()` 翻转 lang 值 + 写 localStorage。init 中调用 → 每次刷新语言反转到另一种。修复：拆出 `applyLang()`（只应用不翻转），init 调 `applyLang()`，按钮调 `toggleLang()`。

### 坑点：卡片开关右对齐 — 不要改 HTML 顺序，用 CSS margin-left: auto

用户要求"暂停 SSR \n 暂停后不推荐任何技能，这变到右边"。HTML 中 `<label class="switch">` 在最左边，需要推到行右端。不要改 HTML 顺序——用 CSS：`.card-row label.switch { margin-left: auto; }`。`.card-row` 已有 `justify-content: space-between`，margin-left: auto 叠加生效。

### 坑点：设计 skill 选择 — design-taste-frontend 明确排除 dashboard

`design-taste-frontend` SKILL.md Section 13：明确标注 NOT for dashboards。Dashboard 设计不应加载该 skill。可用：`ui-ux-pro-max`（配色/字体/UX 规范）+ `sleek`（极简仪表盘）+ `bento`（网格布局）+ `mono`（等宽数字）等 typeui.sh 风格 skill。不要用 `neobrutalism`（太重）、`glassmorphism`（AI 味）。

### 坑点：$() 函数 # 前缀 bug

`function $(id){return document.getElementById(id)}` 不处理 `#` 前缀。所有调用写 `$("#search")` → `getElementById("#search")` → null。修复：`id.replace(/^#/,"")`。

### 坑点：init 中调 toggleLang 导致每次刷新语言翻转

`toggleLang()` 翻转 lang 值 + 写 localStorage。init 中调用 → 每次刷新语言反转到另一种。修复：拆出 `applyLang()`（只应用不翻转），init 调 `applyLang()`。

### Dashboard 三维基准测试（v2.0.0+）

评分测试区有三个独立按钮，分别跑不同维度：

| 按钮 | API | 测什么 | 耗时 |
|------|-----|--------|------|
| **总评分** | `POST /api/benchmark/total` | 全链路（A层keyword + Embedding + B层LLM） | ~30s |
| **Embedding** | `POST /api/benchmark/embedding` | Embedding 语义匹配裸分 | ~10s |
| **门控** | `POST /api/benchmark/gate` | 本地模型意图门控 | ~5s |

后端 `dashboard.py` 将 mode 参数传给 `ssr_scoring_benchmark.py --mode <mode> --json`，单模式只跑对应测试，不再捆版全跑。旧 `/api/benchmark` 端点保留（等价于 `--mode all`）。

**先检查是否已运行：** `lsof -ti:8766` — 有 PID 则直接 `open http://localhost:8766`。

### 坑点：Dashboard 面板设计不要用 ASCII/markdown 草图（2026-06-21 实战）

**症状：** 设计 Embedding 模型诊断面板时，用 ASCII 框图画出"┌─── Embedding Model ──┐"草图给用户看。用户当场纠正：「这样设计太丑了，没必要用 ascii 或者 markdown。看看有没有设计用的 skill，设计板块和整个 dashboard」。

**根因：** AI 习惯用 ASCII/markdown 快速表达想法——但在 UI 设计场景下这是反模式。ASCII 草图传递不了间距、颜色、质感、比例——而这些才是设计决策的核心。

**正确做法：**
1. 设计任何 Dashboard UI → 先加载设计 skill（`dashboard` + `ui-ux-pro-max`），拉取设计 token
2. 用设计 token（颜色/间距/字体/圆角）描述面板，不画 ASCII
3. Dashboard 页面设计只推荐 `dashboard` skill 的 token 体系——不要用 `high-end-visual-design`（代理商营销页）或 `design-taste-frontend`（明确排除 dashboard）
4. 如果用户要看效果 → 写代码后在浏览器里截图验证，不在对话里 ASCII 模拟

**设计 token 参考（来自 `dashboard` skill）：**
```
surface: #09090b · surface-elevated: #18181b · accent: #0C5CAB
success: #10b981 · warning: #f59e0b · danger: #ef4444
radius: 12px · grid: 8px · font: IBM Plex Sans
```

## 第零-B 步：Auto-Gen 验证（v0.4.0+）

SSR v0.4.0 引入 `_auto_gen_a_rules()`：启动时从本地 skill description 自动生成 A 层规则，不再依赖预置 JSON。

**验证 auto-gen 是否生效：**

```bash
grep 'auto-gen' ~/.hermes/logs/agent.log | tail -1
```

期望输出：`[ssr] 插件注册完成 | 可用 skill: 293 | 残骸: 0 | A 层规则: 1214 (auto-gen: +1204) | B 层: main/ timeout=30s`

**auto-gen 行为：**
- 遍历 `_SKILL_INDEX` 中所有 skill 的 description
- 提取英文 3+ 字母词（过滤停用词）和中文 2-4 字词作为关键词
- 已有规则（手动添加/B 层升级）不被覆盖
- 每次启动重新生成 → **规则集自动适配当前 skill 集**

**不绑定特定 skill 集：** 你换机器、别人装 SSR → 各自匹配自己的 skill，规则完全解耦。

**⚠️ auto-gen 准确率只有 10%。** 这是已知问题——Phase 2 将用 Embedding 语义匹配替代关键词。

### 第零-C 步：Embedding 索引验证（v0.5.0+，Phase 2）

SSR v0.5.0 引入 Embedding 语义匹配（替代 auto-gen 关键词）。

**推荐模型（按优先级）：**

| 模型 | 大小 | 维度 | 中文质量 | Top-5 命中 | 国内安装 |
|------|------|:--:|:--:|:--:|------|
| **bge-large-zh-v1.5** (CompendiumLabs) | 202MB | 1024 | ★★★★★ 纯中文优化 | **66%** (15条中文) | hf-mirror 13秒 |
| qwen3-embedding:0.6b | 639MB | 1024 | ★★★★ 多语言 | **66%** (15条中文) | `ollama pull` |
| bge-m3 (BAAI 多语言) | 437MB | 1024 | ★★★★ 多语言 | 55% (20条中文) | hf-mirror |
| qwen3-embedding | 4.7GB | 4096 | ★★★★★ 中文原生 | 未测 | Ollama |
| ~~text2vec-bge-large-chinese~~ | 207MB | 1024 | ❌ Ollama 崩溃 | — | 不可用 |

> **基准数据来源：** 2026-06-21 会话实测。bge-large-zh-v1.5 在 20 条中文查询 Top-5 命中率 60%，比 bge-m3(55%) 高 5 个百分点。纯中文场景（"论文文献综述""新疆美食""暗色仪表盘"）优势明显，英文混排场景（"KeyError""Python单元测试"）bge-m3 略优。
>
> **qwen3-embedding 警告：** 4.7GB 模型在 8GB Mac 上不可用——加载后 swap 炸到 320GB+，每调用 3-5 秒，388 skill 索引重建需 19 分钟，execute_code 沙箱直接超时。不推荐。
| ~~text2vec-bge-large-chinese~~ | 207MB | 1024 | ❌ Ollama 崩溃 | 不可用 | — |

> 中文基准 20 查询详见 `references/chinese-benchmark.md`。

**⚠️ `nn200433/text2vec-bge-large-chinese` 在 Ollama 中崩溃（GGML 断言失败），不要使用。**

**安装 bge-large-zh-v1.5（推荐，纯中文优化，202MB，hf-mirror 14秒）：**
```bash
# 从 hf-mirror 下载 GGUF（国内极速）
curl -L -o ~/Downloads/bge-large-zh-v1.5-q4_k_m.gguf \
  "https://hf-mirror.com/CompendiumLabs/bge-large-zh-v1.5-gguf/resolve/main/bge-large-zh-v1.5-q4_k_m.gguf"
ollama create bge-large-zh-v1.5 -f <(echo "FROM ~/Downloads/bge-large-zh-v1.5-q4_k_m.gguf")
```

**安装 bge-m3（备选，多语言，437MB）：**
```bash
curl -L -o ~/Downloads/bge-m3-q4_k_m.gguf \
  "https://hf-mirror.com/groonga/bge-m3-Q4_K_M-GGUF/resolve/main/bge-m3-q4_k_m.gguf"
ollama create bge-m3 -f <(echo "FROM ~/Downloads/bge-m3-q4_k_m.gguf")
```

**验证 embedding 可用：**
```bash
curl -s http://localhost:11434/api/embeddings -d '{"model":"bge-large-zh-v1.5","prompt":"测试中文"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'embedding' in d else d.get('error','?'), len(d.get('embedding',[])), '维')"
# 期望: OK 1024 维
```

**⚠️ 换模型必须验证四步（只改 config ≠ 切换成功）：**
```bash
# ① 模型在 Ollama 中
ollama list | grep <模型名>
# ② API 可用（直调，不等 register）
curl -s http://localhost:11434/api/embeddings -d '{"model":"<模型名>","prompt":"test"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'embedding' in d else f'FAIL: {d}')"
# ③ config.yaml 一致
grep 'embedding:' -A 3 ~/.hermes/config.yaml | grep model
# ④ 删旧索引 + 重启 Hermes（完整退出，非 /new）
TS=$(date +%Y%m%d_%H%M)
cp ~/.hermes/plugins/ssr/embeddings.json ~/.hermes/plugins/ssr/embeddings.json.bak.$TS
rm ~/.hermes/plugins/ssr/embeddings.json
# → 重启 Hermes → register() 重建索引
```

**embedding 多后端设计：**
```
ssr.embedding.provider:
  推荐: ollama (bge-large-zh-v1.5, 本地免费, 202MB, 1024维, 纯中文)
  备选: ollama (bge-m3, 437MB, 1024维, 多语言)
  备选: siliconflow (BAAI/bge-large-zh-v1.5, 免费需 API key)
  备选: openai (text-embedding-3-small, 付费)
```

**⚠️ 换模型必须删旧索引（即使维度相同！）：** 不同模型向量空间不同。`rm ~/.hermes/plugins/ssr/embeddings.json` + 重启 Hermes。

**embedding 索引验证：**
```bash
python3 -c "import json; d=json.load(open('$HOME/.hermes/plugins/ssr/embeddings.json')); print(f'{len(d)} skill, {len(d[list(d.keys())[0]][\"embedding\"])}维' if d else 'embeddings.json 为空，重启 Hermes 重建')"
# 期望: 371 skill, 1024维
```

## 噪音过滤（v2.1.0+ · 配置驱动）

> **2026-06-23 重构：** 旧版硬编码 `_NOISE_PATTERNS` 已移除。所有噪音模式统一在 `config.yaml` 的 `ssr.noise_filter.patterns` 中，用户可自由编辑。代码层只保留通用任务动词安全阀（含 任务动词 的消息不受噪音规则拦截）。

```yaml
ssr:
  noise_filter:
    enabled: true
    patterns:
      # 短确认/闲聊 — 17条正则，免调LLM
      - '^[嗯哦啊噢好对行可]{1,3}[.!~。！～]*$'
      - '^(谢谢|感谢|多谢|谢啦|3Q|thx|thanks)[你您]?[.!~。！～]*$'
      ...
      # 元讨论/系统自指
      - '(SSR|ssr).*(优化|怎么样|能不能|推荐|匹配|加载|命中|好用)'
      - 'CMG.*(拦截|hook|规则|激活|约束)'
      ...
```

**任务动词安全阀（代码内置，不可配置）：** `设计|写|生成|部署|画|做|创建|构建|实现|修复|分析|查询|搜索|查找|计算|转换|优化|配置|安装|发送|测试|帮我|安排|规划|总结|翻译|解释|对比|检查|调试|诊断|处理|整理|推荐|评估` — 命中任一 → 放行，不受噪音规则拦截。

## 显示控制：`ssr.display: false` → `return None`（完全不推荐），不再用 `[SSR:SILENT]` 障眼法前缀。
> **v2.3.5 新增 report 开关：** `ssr.report: true` → AI 每轮汇报 SSR 使用情况。详见 `references/display-report-switches.md`。

### 快速诊断：SSR 推荐为什么每条回复都出现？

用户问「SSR 为什么每条回复都在最后展示？」→ 三步诊断：

```bash
# ① 检查 display 开关（最常见根因）
python3 -c "import yaml; c=yaml.safe_load(open('$HOME/.hermes/config.yaml')); print(c.get('ssr',{}).get('display', 'NOT SET'))"
# True → 就是这个。关掉：
hermes config set ssr.display false
# → 重启 Hermes 生效（完整重启，非 /new）
```

**注意：** SSR 用 `post_llm_call` 注入推荐，配置 `position: prepend` 是前置到回复开头——但 `[SSR] ...\n---\n正文` 的分隔线格式让推荐看起来像附录。不是 bug，是视觉错觉。真正关闭用 `display: false`，不是改 position。

## 对外发布审计（v2.1+ · 2026-06-23 实战）

每次发布或大改后必做全量 grep 审计。

### 铁律

**对外发布的文本（docstring、README、CHANGELOG 标题）不写具体模型名和维度数。** 只写架构描述（"Embedding 语义匹配"），不写实现细节（"Qwen3-Embedding-8B 4096维"）。

### 审计命令

```bash
cd ~/.hermes/plugins/ssr

# ① 扫描模型名/维度泄漏（对外文本）
grep -nIE 'bge|qwen|siliconflow|1024维|4096维|[0-9]+维' __init__.py README.md
# ⚠️ 代码实现层的 provider 检测/API URL 不算泄漏。只清 docstring/注释中的模型名。

# ② 版本号一致性（排除 CHANGELOG/README 历史版本）
CANONICAL=$(python3 -c "import yaml; print(yaml.safe_load(open('plugin.yaml'))['version'])")
echo "规范: $CANONICAL"
grep -rn 'v[0-9]\.[0-9]' *.py plugin.yaml | grep -v '.bak' | grep -v 'CHANGELOG' | grep -v 'README'
# 每个不一致都需修正

# ③ 格式残留 — a_rules.json 不能有旧 skills 字段
python3 -c "
import json
with open('a_rules.json') as f: rules = json.load(f)
old = sum(1 for v in rules.values() if isinstance(v,dict) and 'skills' in v)
new = sum(1 for v in rules.values() if isinstance(v,dict) and 'keywords' in v)
print(f'v2(skills): {old}, v3(keywords): {new}')
if old: print('⚠️ 发现旧格式残留')
"

# ④ 死文件/备份清理
find . -name '*.bak*' -o -name '*_v3*' | wc -l
# >0 → 清理后再发布

# ⑤ 配置示例一致性 — __init__.py docstring 的 config 示例是否覆盖当前版本所有 key
grep -A 20 '配置（config.yaml）' __init__.py
```

### 坑点：审计 grep 勿含 CHANGELOG/README — 历史版本号必误报

CHANGELOG.md 和 README.md 的版本历史表按设计包含所有历史版本号。grep 时排除这两个文件，只检查活跃源码（`*.py` + `plugin.yaml`）。

### 坑点：对外不发模型名 — docstring 零泄漏

用户两次纠正：「不要写模型名」「4096、1024 都不要写」。docstring 是用户第一眼看到的文档——写 `bge-m3 1024维` 换模型后立刻过时。只写「Embedding 语义匹配」，配置示例用 `xxx` 占位。

---

## 动态阈值（v2.2+ · 无极优先+有极兜底）

`_similarity_floor()` 优先级：config 显式设置 > 无极校准值（calibrated_floor）> 有极查表（overall 得分映射）> 默认 0.35。

**无极校准：** `tests/calibrate_floor.py` 实测 embedding 分布 → 写入 model_scores.json 的 `calibrated_floor` → 公式连续计算（`noise_baseline + (signal_avg - noise_baseline) × 0.25`）。任何用户换模型后跑一次校准即用。

**有极兜底：** 无校准数据时查 `overall` 得分（5→0.25, 4→0.30, 3→0.35, 2→0.42, 1→0.48）。

**验证：**
```bash
grep '自动 floor' ~/.hermes/logs/agent.log | tail -1
# 期望: [ssr] 自动 floor (无极): Qwen3-Embedding-8B → 0.xxx
# 或:   [ssr] 自动 floor (有极): Qwen3-Embedding-8B (得分 5) → 0.25
```

---

## 第一步：存活验证（CLI 备选）

每次必须运行此命令，不可凭记忆或假设判断：

```bash
grep 'ssr' ~/.hermes/logs/agent.log | tail -10
```

### ⚠️ 存活验证 ≠ 基准测试通过（2026-06-09 实战坑点）

**三段式存活验证只能回答一个问题：SSR 插件是否在运行并产出推荐。** 不能回答"推荐是否准确"。

| 验证了什么 | 验证不了什么 |
|-----------|------------|
| 插件已注册（skill: 296, A层: 2110, emb: 246） | 推荐给用户的 skill 是不是用户需要的 |
| A 层在命中（`A 层命中: [...]`） | 命中的大部分 skill 是否相关 |
| Embedding 索引存在且可用 | 语义匹配的 top-30 中有几个是对的 |

**存活验证绿灯 ≠ 可以报告"SSR 全部通过"。** 匹配质量只能通过第三步的 GREEN 5 场景基准测试验证。看到三段式全绿时，必须补充："存活验证通过——但 GREEN 基准测试尚未执行，匹配准确率未知。"

**三段式快速诊断（存活用，非质量用）：**
```bash
# ① 存活确认
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# ② 实时命中
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -3
# ③ 合并效果（关键词+Embedding 双路径）
grep 'embedding' ~/.hermes/logs/agent.log | tail -3
```
三条全有输出 → SSR 在运行。但要回答"推得准不准"→ 必须跑第三步 GREEN 基准。

### ⚠️ 先判定：完整重启 vs /new

**`register()` 只在 Hermes 启动时执行一次。** `/new`（新会话）不会重新注册插件——hook 持续生效，但不会输出"插件注册完成"日志。

| 场景 | register() 执行 | 注册日志出现 | hook 生效 |
|------|:---:|:---:|:---:|
| Hermes 完整重启 | ✅ | ✅ | ✅ |
| `/new` 新会话 | ❌ | ❌ 不出现 | ✅（从上次启动继承） |

**判定方法：**
```bash
# 有新的 gateway 连接 + SSR 注册日志 → 完整重启
grep 'tui_gateway.ws.*accepted' ~/.hermes/logs/agent.log | tail -3
# 只有 conversation_turn、无 gateway 日志 → 只是 /new
```

### 坑点：测试"X缺失"假警报 → 未区分"未安装"和"重建失败"（2026-06-21 实战）

**症状：** A 层规则检查报 `❌ A 层 skill 在 embedding 中 6 缺失 (已知3个空描述，待重启重建)`。用户重启 Hermes 两次，embedding 重建了 387 skill，但测试仍然报 6 缺失。

**根因：** 这 6 个 skill（ascii-art、baoyu-article-illustrator、comfyui、p5js、pixel-art、popular-web-designs）**根本没安装**——没有 SKILL.md → 没有 description → 从未被 embed。测试把它们等同于"重建失败"，误导用户反复重启。

**修复（test_ssr.py）：**
```python
# 区分：未安装 vs 真正缺失（安装但无 embedding）
not_installed = {name for name in missing
                 if not any((base / f"**/{name}/SKILL.md").exists()
                           for base in (skills_base, agents_base))}
if not_installed:
    skip_test(...)  # 跳过，不是故障
elif truly_missing:
    test(..., False, ...)  # 真正的缺失
```

**修复（__init__.py）：** A 层关键词匹配中过滤未安装 skill：
```python
for skill_info in rule.get("skills", []):
    name = skill_info if isinstance(skill_info, str) else skill_info.get("name", "")
    if name not in _SKILL_INDEX:  # ← 未安装，跳过
        continue
```

**教训：** 测试报"缺失"时必须区分两个根因——是 skill 没装（正常），还是装了但 embedding 没建（故障）。前者不应报错。

### 🚫 铁律：禁止手动硬编码 a_rules.json 的 skill 引用（2026-06-21 被两次纠正）

**用户当场纠正：**「未安装为什么会被推荐？？幻觉？」→「可能是我归档了，skill列表肯定是实时变动的，有可能会多出新的，也有可能卸载旧的。我再重申一遍，不能写硬编码」。

**现状（v1.7.0）：三层自动适应机制，零硬编码：**
1. **运行时过滤**：`_match_a_layer_keyword()` 跳过 `_SKILL_INDEX` 外的 skill → 死引用不会推荐出去
2. **启动自动清理**：`_cleanup_a_rules()` 每次启动扫描死引用→移除，空规则保留作意图信号
3. **热删除联动**：`_hot_remove_skill()` skill 卸载时实时清理 A 层引用

skill 装/卸/改名 → 规则自动跟。**禁止手动编辑 a_rules.json 的 skill 列表。** 如果有人告诉你「手动改 ascii-art → creative」，那是在制造下一个死引用。

### 坑点：A 层规则引用了未安装的 skill → 自动清理已内置，不再需手动操作（2026-06-21 v1.7.0）

**症状：** a_rules.json 中 7 条规则引用了 6 个未安装的 skill。旧方案是手动清理。

**v1.7.0 修复（自动）：** 启动 `_cleanup_a_rules()` 自动扫描 + 移除死引用。空规则不删除（保留作为关键词意图信号，`_match_a_layer_keyword` 的 `_SKILL_INDEX` 过滤已阻止死推荐）。

**验证自动清理是否生效：**
```bash
grep 'A 层死引用清理' ~/.hermes/logs/agent.log | tail -1
# 期望：[ssr] A 层死引用清理: N 个 → 删除 0 条空规则
```

**手动清理（仅当自动清理失效时）：**
```bash
# ① 备份
cp a_rules.json a_rules.json.bak.deadref

# ② 扫描死引用 + 清理
python3 -c "
import json
from pathlib import Path
rules = json.loads(open('a_rules.json').read())
# 收集已安装 skill
installed = set()
for base in (Path.home()/'.hermes'/'skills', Path.home()/'.agents'/'skills'):
    for md in base.rglob('SKILL.md'):
        for line in md.read_text().split(chr(10)):
            if line.startswith('name:'):
                installed.add(line.split(':',1)[1].strip()); break

cleaned = 0
to_delete = []
for pattern, rule in list(rules.items()):
    new_skills = [s for s in rule.get('skills',[]) if (s['name'] if isinstance(s,dict) else s) in installed]
    cleaned += len(rule.get('skills',[])) - len(new_skills)
    if not new_skills: to_delete.append(pattern)
    else: rule['skills'] = new_skills
for p in to_delete: del rules[p]
print(f'移除 {cleaned} 死引用, 删除 {len(to_delete)} 空规则, 剩余 {len(rules)} 条')
with open('a_rules.json','w') as f: json.dump(rules, f, ensure_ascii=False, indent=2)
"

# ③ 检查是否有 GREEN 基准规则被误删 → 从备份恢复并改引用的 skill
grep 'ascii\|popular-web\|comfyui\|p5js\|pixel\|baoyu' a_rules.json.bak.deadref
# 有 GREEN 测试覆盖的规则 → 恢复 + 替换为已安装的 skill
```

**⚠️ 清理后必须重跑 GREEN 基准。** 删除规则可能导致某些测试场景零命中——如果规则有 GREEN 测试覆盖，恢复规则但换一个已安装的 skill 引用。本 session 实例：`ascii-art` 规则被删 → GREEN·ASCII 场景 0 命中 → 恢复规则改引 `creative`。

### 坑点：幻觉模型参数 —— DeepSeek v4-pro 是 1M 上下文，不是 128K（2026-06-22 被纠正）

**症状：** AI 分析纯LLM方案 54% 准确率时，说「218个skill信息过载导致LLM频繁判NO_NEED」。用户当场纠正：「v4 pro是1m的上下文，你幻觉太多了」。

**根因：** 不是上下文过载——是 prompt 设计问题让 LLM 误判「帮我写论文」为它能直接处理的请求。用伪技术解释掩盖 prompt 设计缺陷。

**正确做法：** 引用模型参数前必须确认实际规格。DeepSeek v4-pro = 1M 上下文。说「信息过载」前先用更大 prompt 验证，而不是直接下结论。

### 坑点：日志分析≠实测 —— 二手数据不能替代端到端验证（2026-06-22 实战）

**症状：** 用户问「实测的？」。AI 运行 grep、读 config、分析日志统计（命中率 97%）→ 报告 SSR 健康。用户纠正——日志是二手数据，97% 来自上一会话的已覆盖类目（学术/金融），当前会话盲区从未触发。

**正确做法：**
1. 用测试消息（「画一个登录页面」「部署到Vercel」「分析这段感情」）端到端验证
2. 直测 API（curl Ollama embedding + DeepSeek chat/completions）
3. 报告结论时区分「日志显示」和「实测验证」——前者是参考，后者是证据

### 坑点：版本审计 grep 勿含 CHANGELOG/README —— 历史版本号必误报（2026-06-23 实战）

**症状：** 格式迁移审计第①步 `grep -rn 'v[0-9]\\.[0-9]' *.py *.yaml *.md` 返回 38 条命中，其中 20+ 条来自 CHANGELOG.md 和 README.md 的历史版本表（`v1.6.0`、`v0.6.3`...），全部标记为"与规范版本不一致"——假阳性。

**根因：** CHANGELOG.md 按设计包含所有历史版本号，README.md 含版本历史表。这些不是不一致——是版本档案。

**正确做法：** grep 排除 `CHANGELOG|README`，只检查活跃源码：`*.py` + `plugin.yaml`。或把 CHANGELOG/README 的命中标记为"历史版本（忽略）"。

### 坑点：版本号缩写残留 —— `v2.0` 能被 grep 抓到但 `v2.0.0` 的 grep 漏过（2026-06-23 实战）

**症状：** test_ssr.py 两处写 `v2.0`（少 `.0` 补丁位），`grep -rn 'v[0-9]\\.[0-9]'` 能抓到（命中 `v2.0`），但如果用更严格的 `grep -rn 'v[0-9]\\.[0-9]\\.[0-9]'`（三段的版本号）就漏过——`v2.0` 不匹配三段式。且 `v2.0` 在 `grep -rn 'v2\\.0\\.0'` 中也漏过——`v2.0` ≠ `v2.0.0`。

**根因：** 代码注释/docstring 中可能使用缩写 `v2.0` 而非全称 `v2.0.0`。不同 grep 模式的覆盖域不同。

**正确做法：**
```bash
# ✅ 两步 grep，互补覆盖
# 第一步：宽松匹配（抓 v2.0 和 v2.0.0 以及其他所有 vX.Y 格式）
grep -rn 'v[0-9]\.[0-9]' *.py plugin.yaml | grep -v CHANGELOG

# 第二步：验证：三段式版本号 grep 也跑一遍，确认没有漏网
grep -rn 'v[0-9]\.[0-9]\.[0-9]' *.py plugin.yaml | grep -v CHANGELOG

# 两个结果合并取并集，与 plugin.yaml 规范版本号逐条对比
```

### 坑点：grep 输出被会话日志污染 → 假阴性（2026-06-22 实战）

**症状：** `grep '插件注册完成' agent.log | tail -1` 返回 conversation turn 日志行而非注册行，误判 emb=0。实际 emb=387。

**根因：** 搜索字符串在日志中不存在时，某些 shell 环境返回缓冲区相邻内容。输出存在≠匹配存在。

**正确做法：** 三步确认：grep + echo $?（exit code 0=匹配到） + grep -c 计数。exit 1 但有输出 = 污染。

### 坑点：硅基 API key 在 `~/.hermes/tokens/siliconflow`，不在 config.yaml（2026-06-23 实战）

**症状：** 配置硅基 embedding 时用 `config.yaml` 中 `custom_providers[0].api_key` → 401。config.yaml 中的硅基 key 是旧版残留（尾号相同但内容不完整）。

**正确位置：** `~/.hermes/tokens/siliconflow`。用户手动存放。读取：
```python
with open(os.path.expanduser('~/.hermes/tokens/siliconflow')) as f:
    key = f.read().strip()
```

**注意：** 硅基 `/v1/embeddings` 要求 `"input": ["text"]`（数组），不是 `"input": "text"`（字符串）。字符串格式也会返回结果但质量下降。

### 坑点：API key 在测试代码中截断 → 假 401（2026-06-22 实战）

### 坑点：benchmark 独立模式不支持 siliconflow → 全零分（2026-06-23 实战）

**症状：** `--mode embedding` 切硅基后 `信号命中: 0/0, 延迟: 46ms`。索引文件正确（403 skill, 4096维），但 benchmark 静默失败。

**根因：** `ssr_scoring_benchmark.py` L98-106 的 `_embed_text()` 硬编码了 Ollama URL。硅基索引的 4096 维向量和 Ollama 返回的 1024 维查询向量维度不匹配，全部跳过。

**修复：** `_embed_text()` 改为多后端——从 config 读 `EMB_PROVIDER`，ollama 走 `/api/embeddings`，siliconflow 走 `/v1/embeddings`。不硬编码 provider。

### 坑点：API key 在测试代码中截断 → 假 401（2026-06-22 实战）

**症状：** Python 脚本硬编码 key 为 `sk-7c6...5711`（含字面 `...`）→ API 返回 401。误判 key 过期。实际 .env 完整 key 有效。

**根因：** 字符串中的 `...` 不是省略号——是三个字面句点。API 收到的 Authorization header 就是截断版。

**正确做法：** 永远从文件读完整 key（`open('.env').read()`），不截断、不手打、不打印。

### 坑点：B 层 404 是上一会话残留 → 误判当前故障（2026-06-22 实战）

**症状：** `grep 'LLM 筛查 HTTP 404' agent.log | tail -1` 返回上一会话（000042）的错误。误判当前会话（001339）B层故障。实际当前零404。

**正确做法：** 诊断前先确认会话范围。`grep '插件注册完成' agent.log` 取当前 session ID，再限定 grep 范围。

**检测：** 
```bash
# 意图门控从未产生日志（连 NO 都没有）
grep '意图门控' ~/.hermes/logs/agent.log
# 空输出 = 门控一次都未被调用过

# 确认 intent_gate config 引用已删除模型
grep -A 5 'intent_gate:' ~/.hermes/config.yaml
# providers[0].model: qwen2.5:3b → ollama list 已不存在
```

**当前架构实际流程：** embedding → A层关键词 → LLM筛查。无噪音前置拦截、无意图门控、无 B 层兜底。

### 坑点：B 层筛查收紧被用户纠正 — 新陈代谢机制已存在，不滥推（2026-06-23）

**症状：** AI 改 `_llm_screen` prompt 为"宁可漏推不可滥推"，用户当场纠正：creative/canvas-design/doodle 对"画猫"有帮助（虽然不是精确 ascii）。毫不相关的（threejs、industrial-brutalist）才是噪音。

**正确做法：** 不改 B 层筛查。新陈代谢机制已存在——推了用户没加载 → 冷却延长 → 自然淘汰。"有帮助但非精确"的推荐应该保留。只有完全无关的 skill 才是噪音。

**症状：** A 层盲区场景（PPT/地图/微信）永远无推荐。`_pre_llm_call` L1845-1847: `if not result: return None`。

**检测：**
```bash
# 看有多少 miss（A层无候选 → 直接放弃）
grep '无匹配' ~/.hermes/logs/agent.log | tail -5
# miss 率高 + 无后续 B层调用 = 兜底缺失
```

**待修复：** A 层无候选 → `_match_b_main(user_message)` 独立匹配（函数仍存在可用）。

**症状：** 用户用 `grep '意图门控' ~/.hermes/logs/agent.log | tail -3` 验证门控是否加载 → 返回空（只有用户消息回显）。误判为「门控未加载，需重启」。

**根因：** 意图门控在 `pre_llm_call` 内联运行——通过时静默（无日志），拒绝时打 `logger.debug("[ssr] 意图门控: NO → 静默")`。debug 级别日志通常不出现在 agent.log。没有独立的「门控已加载」注册消息。

**正确做法：**
```bash
# ① 确认 SSR 插件已注册（门控是插件的一部分）
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# ② 确认 config 中门控开启
python3 -c "import yaml; c=yaml.safe_load(open('$HOME/.hermes/config.yaml')); ig=c.get('ssr',{}).get('intent_gate',{}); print(f'enabled={ig.get(\"enabled\")}, providers={ig.get(\"providers\",[])}')"
# ③ 发一条信号消息验证实际效果（最可靠）
# 发送「帮我设计一个暗色仪表盘」→ grep 'A 层命中' agent.log | tail -1
```

**判断：** ①② 都满足 + ③ 有命中 → 门控已生效。`grep '意图门控'` 返回空是正常行为，不是故障。

### 三种状态判定

| A 层规则 | Embedding 索引 | B 层状态 | 实际效果 | 动作 |
|---------|:---:|---------|---------|------|
| >0 | >0 | 正常 | ✅ 三层漏斗全工作 | 正常使用 |
| >0 | 0 | 正常 | ⚠️ 仅 A 层+B 层 | 重建 embedding 索引 |
| 0 | >0 | 正常 | ⚠️ 仅 Embedding+B 层 | 重建 A 层规则 |
| **0** | **0** | 正常 | 🔴 仅 B 层孤跑 | **立即重建全部索引** |
| **0** | **0** | **超时/401** | ❌ SSR 形同虚设 | **立即降级为手动匹配 + 重建** |

**⚠️ 六格矩阵替换旧三格表（2026-06-12）。** 旧表只检查 A 层规则和 B 层状态，遗漏了 Embedding 索引维度。本会话生产环境确认：A 层 0 + Embedding 0 + B 层正常 = 推荐全废。"

### ⚠️ "无日志"的五种可能（必须区分）

当前会话日志中无 `[ssr]` 条目时，不代表 SSR 挂了：

| 现象 | 可能原因 | 判定方法 |
|------|---------|---------|
| 当前会话无 SSR 日志 | 只是 `/new`，register() 未重跑 | 查 gateway 日志确认 |
| 当前会话无 SSR 日志，但 gateway 有 | 完整重启但 register() 异常 | 查 root-level（无 session ID）的 WARNING/ERROR |
| 无 A 层/B 层命中日志 | 用户消息未匹配到任何 skill（如"看看ssr""ssr怎么样了"） | 正常——无匹配静默返回 None，不是故障 |
| 有注册日志但从未命中 | embedding 索引未构建 + auto-gen 准确率仅 10% | 查 embeddings.json 是否存在 |
| **注册成功但 hook 从未被调用** | pre_llm_call 注册了但 Hermes 没触发（多 hook 执行顺序/签名不匹配/logger 上下文） | 注册日志 `emb: >0` + 但当前 session 零 `[ssr]` 条目 → 见 [`references/hook-registered-but-not-fired.md`](references/hook-registered-but-not-fired.md) |
| **A 层 0 规则 + B 层 miss → 零日志（假性沉默）** | A 层空 + B 层无匹配 → `return None` 不记任何日志 → 看起来像 hook 未触发 | 查 `a_rules.json` 大小 + B 层连通性。若 A=0 且 B 超时 → 发触发消息验证。详见 [`references/silent-miss-path.md`](references/silent-miss-path.md) |

## 第零-E 步：门控 Prompt 直测（v2.1+ · 2026-06-23 实战）

Benchmark 脚本是独立模式——不 import 真实 SSR plugin，读不到 `config.yaml` 中的 `intent_gate.prompt`。验证门控 prompt 效果必须用 **httpx 直测 DeepSeek API**：

```python
# 从 config.yaml 读当前 prompt → 对 20 条噪音 + 15 条信号发 API
# 对比默认 prompt vs 优化 prompt 的拦截率/放行率
```

**本会话基准数据（DeepSeek v4-pro）：**

| Prompt | 噪音拦截 | 信号放行 |
|--------|:--:|:--:|
| 默认 "Does this user message need an AI skill?" | 95% (19/20) | 93% (14/15) |
| 优化（任务分类） | **100%** (20/20) | 93% (14/15) |

**优化 prompt（配置在 `ssr.intent_gate.prompt`）：**
```
Determine if this message needs a specialized AI skill
(code, design, analysis, research, data processing, planning,
deployment, debugging, writing, etc.).

Needs skill (YES): user wants a specific task done - building, creating,
analyzing, fixing, searching, planning, computing, generating, deploying.
No skill needed (NO): pure conversation, chitchat, greetings,
simple confirmations, emotional expressions, small talk.

Answer only YES or NO.
```

**坑点：改 prompt 前必须 benchmark 直测验证，不硬编。** 详见 `references/gate-prompt-benchmark-20260623.md`。

**坑点：meta_detection 一刀切正则不如让 LLM 判 NO 后自然静默。** 元对话检测（SSR/CMG 自指）如果判 YES → 进入 A层+embedding → B层筛查应判"全不相关→静默"。正则拦截是绕过问题，不是解决问题。

## 第二步：B 层后端确认

**关键：日志消息不可信，必须读 config 确认 provider。**

SSR 支持三种 B 层后端：

| Provider | 用途 | 配置位置 |
|----------|------|---------|
| `main` | 复用 Hermes 主模型（默认） | `config.yaml → ssr.b_layer.provider` |
| `ollama` | 本地 Ollama | `config.yaml → ssr.b_layer.provider: ollama` |
| `openai` | OpenAI 兼容 API | `config.yaml → ssr.b_layer.provider: openai` |

### 坑点：B 层从不命中 ≠ B 层挂了 —— 可能是 prompt 太保守（2026-06-21 实战）

**症状：** B 层日志持续 `B 层判断: 不需要 skill`，信号命中率仅 40%（4/10）。B 层 provider 正常、API 连通、无超时——但它对每条消息都回 NO。

**根因：** `_match_b_main` line 1345 的 prompt 设了二元门控：
```
先判断用户消息是否需要工具。不需要→只回答NO。需要→回答YES
```
DeepSeek 对大量技术任务判定"不需要工具"。

**诊断：**
```bash
# B 层命中率 = 0 且无超时/401 → prompt 保守
grep 'B 层判断\|B 层命中' ~/.hermes/logs/agent.log | tail -10
# 全部 "不需要 skill" + 零 "命中" = prompt 问题
```

**修复：** prompt 改为 "列出与此消息最相关的至多3个技能名"。详见 `~/.hermes/plans/ssr/b-layer-embedding-fix_plan.md`。

### 坑点：embedding 索引存在但不工作 —— 被 A 层关键词锁死（2026-06-21 实战）

**症状：** embeddings.json 含 388 skill，TDD 基准 5/5 GREEN。但实际会话中 embedding 从不产出推荐——因为 A 层关键词没命中时 embedding 不跑（line 626 `if keyword_result and _EMBEDDING_INDEX:`）。

**检测：**
```bash
# 对比 A 层命中 vs 实际应触发 embedding 的场景
grep 'A 层命中\|无匹配' ~/.hermes/logs/agent.log | tail -10
# 如果"无匹配"频繁出现但 TDD 基准全绿 → embedding 被锁
```

**修复：** 删 `keyword_result and` → `if _EMBEDDING_INDEX:`。详见修复计划。

### 10 信号 + 5 噪音快速验证（2026-06-21 实战测试模式）

完整的 SSR 质量验证分四步——存活→TDD→信号噪音→Dashboard。

**信号测试（11 条，覆盖主要域）：**

| # | 消息 | 期望命中 |
|---|------|---------|
| 1 | 帮我设计一个暗色仪表盘 | brainstorming, ui-ux-pro-max, frontend-design |
| 2 | Python代码报KeyError怎么调试 | diagnose, systematic-debugging |
| 3 | 分析茅台均线走势 | technical-analysis, tushare-finance |
| 4 | 北京自驾到南昌路线规划 | road-trip-planner, travel-skill |
| 5 | 帮我写论文文献综述 | research-paper-writing, survey |
| 6 | 画一个ASCII猫咪 | creative |
| 7 | 部署网站到Vercel | deploy-to-vercel, vercel-cli-with-tokens |
| 8 | 生成季度PPT汇报 | pptx |
| 9 | 画中国地图显示GDP | geographic-visualization, svg-geo-map |
| 10 | 发微信给示例用户A | wechat-desktop-send |
| 11 | 分析这段感情问题 | relationship-conflict-analysis, tong-jincheng-perspective |

**噪音测试（5 条）：**

| # | 消息 | 期望 |
|---|------|------|
| 1 | 今天天气怎么样 | 静默 |
| 2 | 谢谢你的帮助 | 静默 |
| 3 | 好的我明白了 | 静默 |
| 4 | 你觉得呢 | 静默 |
| 5 | 嗯嗯 | 静默 |

**验证命令：**
```bash
# 每条消息后查日志
grep 'A 层命中\|B 层命中\|无匹配' ~/.hermes/logs/agent.log | tail -1
# 信号：期望出现命中 | 噪音：期望出现无匹配
```

**通过标准：** 信号 ≥8/11 命中，噪音 5/5 静默。

**v1.7.0 实测（10信号 2026-06-21）：** 金融 4/4·学术 7/8·地图 2/2 精准 🟢，设计·自驾·调试 P档救援 🟡，部署·PPT·微信 D档空缺 🔴，ASCII 技能缺口 ⚠️。综合 2🟢+3🟡+3🔴+1⚠️。**v1.8.1 更新（2026-06-22）：** 补 UI（加「画/做/生成」前缀+4 skill）、部署（deploy-to-vercel）、情感（relationship-conflict-analysis）三条 A 层规则 → 部署+情感从 🔴→🟢，UI 从 🟡→🟢。详见 `references/signal-noise-test-20260621.md`。

冷启动预热代码（`__init__.py` 第 449-461 行）**硬编码了 Ollama 的 `/api/generate` 端点**，无论 provider 是什么。所以日志中出现 "Ollama 调用失败" **不代表 B 层配置的是 Ollama** ——很可能是 `main` 模式下预热请求打到 DeepSeek 的 `/api/generate`（不存在）超时。

**判断 B 层真身后端的方法：**

```bash
grep -A 10 'b_layer:' ~/.hermes/config.yaml
```

只看 `provider:` 字段，不信日志里的 "Ollama" 字样。

### 常见 B 层故障

| 日志特征 | 根因 | 修复 |
|---------|------|------|
| `401 Authorization Required` + `api.deepseek.com` | B 层 API key 过期 | 更新 `b_layer.api_key` |
| `timed out` + provider=main | 主模型不可用或预热 bug | 切换 `b_layer.provider: ollama` |
| `timed out` + provider=ollama | Ollama 未启动 | `ollama serve` |
| `404` + main provider | ① 上一会话残留（最常见，当前会话零错误）② api key 失效（某些状态下 DeepSeek 返回 404 非 401）③ 模型名不被 API 识别 | 三步诊断：① 确认当前 session → ② 直测 API（`.env` key + `deepseek-v4-pro`）→ ③ 直测通过则忽略日志残留。详见 `smart-skill-router` 坑点 54 |

### 坑点：grep 输出被会话日志行污染 → 假阴性（2026-06-22 实战）

**症状：** `grep '插件注册完成' agent.log | tail -1` 返回了一行 conversation turn 日志而非注册行，误判 emb=0。实际 emb=387，注册完好。

**根因：** 当搜索字符串在日志中不存在时，某些 shell 环境不会返回空——可能输出相邻行或其他缓冲区内容。输出存在 ≠ 匹配存在。

**正确做法：**
```bash
# ✅ 三步确认
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
echo "exit code: $?"  # 0=匹配到, 1=未匹配
# 如果 exit 1 + 有输出 → 输出是噪音，实际无匹配
# 额外验证：grep -c 计数
grep -c '插件注册完成' ~/.hermes/logs/agent.log
```

### 坑点：API key 在测试代码中截断 → 假 401（2026-06-22 实战）

**症状：** 用 Python 脚本直测 DeepSeek API 时，硬编码 key 为 `sk-7c6...5711`（含字面 `...`）→ 返回 401。误判 key 过期。实际 .env 中的完整 key 有效（200 OK）。

**根因：** 在 Python 字符串中写了截断的 key（`sk-7c6...5711`），`...` 不是省略号——是三个字面句点。API 收到的 Authorization header 就是截断版。

**正确做法：**
```python
# ✅ 永远从文件读完整 key，不截断不手打
with open(os.path.expanduser('~/.hermes/.env')) as f:
    for line in f:
        if 'DEEPSEEK_API_KEY' in line:
            key = line.strip().split('=', 1)[1]
# 然后 key 直接用于 API 调用，不打印不截断
```

### 坑点：日志分析 ≠ 实测 —— 翻日志不能替代端到端验证（2026-06-22 实战）

**症状：** 用户问「实测的？」。AI 运行了 grep、读了 config、分析了日志统计（"命中率 97%"）→ 报告 SSR 健康。用户当场纠正——这些是日志分析，不是实测。

**根因：** 日志是二手数据——只记录过去发生的事，不能证明当前状态。命中率 97% 的日志来自上一会话的已覆盖类目（学术/金融），当前会话盲区（UI/部署/情感）从未被触发过。

**正确做法：**
1. 用测试消息（「画一个登录页面」「部署到Vercel」「分析这段感情」）端到端验证
2. 直测 API（curl Ollama embedding + DeepSeek chat/completions）
3. 写 Python 脚本对 a_rules.json 做正则匹配测试
4. 报告结论时必须区分「日志显示」和「实测验证」——前者是参考，后者是证据

**判别标准：** 用户问「实测的？」= 对你的结论不信任。此时必须立即补充端到端测试，不能再引用日志。

### 坑点：B 层 404 是上一会话残留 → 误判当前故障（2026-06-22 实战）

**症状：** `grep 'LLM 筛查 HTTP 404' agent.log | tail -1` 返回上一会话（`000042`）的错误。误判当前会话（`001339`）B 层故障。实际当前会话零 404。

**正确做法：**
```bash
# ✅ 诊断前先确认会话范围
CURRENT_SESSION=$(grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1 | grep -oP '\d{8}_\d{6}_\w+' | tail -1)
grep "LLM 筛查 HTTP" ~/.hermes/logs/agent.log | grep "$CURRENT_SESSION"
# 如果无输出 → 当前会话无此问题；有输出 → 需修复
```

## 基准测试执行

三维评分脚本: `~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py`（50条·四元组格式·三档相关度评分）

```bash
# 快速冒烟（纯 A 层，零 LLM，31s，任何用户可跑）
python3 ~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py --mode total --quick

# 全链路（含 gate LLM + LLM 筛选，如 llm_screen 开启）
python3 ~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py --mode total
```

### 三档相关度评分

benchmark 数据格式：`(类别, 消息, 精准匹配, 相关可接受)` — 四元组。评分分三档：精准(2分) > 相关(1分) > 不相关(0分)。

```
相关度: 43/46 (93%)  |  精准 40 + 相关 3
分类: ✅ 设计 8/8  ✅ 调试 6/6  ⚠️ 学术 3/4
```

93% 相关度代表 93% 的用户会拿到一个能用（精准或相关）的 skill——比旧二进制 57% top-3 更接近真实体验。

### --quick vs total

| 模式 | LLM 调用 | 耗时 | 适用 |
|------|:--:|------|------|
| `--quick` | 0 | ~31s | 本地用户、弱模型用户、快速冒烟 |
| `--mode total` | ~28 次（仅 gate 噪音） | ~60s | API 用户、完整评估 |

### LLM 筛选开关（v2.1.1+ · 默认关闭）

`_llm_screen` 对 A 层候选做 LLM 重排序。已知降低 top-3 准确率（embedding 排序 57% → LLM 重排 50%），默认关闭。开启：`ssr.llm_screen: true`。

```bash
grep 'llm_screen' ~/.hermes/config.yaml
# 无输出 = 关闭（默认）

旧 GREEN 5场景脚本 `ssr-green-benchmark.py` 已废弃（硬编码 bge-m3 + 不兼容 v3）。TDD 5场景作为历史快速冒烟保留在 `smart-skill-router` SKILL.md 中。

### Force 模式（无需用户输入）

用户说"帮我跑 GREEN"时，用 `execute_code` 直接对 `a_rules.json` 做正则匹配——不依赖用户消息、不依赖 Hermes hook、不依赖 embedding 索引。详见 [`references/force-mode-green.md`](references/force-mode-green.md)。

**边界：** 只测 A 层关键词。embedding 和 B 层仍需真实会话验证。当前 GREEN 5 场景全部被关键词覆盖，force 模式足够。

### 标准模式（需用户输入）

### 三档相关度评分（v2.2.1 · 2026-06-23 落地）

benchmark 评分从二进制（命中/不命中）升级为三档：精准(2分) > 相关(1分) > 不相关(0分)。

数据格式从 3-tuple `(cat, msg, expected)` 改为 4-tuple `(cat, msg, exact, acceptable)`：
- `exact`: 期望精准命中的 skill（2分）
- `acceptable`: 相关但不精准的 skill，推了也能用（1分）

**输出示例：**
```
相关度: 43/46 (93%)  |  精准 40 + 相关 3
分类: ✅ 设计 8/8  ✅ 调试 6/6  ⚠️ 学术 3/4
```

**为什么比旧二进制更真实：** 旧评分"文献综述→nature-writing"算 MISS（0分），实际用户拿到 nature-writing 也能写论文。新评分算相关（1分）——更接近用户真实感受。

**benchmark 用法：**
```bash
# 快速验证（纯 A 层，31s，零 LLM，任何用户可跑）
python3 ~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py --mode total --quick

# 全链路（含 gate LLM 调用，~180s）
python3 ~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py --mode total
```

**embedding 裸分 ≠ 含噪音评分。** embedding 的职责是信号召回，噪音是门控的活。

| 维度 | 测什么 | 当前 | 不该测什么 |
|------|-------|:--:|----------|
| embedding | 信号召回（零 token） | **71%** (20/28) | 噪音拦了多少 |
| 门控 | 噪音拦截 + 信号放行 | **78%** (噪音 19/20, 信号 16/30) | embedding 够不够好 |
| total | 全链路端到端 | — | 单层失败原因 |

**49.3 是伪低分。** 它把噪音指标也算给 embedding 了——20 条噪音 19 条被推荐了 skill，但这个不应该由 embedding 负责。剥离噪音后，embedding 的信号召回是 71%，对零 token 成本的纯向量搜索引擎来说不差。

### 三层漏斗职责划分（不可混淆）

```
门控: 噪音拦截 → "这条消息需要 skill 吗？" → NO 直接静默
embedding: 信号召回 → 语义相似度 → 召回可能相关的 skill
LLM: 语境决策 → embedding 候选 + keyword 候选 → 最终判断
```

门控 90% 噪音已拦截。漏过门控的噪音到 embedding 层会自动衰减（相似度不够高推不了什么），到 LLM 直接判 NO_NEED。**不要因为 embedding 评分难看就要求它做它不该做的事。**

### 坑点：Embedding 模型对比：bge vs qwen3 打成平手（2026-06-23 三轮实测）

**数据：** 15 条中文查询，各自建独立索引（公平对比，不跨模型查询）：
- bge-large-zh-v1.5 (本地 1024维): top-5=10/15 (66%)
- qwen3-embedding:0.6b (本地 1024维): top-5=10/15 (66%)
- Qwen3-Embedding-8B (硅基 4096维, 对称instruction): top-5=10/15 (66%)

三轮全部打成平手。Qwen3 强在论文/PPT（rank=1），弱在代码/调试（KeyError rank=151, SQL rank=220）。bge 相反。换模型不提升整体命中率——只是把错误换到不同场景。

**教训：** 维度翻 4 倍（1024→4096），本地换云端，命中率不变。embedding 不是 SSR 瓶颈——候选池覆盖才是（rank 72-84 的正确答案进不了 top-30）。真正提分在 A 层关键词补盲。

### 坑点：meta_detection 一刀切不如让管道自然静默（2026-06-23）

**症状：** AI 开启 meta_detection 用硬正则拦截 SSR 自指消息。用户纠正：「说不定测试真的需要呢？判成 YES 就去匹配，匹配不到就静默。不要硬塞不合适的 skill 推出来」。

**正确做法：** 不开 meta_detection。SSR 元对话 → 门控判 YES → embedding+B层 → 筛不到相关 → 自然静默。硬正则拦截是绕过问题，不是解决问题。管道已设计好这条路径。

### 坑点：Embedding 召回是信号瓶颈，不是 LLM（2026-06-23 实战确认）

**数据：** 15 条信号查询中 5 条未命中 top-5，其中 3 条正确答案 **不在 top-30 候选池**（暗色仪表盘 rank=72, ASCII猫咪 rank=84, Python重命名 rank=72）。LLM 只能从候选池中筛选——如果正确答案不在候选池，LLM 再强也筛不出来。

**结论：** 提升命中率的瓶颈在 embedding 召回，不在 LLM。B 层 LLM 筛查 prompt 优化只能减少滥推，不能增加召回。真正提信号命中率需要：① 更高维度 embedding 模型（4096维实测未做）② A 层关键词补盲区（rank 72→关键词命中直达 top-1）。

### 坑点：提改善方案前必须先扫描数据覆盖率（2026-06-23 实战）

**症状：** 讨论 SSR embedding 信号提升时，提出"方案 B：利用 skill 自带的 tag/category 元数据"，理由是"很多 skill 有 tag 字段，零成本高信号"。用户说「先扫再说」——扫描结果：401 个 skill 中 **3% 有 tag，1% 有 category，97% 什么都没有**。方案 B 当场死亡。

**根因：** 凭经验假设数据质量。看到几个知名 skill 有 tag 就推断"大部分都有"。实际 Hermes skill 生态中 tag/category 极少被填写。

**正确做法：**
1. 任何依赖"外部数据已存在"的优化方案，**做任何设计之前先扫描**
2. 扫描脚本很简单：读 embeddings.json 的 key → 遍历 SKILL.md frontmatter → 统计
3. 不扫就设计 = 在沙子上盖楼

**本会话数据：** [tag/category 覆盖率扫描](references/skill-metadata-coverage-20260623.md)

### 坑点：用户质疑时不要立刻转向——先站住脚再分析（2026-06-23 被批评）

**症状：** 先建议"改评分体系"，用户一问"需要改吗？"立刻缩回"不该改"；先说"方案A和B都好"，用户一逼"哪个好？"立刻摇摆选B。用户当场：「你一点主见都没有一质疑就变」。

**根因：** 把"听取用户反馈"理解成了"用户一开口就推翻自己"。用户质疑是让你解释和防守，不是让你投降。90% 的情况下用户质疑是为了逼你把分析做透，不是让你改结论。

**正确做法：**
1. 用户质疑 → 先确认质疑的具体点 → 解释原结论的理由 → 再判断是否需要调整
2. 如果原结论确实对，站住——「不改，理由：...」
3. 如果部分对，修正部分——「这个点你对了，那个点我坚持」
4. 禁止「都对」「都好」「都行」——给出明确选择并说明唯一理由

> 本条同时写入 CMG user memory。

### 坑点：meta_detection 关闭 → SSR 测试自身时 B 层噪音洪水（2026-06-23 实战）

**症状：** 用户说"测试ssr"，运行存活验证→embedding裸分49.3/门控67.0→一切正常。但 B 层日志 125 次命中，大量推 design/frontend/threejs skill 到 SSR 架构讨论中。A 层命中=0（关键词不覆盖元对话）。

**根因：** `meta_detection.enabled: False`。SSR 讨论自身时无法被零 token 正则拦截，全部流入 B 层 → LLM 盲猜产生噪音。不是 A 层的问题——元对话就该由 meta_detection 处理。

**修复：**
```bash
hermes config set ssr.meta_detection.enabled true
# 重启生效
```

**存活验证新增检查：** `grep -A3 'meta_detection:' config.yaml | head -5` → 必须显示 `enabled: true`。

## 门控 prompt 优化（2026-06-23 实战）

### 默认 prompt 的问题

默认 prompt `"Does this user message need an AI skill? Answer only YES or NO."` 太模糊，噪音拦截 95%（"今天天气怎么样"被误判 YES），信号放行 93%（"部署网站到Vercel"被误判 NO）。

### 优化 prompt（配置到 intent_gate.prompt）

```yaml
ssr:
  intent_gate:
    prompt: "Determine if this message needs a specialized AI skill (code, design, analysis, research, data processing, planning, deployment, debugging, writing, etc.).\n\nNeeds skill (YES): user wants a specific task done - building, creating, analyzing, fixing, searching, planning, computing, generating, deploying.\nNo skill needed (NO): pure conversation, chitchat, greetings, simple confirmations, emotional expressions, small talk.\n\nAnswer only YES or NO."
```

**实测效果（DeepSeek v4-pro，20噪音+15信号）：**
- 噪音拦截：95% → 100%（"今天天气怎么样"从误判YES→正确NO）
- 信号放行：93% → 93%（持平，"发微信"从YES→NO，但"部署Vercel"从NO→YES，扯平）

**写法原则：** 不绑定特定模型。用通用英语描述"什么算需要 skill""什么不算"，任何 LLM 都能理解。不硬编模型特有的 token 或参数。

### 坑点：不要硬编 prompt — 先测试再落地

**症状：** AI 编了一个自认为更好的 prompt 直接写进 config，用户当场纠正"又硬编了？"。

**正确做法：** ① 对比测试默认 vs 优化 prompt（至少 20 条噪音 + 15 条信号）② 数据说话 ③ 用户确认后落地。prompt 是配置项，从 config 读，不硬编码在代码里。详见 `references/gate-prompt-benchmark-20260623.md`。

### 坑点：B 层筛查 prompt 收紧 — "宁可漏推不可滥推"

**位置：** `__init__.py` L1252

**改动：**
```
旧：规则：只返回真正相关的。全不相关返回空数组。不要解释。
新：规则：宁可漏推不可滥推。不确定是否相关的技能一律不返回。全不相关返回空数组。不要解释。
```

"不确定就不推"比"真正相关"更明确，LLM 执行时更保守，减少滥推。

## Embedding 模型对比（2026-06-23 实测）

**方法：** 15 条中文查询，bge-large-zh-v1.5 (1024维) vs qwen3-embedding:0.6b (1024维)。各自建独立索引（公平对比，不跨模型查询）。

**结果：** top-5 命中率打成平手（bge 10/15=66%, qwen 10/15=66%）。bge 在代码/调试类更强（SQL优化 rank=2 vs qwen rank=260），qwen 在论文/PPT 类更精准（rank=1）。bge 体积 202MB，qwen 639MB，3 倍体积换相同准确率 → 不划算。

**结论：** embedding 模型不是 SSR 命中率的瓶颈。瓶颈在候选池覆盖（rank 72-84 的正确答案进不了 top-30）和 B 层 LLM 筛查精度。

**教训：** 不要无数据支撑说"XX维有天花板"——实测之前都是猜测。详见 `references/embedding-model-comparison-20260623.md`。

### 坑点：A 层命中=0 不一定是故障

SSR 元对话（"测试ssr""SSR怎么样"）不触发 A 层关键词是正常的——A 层规则不覆盖元对话场景。A 层命中=0 + B 层正常工作 ≠ SSR 坏了。

SSR/CMG/skill 系统自指消息（聊 SSR 架构、讨论匹配逻辑、CMG 活跃约束注入等）→ 零 token 正则直拦。

### 配置（config.yaml）

```yaml
ssr:
  meta_detection:
    enabled: true
    patterns:
      - ssr.*(优化|怎么样|能不能|推荐|加载|命中|匹配|好用|不行|问题)
      - 智配路由
      - (skill|插件|plugin).*(推荐|建议|命中|匹配|不工作|没触发)
      - (门控|gate|embedding|A层|B层|a_rules).*(怎么|如何|问题|异常|失败)
      - 三省引擎.*(激活|拦截|规则)
      - CMG.*(拦截|hook|规则|激活)
      - \[CMG 活跃约束\]
```

- 模式从 config 读取，不硬编码 → 用户可自行增减
- 安全阀：含任务意图动词（设计/写/生成/部署/画/做）→ 放行，不误拦
- 匹配用 `re.IGNORECASE`，大小写不敏感
- 位置：`_intent_gate()` 中，噪音白名单之后、LLM gate 之前

### 验证

```bash
# 查看当前元对话模式
python3 -c "import yaml; c=yaml.safe_load(open('$HOME/.hermes/config.yaml')); md=c.get('ssr',{}).get('meta_detection',{}); print(f'enabled={md.get(\"enabled\")}, patterns={len(md.get(\"patterns\",[]))}')"

# 发元对话消息后验证拦截日志
grep '元对话检测' ~/.hermes/logs/agent.log | tail -3
```

### 坑点：`测` 字太短 — 含"检测"的消息被误判为任务意图

`task_verbs` 正则中独立 `测` 匹配到"检测"中的"测" → 安全阀误开放。修复：`测`→`测试|测一下`。

## Gate prompt 配置化（v2.1 · 已落地）

`_call_llm_intent()` 从 `intent_gate.prompt` 读取 prompt，空则用默认英文。配置位置：

```yaml
ssr:
  intent_gate:
    prompt: ""   # 空=默认 "Does this user message need an AI skill? Answer only YES or NO."
```

**落地细节（2026-06-23）：**
- `_call_llm_intent(..., gate_prompt: str = "")` 新增参数，空 → 默认 prompt
- ollama 路径：`f"{prompt}\nMessage: {msg}\nAnswer:"`
- OpenAI/main 路径：`f"{prompt}\n\nMessage: \"{msg}\""` + system `"Answer only YES or NO."`
- 配置段在 `ssr.intent_gate.prompt`（非独立 `ssr.gate` 键，与 intent_gate 其他字段共存）

**⚠️ config.yaml 写保护：** Hermes 不允许直接 `patch`/`write_file` 修改 `~/.hermes/config.yaml`。只能用 `hermes config set` 或 `execute_code` 中 `yaml.dump()` 写。参见本 skill 头部坑点。

## 元对话检测（v2.1.1 已移除）

meta_detection 在 v2.1.1 中移除。年收益忽略不计（不到一分钱），代码复杂度远超价值。从 `__init__.py` / `dashboard.html` / `dashboard.py` / `config.yaml` 全部删除。元对话自然流入管道 → embedding 筛不到相关 → LLM 判 NO → 自然静默。不需要额外拦截层。

## ESR 回声规则

**SSR 推荐命中了 ≠ AI 展示了。** SSR 输出在 agent.log，不在对话中。AI 必须在收到 SSR 推荐后的**第一条回复中**展示推荐结果：

```
[SSR] 检测到任务需求，建议加载: brainstorming (DISCOVER) | ui-ux-pro-max (BUILD)
```

## 推荐数量控制

**v0.5.0 教训（2026-06-09）：「去上限」≠「不控量」。**

移除所有硬上限后，单条消息 A 层命中 30 个 skill——用户被淹没。根因：A 层 100 条正则规则中很多宽泛匹配（如 `写.*(代码|程序|功能|模块)` 匹配任何技术对话）。

**v0.5.1 修复（P0）：智能截断。**

新增 `max_total_recommendations` 配置（默认 12）。在 `_format_recommendation` 之前按质量排序截断：
- 非冷却 skill 优先
- 同优先级的按阶段分散
- 超过上限的丢弃（不折叠，直接截断）

```yaml
ssr:
  max_total_recommendations: 12  # 0=不限制
```

**原则：** 不限匹配层的产出数量，但展示层智能截断。匹配全跑（保留 B→A 升级数据），展示只推最相关的 12 个。

**用户偏好历史：** 用户三次纠正要求去上限；但去上限后实测 30 条淹没，用户问"是否为过度迭代"——信号是推太多而非推太少。P0 截断平衡了"不设限"和"不被淹"。

## 去上限全局分析（v0.5.0，2026-06-09）

用户要求去上限。**全局逐条审计后发现大部分"上限"实际上已不存在或不是人为限制：**

| 位置 | 旧值 | 当前 | 性质 | 处理 |
|------|------|------|------|------|
| A 层关键词 `break` | 5 | **已删除** | 合并架构下上限无意义 | 2026-06-09 删除 |
| A 层 embedding `[:30]` | — | 30 | 语义相似度质量过滤，非人为上限 | 不动 |
| B 层 ollama prompt | "3-8个" | "不限数量" | ✅ 已改 | — |
| B 层 openai/main prompt | "3-8个" | 不限（prompt 中无限量词） | ✅ 已改 | — |
| B 层 max_tokens | 200 | 500 | ✅ 已升 | — |
| prefilter candidates | 20 | 20（可配） | 输入优化，非上限 | `ssr.prefilter_candidates` |
| 展示折叠 | 12 | 12（可配） | 纯显示，不影响推荐 | `ssr.display_max` |

**翻来覆去改同一个点的根因：** 每次只改一处，没做全局审计。用户纠正后改为「逐条列出所有限制 → 分析每一条是上限还是质量过滤 → 做成可配项让用户选」。一次到位。

**可配项 config.yaml：**
```yaml
ssr:
  prefilter_candidates: 20       # B 层预过滤候选数（0=不过滤）
  display_max: 12                # 推荐展示折叠阈值（0=不折叠）
  max_total_recommendations: 12  # 推荐总数硬截断（0=不限制，v0.5.1+）
```

## B 层升级保护（v0.4.0）

**auto-gen 规则不覆盖 B 层升级的规则。** `_A_RULES.update(auto_gen)` 改为逐条检查：已有 key 的跳过，只补充新 key。

日志格式变更：`A 层规则: X (B 层升级: Y, auto-gen: +Z)`，明确区分来源。

**原因：** B 层升级规则来自真实使用验证（命中 3 次 → `_promote_to_a`），质量远高于 auto-gen 粗糙关键词。auto-gen 只做冷启动种子，主力是 B 层 → A 层升级循环。

## Phase 3：精准匹配升级（v0.5.x+ · 2026-06-09 实施）

Phase 3 在双阈值（similarity_floor + confidence_threshold）基础上新增四项增强。

### 3.1 Skill description 富化

`_get_skill_info()` 不再只取 YAML frontmatter 的一行 description。提取 SKILL.md 正文前 3 段散文（跳过表格行 `|...`、代码块、Markdown 标题、引用行 `>...`），追加到 description 尾部。无 YAML description 的 skill 直接用正文兜底。

**效果：** description 从平均 ~190 字符扩展到 ~450 字符（+135%），bge-m3 embedding 语义覆盖显著提升。

**验证：** 重启后 `embeddings.json` 全量重建，检查注册日志 `emb:` 字段 >0。

### 3.2 中文 query 扩展

`_expand_chinese_query()` — 14 域中英映射表。用户查询命中中文关键词时自动追加英文领域术语：

| 域 | 中文关键词示例 | 追加英文词 |
|----|-------------|-----------|
| 设计/UI | 设计、界面、仪表盘 | design, UI, interface, frontend, CSS |
| 调试 | 报错、KeyError、Traceback | debug, error, diagnose, fix |
| 金融 | 股票、均线、茅台 | finance, stock, trading, technical analysis |
| 论文 | 论文、学术、写作 | academic, paper, research, journal |
| ... | （共 14 域） | |

**位置：** `_match_a_layer()` embedding 路径中，`_embed(query)` 前调用。不影响关键词路径。

### 4.2 会话命中率日志

`_SESSION_STATS` 字典追踪每会话：calls / hits_a / hits_b / misses / skipped_low_conf。每 10 次调用自动输出结构化日志：

```
[ssr] 会话统计 | session=X | 调用=N | A层命中=N | B层命中=N | 无匹配=N | 低置信跳过=N | 命中率=XX%
```

### 4.1 Dashboard 监控面板

- **后端：** `dashboard.py` 新增 `GET /api/stats` 端点，返回 rules_count / embedding_count / total_hits_log / last_hit_rate / health
- **前端：** `dashboard.html` 新增 `loadStats()` 函数，4 格统计面板（活跃规则 / Embedding 索引 / 累计命中 / 命中率），颜色随命中率变化（绿>50% / 黄>25% / 红≤25%）
- **刷新：** 随 30s 自动刷新周期更新

### 升级安全评估

修改 SSR 前按风险分级（本 session 实例）：

| 档位 | 条件 | 实施内容 |
|------|------|---------|
| ✅ 零风险 | 纯增强/只加新功能 | 3.1 描述富化、3.2 中文增强、4.1 Dashboard、4.2 日志 |
| ⚠️ 需回归 | 改排序/匹配/会话行为 | 3.3 混合权重（已跳过，keyword-first 已足够） |
| ❌ 不能推 | 缺数据/高风险 | 4.3 误报降权、5.2 分阶段冷却、6.x 增量索引 |

**验证流程：** 改代码 → `cp` 备份 → `patch` → `python3 -m py_compile` 语法检查 → 删 `embeddings.json` → 重启 Hermes → 查注册日志 emb 字段 → 发测试消息 → 查命中率日志

> 详细架构见 `references/phase2-embedding-architecture.md`
>
> **准确率基准**：bge-large-zh-v1.5 1024维在关键词零命中场景下 ~63%（4 场景 2.5/4）。详见 [`references/bge-m3-embedding-accuracy.md`](references/bge-m3-embedding-accuracy.md)。对比 auto-gen 关键词 10%，6x 提升。

### 目标

用语义相似度替代 A 层 auto-gen 关键词（10% 准确率）。多后端设计，默认 Ollama 本地免费。

### 多后端设计

```yaml
ssr:
  embedding:
    provider: ollama          # 默认（本地免费，零依赖）
    model: bge-large-zh-v1.5  # 推荐：纯中文 202MB 1024维
    # provider: siliconflow   # 备选（bge-large-zh-v1.5，免费）
    # provider: openai        # 备选（text-embedding-3-small，付费）
```

- **ollama**（默认）：bge-large-zh-v1.5，202MB，1024 维纯中文，零 API key
- **siliconflow**：BAAI/bge-large-zh-v1.5，1024 维，免费，需 API key
- **openai**：text-embedding-3-small，付费

### nomic-embed-text 下载问题

`ollama pull nomic-embed-text` 可能因网络问题失败（TLS 握手超时 registry.ollama.ai）。

**hf-mirror 替代方案：**

```bash
# 1. 从 hf-mirror 下载 GGUF（~140MB，国内可通）
curl -L -o ~/nomic-embed-text.Q8_0.gguf \
  "https://hf-mirror.com/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q8_0.gguf"

# 2. 导入 Ollama
ollama create nomic-embed-text -f - <<'EOF'
FROM ~/nomic-embed-text.Q8_0.gguf
EOF

# 3. 验证
ollama list | grep nomic
```

### 关键发现：B 层已预过滤

当前代码 `_prefilter_skills`（`__init__.py` 第 540 行）已用关键词将 295 skill 预过滤到 top-20 再喂给 B 层 LLM。精度升级计划中 "294→30" 的 token 成本降低假设基于 294 全量——实际已是 20→N。

### 精度升级计划 vs 代码实际（2026-06-09 审计 · 2026-06-09 更新）

| 计划声称 | 代码实际 | 偏差 | 备注 |
|---------|---------|:--:|------|
| A 层去上限完成 | `len(result) >= 5: break` 两处仍在**关键词路径** | ✅ 已绕过 | embedding 路径走 top-30 语义粗筛，关键词路径是死代码 |
| B 层 prompt "不限数量" | 已改为"不限数量" | ✅ 已修正 | ollama 路径用 `_build_b_prompt`，openai/main 路径用硬编码 prompt |
| B 层 max_tokens 500 | 已改为 500 | ✅ 已修正 | main 路径 max_tokens=500 |
| 按阶段分组展示 | `_format_recommendation` 已实现分组 | ✅ 已完成 | DISCOVER/PLAN/BUILD/VERIFY 四阶段 |

**2026-06-09 更新：** 前次审计时 B 层 prompt 和 max_tokens 确实未改。本次会话中代码已更新。A 层 keyword 路径的 `break` 不需要改——embedding 路径自动绕过。

**结论：** Phase 1 去上限不能提升质量（A 层 auto-gen 只有 10% 准确率）。真正提升在 Phase 2——用 embedding 语义匹配替代关键词瞎碰。详见 `~/.hermes/plans/ssr/precision-upgrade/task_plan.md`。

## A 层匹配架构（v0.5.0+ · 2026-06-09 合并架构）

`_match_a_layer` 的双层匹配——**并行合并，不互相封堵**：

```
关键词精确匹配（2110条规则，零延迟）
  → 收集所有命中结果（不设上限）
Embedding 语义匹配（bge-large-zh-v1.5 1024维, top-30）
  → 补充关键词未覆盖的 skill
合并去重（关键词优先排前面，Embedding 补充排后面）
  → 有结果 → 返回
  → 无结果 → B 层兜底
```

**这是 2026-06-09 修复后的架构。** 修复前关键词命中后直接返回，Embedding 永远不跑——bge-m3 精度被浪费。修复后两条路径并行，关键词的精确命中 + Embedding 的语义覆盖互补。

**设计原则：** 精确规则和语义匹配是两把不同的刀——不该互相替换。关键词 cut 蔬菜，Embedding cut 肉。

诊断前必读数据格式——不用 skill_view 就猜 JSON 结构 = 两次报错结论（2026-06-13 实战）

**症状：** 用户问"新装 skill 在 SSR 里吗？"→ AI 用 `execute_code` 读 `embeddings.json` → 错误代码 `data.get('skills', {})` → 报"索引为 0"→ 实际 311 个 skill 全在。第二次读 `a_rules.json` 用 `a_data.get('rules', [])` → 报"规则为 0"→ 实际 100 条规则全在。

**根因：** 两次错误都是**凭经验猜 JSON 键名**，没先看数据结构。embeddings.json 是扁平 dict（`{name: {embedding: [...]}}`）；a_rules.json 的键直接是正则 pattern（`{"设计.*页面": {...}}`）。都没走 `skill_view` 读文档。

**正确做法：**
1. 检查任何 SSR 数据文件前，先 `skill_view('smart-skill-router')` 看数据结构说明
2. 或至少 `import json; d=json.load(f); print(type(d), list(d.keys())[:5])` 看实际格式
3. 数据文件存在≠读对了。`len(data)` 返回 0 不等于数据为空——可能是用了错误的访问键
4. 全量断言（"SSR 坏了""索引为空"）前必须先做最小验证：取一个已知 skill 名直接查

### 坑点：`added` 变量未初始化 → 插件加载崩溃（2026-06-09 修复）

**症状：** `auto_gen_rules: false` 时，Hermes 重启后插件加载失败：
```
WARNING hermes_cli.plugins: Failed to load plugin 'ssr': cannot access local variable 'added' where it is not associated with a value
```
A 层命中正常（关键词匹配），但 Embedding 索引构建和注册日志的最后一行被跳过。

**根因：** `added = 0` 在 `if _auto_gen_enabled():` 块内初始化（旧 ~1197 行）。`auto_gen_rules: false` 时走 `else` 分支，第 1228 行 `len(_A_RULES) - added` 引用未定义变量 → `UnboundLocalError`。

**修复：** 将 `added = 0` 移到 if/else 块之前：
```python
added = 0                          # ← 移到此处
if _auto_gen_enabled():            # 旧：added 在这一行下面
    auto_gen = _auto_gen_a_rules()
```

**预防：** 修改 `register()` 中任何变量后，必须在 `auto_gen_rules: true` 和 `false` 两种模式都做语法检查 + 模拟注册。可用 `python3 -m py_compile` 做基础验证。

### 坑点：`_cleanup_a_rules()` 淘汰不充分 + 插件崩溃前保存不生效（2026-06-09）

**症状：** a_rules.json 仍有 2110 条，期望清理到 100。插件日志只显示 3 条淘汰，但实际需要淘汰 2010 条。

**根因：** 两重问题叠加：
1. 清理逻辑本身正确（过期 + 按 hits 淘汰），但日志只显示最后几条淘汰，大量淘汰信息被省略
2. `_cleanup_a_rules()` 保存后插件继续执行 → 崩溃在 `added` 变量 → 保存的文件被后续操作覆盖或下一轮启动时重新加载旧数据

**手动清理（已验证可用）：**
```bash
cd ~/.hermes/plugins/ssr && python3 << 'PYEOF'
import json
with open("a_rules.json") as f:
    rules = json.load(f)
# 1. 过期淘汰（TTL 默认 30 天）
# 2. 按 hits 升序淘汰到 max_rules（默认 100）
sorted_rules = sorted(rules.items(), key=lambda x: x[1].get("hits", 0))
keep = max(100, len(rules))  # 实际：保留 hits 最高的 100 条
rules = dict(sorted_rules[-100:])
with open("a_rules.json", "w") as f:
    json.dump(rules, f, ensure_ascii=False, indent=2)
PYEOF
```

**验证清理结果：** `python3 -c "import json; print(len(json.load(open('~/.hermes/plugins/ssr/a_rules.json')))))"`

### 坑点：Hermes 完全重启时不要从 CLI 内杀进程（2026-06-09）

**症状：** 在 CLI 会话内执行 `kill <pid>` 杀所有 Hermes 进程（gateway、dashboard、agent）→ 当前 CLI 会话收到 signal 15（SIGTERM）被同时杀死。用户正在测试中被踢出会话。

**正确做法：**
1. 只杀 gateway + agent 进程，**保留当前 CLI 会话进程**
2. 识别当前会话: `echo $$` → 父进程链 → 不杀
3. 更安全：告诉用户「需要完全重启 Hermes，请手动执行 `hermes restart` 或杀掉进程后重启」，让用户在终端自己操作
4. 如果必须代劳：`kill <gateway_pid> <agent_pid>` — 不要 `killall hermes` 或盲目杀所有匹配进程

### 坑点：description 富化必须跳过表格/代码块/标题行（2026-06-09）

**症状：** `_get_skill_info` 正文提取 v1 将 markdown 表格行当作段落（`| 指标 | 用途 |` → `指标 用途`），对 bge-m3 embedding 无用。

**修复：** 跳过 `|` 开头（表格行）、` ``` ` 包裹（代码块）、`#` 开头（标题）、`>` 开头（引用）、`---` 分隔线。只收集散文段落（每行 ≥15 字符的非标记行聚合成段）。

**验证：** `technical-analysis` description 从 108→236 字符（21 行表格正确跳过），`tushare-finance` 173→475 字符（3 段散文 + 13 行表格跳过）。

### 坑点：中文 query 扩展必须覆盖技术错误名（2026-06-09）

**症状：** 第一版 `_expand_chinese_query` 调试域只有「报错/异常/不工作」等中文词，「KeyError」不匹配 → "这段代码一直报 KeyError" 无扩展。

**修复：** 追加 `KeyError, Traceback, TypeError, AttributeError, Exception, 崩溃` 到调试域。这些是 Python 用户最常见的错误名。

### 坑点：qwen3.5 思考模式占满 token — 门控永远拿不到答案（2026-06-22 实战）

**症状：** 门控测试 0/30 信号正确，全判 NO。`num_predict: 3` 被 `<think>` 标签吃光，永远到不了 YES/NO。`raw: true` 不能关闭思考（只跳过 Ollama 模板）。

**修复：** `think: False` 顶层参数。0.7s 出结果，无 `<think>` 输出。

```python
resp = requests.post(f"{OLLAMA_URL}/api/generate",
    json={"model": model, "prompt": prompt, "stream": False, "think": False},
    timeout=timeout)
```

详见 `references/local-model-gate-testing.md`。

### 坑点：本地模型大小不合可用内存 — swap 风暴致整机卡死（2026-06-22 实战）

**症状：** qwen3.5:9b (6.6GB) 在 8GB Mac 上，8 处 Hermes 组件同时引用 → 任何触发即加载 → swap I/O 炸到系统瘫痪。

**诊断：** `vm_stat | head -4` 算可用内存。`ollama ps` 看当前加载模型。

**修复：** 换 4b (3.4GB) + `think: false`。gate 测试超时从 5s→15s 防冷启动。

详见 `references/local-model-gate-testing.md`。

**症状：** Dashboard `/api/model-info` 显示 nomic-embed-text 为 "available" 而非 "installed"。`ollama list` 输出中模型名为 `nomic-embed-text:latest`，但 `model_scores.json` 的 key 是 `nomic-embed-text`（无 :latest）。子串匹配 `"nomic" in parts[0]` 能通过过滤，但后续 `name in installed_models` 精确匹配失败。

**根因：** `ollama list` 将模型名附加 `:latest` 标签，而配置/评分文件中的模型名不包含此后缀。

**修复：** 在 `get_model_info()` 中提取模型名时，先 `parts[0].replace(":latest", "")` 去掉后缀。

```python
# ❌ 旧：精确匹配失败
installed_models.append(parts[0])  # "nomic-embed-text:latest"
# name in installed_models → "nomic-embed-text" in ["nomic-embed-text:latest"] = False

# ✅ 新：去掉 :latest 再存
name = parts[0].replace(":latest", "")
installed_models.append(name)  # "nomic-embed-text"
```

**影响范围：** 任何通过 `ollama list` 解析模型名并与配置/评分文件匹配的代码。Dashboard `/api/model-info`、手动索引重建脚本、模型切换验证步骤。

### 坑点：execute_code 中 read_file() 会污染文件内容 —— 必须用 open().read()（2026-06-21 实战）

**症状：** 在 `execute_code` 中用 `from hermes_tools import read_file` 读取 `dashboard.html`，`result["content"]` 包含 `LINE_NUM|CONTENT` 格式的行号前缀。处理后 `write_file` 写回 → 行号前缀永久写入 HTML，且超大行被截断（`[...truncated]`）。同一 session 两次 execute_code 串行操作 → 文件被污染两次，`370|370|</div>` 遍布全文。

**根因：** `read_file` 是给 LLM 阅读用的工具（带行号前缀），不是给程序处理的管道。`open().read()` 才是纯文件内容。

**正确做法：**
```python
# ❌ execute_code 中禁用 read_file
result = read_file(path)
content = result["content"]  # 含 "370|370|" 行号！

# ✅ execute_code 中只允许 open().read()
with open(path) as f:
    content = f.read()        # 纯文件内容，无行号
```

**恢复：** 被污染后用 `re.sub(r'^\d+\|\d+\|', '', html, flags=re.MULTILINE)` 清洗。

**关联：** CMG 坑点 51。Dashboard 实战中两次 execute_code 串行 → 第一个用 read_file 读 → 写入污染版本 → 第二个再读 → 叠加污染。

**症状：** `dashboard.html` 是压缩单行（JS 全在一行），用 `patch` 改单处可行但多次累积风险高。新增 `loadStats()` 函数需要更大的代码块 → `patch` 受限。

**正确做法：** 大改 dashboard.html 时用 `read_file` 读取完整内容 → 在外部编辑器中重构 → `write_file` 一次性写入。小改（如加一个函数调用）可用 `patch`。

**症状：** 移除所有硬上限后，单条消息"分析现在情况，之后是否为过度迭代？"触发 30 条 A 层命中——关键词规则如 `写.*(代码|程序|功能)` 匹配对话中的技术讨论，宽泛规则全体开火。用户被推荐淹没，问"是否为过度迭代"。

**根因：** 「去上限」是展示层的决策——不让代码替用户筛选。「不设限」是正确的。但缺少配套的智能截断机制——匹配层产 30 条，展示层也全推 30 条。

**v0.5.1 修复（P0）：**
1. `_max_total_recommendations()` — 读取 `ssr.max_total_recommendations`（默认 12）
2. A 层 + B 层结果路径各加截断逻辑：非冷却优先 → 阶段分散 → top N
3. 匹配层继续全量跑（不影响 B→A 升级数据），展示层只推 top 12

**教训：** 「去上限」≠「不控量」。匹配自由，展示节制。用户三次纠正要去的上限，是代码替用户做筛选的判断——不是推荐总量的节制。这次反噬不是推太少，是推太多。

**症状：** 同一会话中，规则 `"学术论文|research|Related Work|..."` → 应产出 `research-paper-writing`，但 22:29:22 的 A 层命中日志中缺失。22:28:23 和简单 Python 复测均正常。

**根因：** `_match_a_layer()` 关键词→Embedding→合并去重三步中有竞态，合并阶段间歇性吞掉个别条目。

**检测：** 同会话连续 A 层命中对比——同一规则产出的技能不应变化。差异→合并去重 bug。结果详见 `references/2026-06-09-green-verification-results.md`。

### 坑点：关键词封堵 Embedding —— _match_a_layer 优先级倒置（2026-06-09 修复→合并架构）

**症状：** GREEN 测试 4「帮我写论文的 Related Work 部分」期望命中 `research-paper-writing`，但 A 层实际命中 `paper-spine-research`。两者功能等效——都是学术论文研究管线，但名称不同导致被计为 🟡 半命中。

**根因：** A 层关键词规则按精确 skill name 匹配。`research-paper-writing` 和 `paper-spine-research` 是两个不同的 skill name，尽管功能重叠。用户说「论文」时 A 层不知道这两个名称可以互相替代。

**正确做法：**
1. 在 A 层规则 `a_rules.json` 中加别名映射：`{"keywords": "论文写作|写论文|paper writing", "skills": ["research-paper-writing", "paper-spine-research"]}`
2. 不要假设单一 skill 能覆盖整个功能域——学术写作域至少有 3+ 个相关 skill
3. GREEN 验证中名称不精确但功能等效的命中 → 标注 🟡，同时建议补充别名规则

**长期方向：** Embedding 语义匹配天然解决此问题（「论文写作」和「paper spine」在向量空间相近）。但关键词路径的别名映射仍需手动维护。

## RED 反基准：降噪验证（v1.14+）

GREEN 基准只测「该推的必须推」——但 SSR 真正的问题是「不该推的也推了」。100% A 层命中率 = 每条消息必推，但 90% 不相关。需要 RED 反基准来验证降噪效果。

**RED 反基准（不该推的场景）：**

| # | 消息 | 不应推荐的 skill 类型 |
|---|------|----------------------|
| R1 | 讨论 SSR 本身（"SSR有优化空间吗"） | 金融、旅行、视频制作 |
| R2 | 讨论 CMG/规则系统 | 角色扮演、旅行、股票 |
| R3 | 确认性短回复（"对""好""记录好了"） | 任何 build 类 skill |
| R4 | 纯时间陈述（"8:15了"） | 任何 skill |
| R5 | 元对话（"memory 差多少满"） | 和元话题无关的领域 skill |

**验证流程：每次改动 → 跑 GREEN (5) + RED (5)**

| GREEN | RED | 判定 |
|:--:|:--:|------|
| 5/5 | 5/5 | ✅ 完美平衡 |
| ≥4/5 | 5/5 | ✅ 可用 |
| 5/5 | ≤3/5 | ⚠️ 砍过头 |
| ≤3/5 | 5/5 | ❌ 匹配退化 |

### 噪音诊断：A 层宽泛命中 vs Bug（v1.14 更新）

**100% 命中率不是 SSR 健康的标志——是噪音过多的标志。** A 层命中 30 条但 27 条无关 = SSR 在制造噪音，不是提供价值。健康的命中率应该是 40-60%（只在真正相关时推）。

**症状 vs 判定更新：**

| 现象 | 旧判定 | 新判定 | 动作 |
|------|:--:|:--:|------|
| A 层命中 30 条，大部分无关 | 🟢 设计特征 | 🟡 需降噪 | 检查 auto-gen 单英文词规则、embedding gate_threshold |
| A 层命中 0-3 条，全相关 | — | 🟢 健康 | 理想状态 |
| 同一 keyword 持续命中（无关话题） | 🟢 残留规则 | 🟡 待清理 | P0: 删单英文词 auto-gen 规则 |
| 命中率 100% | — | 🔴 噪音过多 | 必查：a_rules.json 单英文词 + embedding gate + 中文扩展误触发 |

### 坑点：100% A 层命中率 = SSR 永不休眠（v1.14+）

**症状：** 用户问"SSR全部通过？走基准测试了吗？"——AI 跑完三段式存活验证（注册日志+命中日志+Embedding 索引）后暗示"SSR 工作正常"，但从未执行 GREEN 5 场景基准测试。用户当场纠正。

**根因：** 存活验证的三个命令（grep 注册日志 / grep A 层命中 / grep embedding）只能证明 SSR 插件在运行并产出推荐。不能证明推荐准确。这是两个完全不同的验证维度——"活着" vs "推得准"。

**正确做法：**
1. 存活验证通过后，必须明确说"存活验证通过"，不能说"SSR 全部通过"
2. 匹配质量必须通过第三步 GREEN 基准（5 场景，≥3/5 通过）单独验证
3. 如果 GREEN 从未执行，必须如实报告"GREEN 基准测试未执行，准确率未知"
4. 禁止从注册日志推断准确率——auto-gen 准确率只有 10%，注册日志看不出

**区分表：**

| 验证项 | 命令 | 回答的问题 |
|-------|------|-----------|
| ① 存活 | `grep '插件注册完成' agent.log` | SSR 进程是否在运行？ |
| ② 命中 | `grep 'A 层命中' agent.log` | 是否有匹配产出？ |
| ③ 索引 | `python3 -c` 查 embeddings.json | Embedding 是否可用？ |
| ④ 质量 | GREEN 5 场景基准 | **推得准不准？** ← ①②③ 都回答不了这个 |


### 坑点：关键词封堵 Embedding —— _match_a_layer 优先级倒置（2026-06-09 修复→合并架构）

**症状（修复前）：** A 层有 2110 条精确关键词规则，但关键词命中后直接返回——Embedding 语义匹配永远不跑。bge-m3 精度被浪费。

**根因（`_match_a_layer` 修复前）：**

```python
# ❌ 修复前：关键词命中 → 返回（Embedding 被封死）
def _match_a_layer(user_message):
    keyword_result = _match_a_layer_keyword(user_message)
    if keyword_result:
        return keyword_result        # ← 这里封堵了 Embedding
    # ... embedding 语义兜底 —— 永不执行
```

**修复一（2026-06-09 第一次）：关键词优先 → Embedding 兜底。** 改后关键词未命中时 Embedding 能跑了——但关键词命中时 Embedding 仍然被封。

**修复二（2026-06-09 最终）：并行合并。** 两条路径都跑，合并去重，不互相封堵：

```python
# ✅ 修复后：并行合并
def _match_a_layer(user_message):
    keyword_result = _match_a_layer_keyword(user_message) or []
    emb_result = [...]  # Embedding top-30
    # 合并去重：关键词优先，Embedding 补充
    result = keyword_result + [e for e in emb_result if e["name"] not in seen]
```

**修复后基准：7/7 合并生效**（每条测试同时得到关键词+Embedding 结果）。

**设计原则：** 精确规则和语义匹配是两把不同的刀——不该互相替换。见 `smart-skill-router` SKILL.md 坑点 16。

### 坑点：/new 不等于重启——register() 不重新执行（2026-06-09 实战）

**症状：** 更新了 `__init__.py`（加了 Phase 2 embedding 代码），用户执行 `/new` 开新会话，期望 SSR 重新注册。但新会话里 SSR 零日志——没有注册、没有 A 层命中、没有错误。skill-autoload 和 cmg-guard 正常。

**根因：** `/new` 只创建新 conversation session，不重启 Hermes 进程。`register()` 在 Hermes 启动时执行一次，hook 此后持续生效。修改插件代码后 `/new` 不会触发 `register()` 重跑——必须重启 Hermes 进程。

**验证方法：**
```bash
# 检查 register() 最后执行时间
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# 对比 __init__.py 最后修改时间
ls -la ~/.hermes/plugins/ssr/__init__.py
# 如果 register() 时间 < 修改时间 → 代码更新了但未生效
```

**解决方案：**
1. 首选：重启 Hermes（`hermes restart` 或杀掉进程重启）
2. 备选（无需重启）：手动运行 register() 等价脚本构建索引，下次重启时 register() 自动加载磁盘上的索引文件

### 坑点：auto-gen 单英文词规则 — 100% 命中率的主要噪音来源（2026-06-13）\n\n**症状：** 日志显示 A 层命中率 40/40 = 100%。但实际推荐大多不相关——金融/旅行/角色扮演 skill 被推到\"检查SSR\"和\"讨论SSR设计\"的对话中。\n\n**根因：** a_rules.json 包含 40+ 条 auto-gen 生成的单英文词规则：\n\n```\nskill → canon-mnemonic-guard-dashboard (87 hit)\nwork  → writing-skills (83 hit)\nonly  → design-taste-frontend-v1 (81 hit)\ncall  → mcporter (81 hit)\nview  → canon-mnemonic-guard-dashboard (81 hit)\nera   → pixel-art (81 hit)\nother → xlsx (80 hit)\ntime  → xlsx (80 hit)\n... (共 40+ 条)\n```\n\n这些规则的特征：\n- pattern 是单个常见英文词（3-5 字符）\n- 只产生 1 个 skill（不是精准推荐，是\"碰上一个算一个\"）\n- hits 极高（80+）因为几乎每条消息都包含这些词\n- 产生的推荐和上下文完全无关\n\n**影响：** 这 40+ 条规则每条命中都贡献 1 个无关 skill → 加上 embedding 追加的 20-30 个 → 最终 12 个推荐里 8-10 个是噪音。用户感觉\"SSR 永远在推垃圾\"。\n\n**修复方向（P0）：** 删除所有单英文词 rule（pattern 不含中文、不含正则操作符、且只产出 1 个 skill）。保留中文关键词和精确英文短语（如 `\\\"debug|修复|报.*错\\\"`）。\n\n### 坑点：Embedding 永不休眠 — 每条消息必推 5 skill 噪音 100%（2026-06-21）

**症状：** Embedding 层即使面对噪音消息（"今天天气""谢谢""好的"）也永远返回 top-5 skill。每条非技术消息推 5 个无关 skill，噪音率 100%。

**实测数据（50 条中文，2026-06-21）：**
- 信号（39 条技术查询）：Embedding 命中 61%，综合 (A+E) 77%
- 噪音（12 条闲聊）：Embedding **100% 误推**，平均每条 5 个 skill

**根因：** Embedding 是搜索引擎，不是决策器。余弦相似度永远有 top-5 结果——即使是"今天天气怎么样"也有 sim 0.32~0.50 的 skill。

**修复方案（二选一）：**

**方案 A：A 层做门控（零成本）** — A 层零命中 → Embedding 静默。A 层用精确中文短语（30+ 规则），噪音 0。信号覆盖靠规则数量。

```python
def _recommend(msg):
    a = _match_a_layer(msg)
    if not a:
        return None  # 静默
    e = _match_embedding(msg)
    return merge(a, e)
```

**方案 B：B 层 LLM gate（¥0.0002/条）** — B 层判断是否需要 skill。max_tokens=200，prompt 极简。6/6 全对。

```
消息 → A 层（免费，0延迟）
       ├─ 命中 → Embedding
       └─ 未命中 → B 层 gate（¥0.0002，2s）
                    ├─ YES → Embedding
                    └─ NO → 静默
```

> 详见 `references/llm-gate-success.md`\n\n**症状：** 用户消息\"所有skill，包括刚装的都在ssr了吗？\"→ A 层关键词命中 smart-skill-router + ssr-operations（正确）→ Embedding 追加 tushare-finance、stock-screen-monitor、road-trip-planner 等 10+ 个（完全无关）。\n\n**根因：** `_match_a_layer` 的关键词和 Embedding 是 OR 关系，不是 AND 关系。关键词先匹配 → 收集结果 → Embedding 全量追加（只做去重，不做相关性过滤）。\n\n**代码位置：** `__init__.py` L594-646，`_match_a_layer`。关键词命中后 Embedding top-30 全部合并，只靠 `_similarity_floor`（默认 0.35）过滤，在 311 skill 密集向量空间中几乎不生效。\n\n**修复方向（P1）：** 关键词命中 > 0 时 → Embedding 只取 sim > 0.50 的候选作为补充；关键词命中 = 0 时 → Embedding 正常工作。\n\n### 坑点：auto-gen 规则声称 2081 条但 a_rules.json 只有 10 条（2026-06-09）

**症状：** 注册日志显示 `A 层规则: 2091 (B 层升级: 10, auto-gen: +2081)`，但 `a_rules.json` 只有 3,656 字节（10 条规则）。

**根因：** `_cleanup_a_rules()` 的 `max_rules=100` 上限淘汰 + `_save_a_rules` 可能被后续操作覆盖。大文件的 auto-gen 规则写入后，如果后续 `_flush_a_rules()` 触发了 cleanup，会把 auto-gen 全部淘汰（命中数=0），只保留 B 层升级规则（命中数≥3）。

**修复（手动重建）：**
```bash
cd ~/.hermes/plugins/ssr && python3 -c "
import sys, os; sys.path.insert(0, '.')
os.environ['HERMES_HOME'] = os.path.expanduser('~/.hermes')
import __init__ as ssr
if not ssr._SKILL_INDEX:
    ssr._SKILL_INDEX, ssr._BROKEN_SKILLS = ssr._build_skill_index()
existing = ssr._load_a_rules()
auto_gen = ssr._auto_gen_a_rules()
added = 0
for k, v in auto_gen.items():
    if k not in existing:
        existing[k] = v; added += 1
ssr._save_a_rules(existing)
print(f'合并: {len(existing)} 条 (B层升级 + {added} auto-gen)')
"
```

**长期修复方向：** `_auto_gen_a_rules` 生成的规则 initial hits=1（不是 0），避免被 cleanup 第一批淘汰。或 `_cleanup_a_rules` 在首次启动的 24h 内跳过 auto-gen 淘汰。

### 坑点：预置规则绑定本地 skill 集（v0.3.0 → v0.4.0 已修复）

**症状：** 从 282 个 skill description 生成 1214 条规则写死到 `a_rules.json`。别人装 SSR 时 skill 集不同 → 规则全部作废。用户纠正：「所有人都能用还是专属于我的？绑定 244 条 skill 不能缺斤少两」

**修复（v0.4.0）：** `_auto_gen_a_rules()` 在 `register()` 中每次启动时动态生成规则。`_A_RULES.update(auto_gen)` 合并已有规则+新增规则。`_save_a_rules()` 持久化供下次使用。规则集自动适配当前 skill 集，换机器/换 skill 都不需要手动维护规则文件。

**教训：** 任何从本地环境提取的数据（skill 列表、路径、配置）都不能写死为 JSON 分发——必须做成启动时动态扫描。

### 坑点：读 SSR 数据文件前不确认格式 → 假警报（2026-06-13 实战）

**症状：** 用 `json.load` 读取 `embeddings.json` 后用 `data.get('skills', {})` 读取 → 返回 0 skill。实际结构是扁平 dict（`{skill_name: {embedding: [...]}}`），不是 `{"skills": {...}}`。同理 `a_rules.json` 用 `a_data.get('rules', [])` → 返回 0 条规则。实际结构是 dict（key=pattern, value={skills, hits, ...}）。

**后果：** 错报「SSR embedding 索引为空」「A 层规则为 0」→ 多次工具调用排查一个不存在的问题 → 用户纠正。

**正确做法：**
```python
# ❌ 错：先假设结构再读
data = json.load(f)
skills = data.get('skills', {})  # 假设有 'skills' 键 → 空

# ✅ 对：先看结构再处理
data = json.load(f)
print(type(data), list(data.keys())[:3])  # 确认实际键名
# 然后按实际结构访问
```

**教训：** 操作任何 SSR 数据文件前，先 `skill_view('smart-skill-router')` 确认数据结构，或至少 `print(list(data.keys())[:5])` 看一眼再下结论。凭经验猜 JSON 键名是 SSR 诊断中最常见的误判来源。

### 坑点：删除 a_rules.json 不备份导致 B 层升级规则全部丢失（2026-06-09）

**症状：** 发现 a_rules.json 格式不兼容后直接 `rm` 清空，导致 B 层 3 次累积升级的 10+ 条高质量规则全部消失。

**正确做法：**
1. `cp a_rules.json a_rules.json.bak.$(date +%Y%m%d)` 永远先备份
2. 格式问题优先修复而非清空
3. 确认内容可恢复后再删原件

**扩展（v1.14+）：** 任何 SSR 状态变更（A 层清洗、版本升级、embedding 重建）前，备份三件套：
```bash
TS=$(date +%Y%m%d_%H%M)
cp a_rules.json a_rules.json.bak.$TS
cp embeddings.json embeddings.json.bak.$TS
cp __init__.py __init__.py.bak.$TS
```

### 坑点：auto-gen 规则注册日志声称 2081 条但 a_rules.json 实际只有 10 条（2026-06-09）

**症状：** 注册日志显示 `A 层规则: 2091 (B 层升级: 10, auto-gen: +2081)`，但 `a_rules.json` 只有 3,656 字节（10 条 B 层升级规则）。auto-gen 的 2081 条从未落盘。

**根因：** `_cleanup_a_rules()` 淘汰逻辑：超 `max_rules`（默认 100）时按命中数升序淘汰——auto-gen 规则 hits=0，第一批被清。2081 条入 → cleanup 秒删 1981 条 → 最终只剩 B 层升级规则（hits≥3）。

**检测：** `python3 -c "import json; r=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(len(r))"`  vs 注册日志声称数。

**修复：** 手动重建（见快速参考「手动重建索引」脚本）或重启 Hermes 触发 `register()` 重建。

### 坑点：config 模型名 ≠ 实际生效的模型 —— 四步验证必须全过（2026-06-21 实战）

**症状：** `config.yaml` 写 `nn200433/text2vec-bge-large-chinese`，但 embeddings.json 实际是旧 bge-m3 建的索引。register() 静默失败——模型在 Ollama 中崩溃（GGML 断言），索引构建被 try/except 吞掉，旧索引继续用。用户问「向量模型不是换成中文模型了吗」才发现切换从未生效。

**根因：** 做了 config 更新 + 删旧索引 + 重启三步，但缺少「新模型在 Ollama 中真的可用」的验证。text2vec 模型在 Ollama 中启动就崩——如果不先调 API 验证，删索引+重启只是把索引变空（register 静默失败），然后从备份恢复旧索引继续用 bge-m3。

**正确做法——切换 embedding 模型必须走完四步验证才能宣称「切换完成」：**

```bash
# ① 模型在 Ollama 中
ollama list | grep <模型名>
# ② API 直调可用（最关键！不等 register 静默吞错）
curl -s http://localhost:11434/api/embeddings \
  -d '{"model":"<模型名>","prompt":"test"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'embedding' in d else f'FAIL: {d}')"
# ③ config.yaml 一致
grep 'embedding:' -A 3 ~/.hermes/config.yaml | grep model
# ④ 删旧索引 + 重启 → 查注册日志 emb 字段 > 0
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
```

**不可用的模型记录：**
- `nn200433/text2vec-bge-large-chinese` — Ollama GGML 断言崩溃，不要用

**可用的中文模型（hf-mirror 快速安装）：**
- `bge-large-zh-v1.5` — CompendiumLabs q4_k_m, 202MB, 1024维纯中文, hf-mirror 14秒

### 坑点：Embedding 索引静默失败——register() 异常被 catch 但无显式告警（2026-06-09 发现 · 2026-06-12 确认生产环境零索引）

**症状：** Hermes 完整重启后，SSR 注册日志未提及 embedding 索引（缺少 `emb:` 字段），`embeddings.json` 文件为 0 skill（文件存在但内容为空对象 `{}`）。A 层 `a_rules.json` 同样为空（0 条规则）。bge-m3 Ollama 端点完全可用（1024 维），但 SSR 从未成功构建索引。

**⚠️ 2026-06-13 追记：`embeddings.json` 是扁平 dict（`{skill_name: {embedding: [...], ...}}`），不是 `{\"skills\": {...}}`。用 `data.get(\"skills\")` 读会返回 None → 误判为"索引为空"。a_rules.json 同理——扁平 dict，不是 `{\"rules\": [...]}`。正确验证方式：`len(data)` 而非 `len(data.get(\"skills\", {}))`。

**三重确认（2026-06-12 生产环境）：**

**后果：** A 层关键词匹配（零延迟精确命中）和 Embedding 语义匹配（bge-m3 1024维）全部失效。只剩 B 层 LLM 兜底，推荐质量从"关键词精确+语义覆盖+LLM兜底"三层漏斗退化为"LLM盲猜"，所有推荐跑偏（本会话全程见证）。

**根因：** `register()` 中 `_build_embedding_index()` 和 `_auto_gen_a_rules()` 调用被 try/except 包裹，异常只打 WARNING 不阻塞插件启动。如果构建中途任何瞬态错误（Ollama 超时、维度不匹配、config 为空），索引为空但仍标记插件已注册。此后 A 层和 Embedding 层永久失效直到下次重启。

**修复：**
```bash
# 删除空索引文件 + 重启 Hermes（完整重启，不是 /new）触发 register() 重建
rm ~/.hermes/plugins/ssr/embeddings.json ~/.hermes/plugins/ssr/a_rules.json
# 然后重启 Hermes，检查注册日志：
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# 预期：可用 skill: 296 | A 层规则: >0 | bge-m3: 296 emb
```

**预防：** 每次存活验证时，除三段式诊断外，必须检查 embeddings.json 和 a_rules.json 的实际内容——文件存在≠不为空。

**症状：** Hermes 完整重启后，SSR 注册日志只显示关键词规则数，未提及 embedding 索引（如 `emb: 0` 或缺少 `emb:` 字段）。`embeddings.json` 不存在。nomic-embed-text Ollama 端点完全可用（768 维），但 SSR 从未调用它构建索引。

**根因：** `register()` 中 `_build_embedding_index()` 调用被 try/except 包裹（line 1135-1149），异常只打 WARNING。如果构建中途 Ollama 超时或其他瞬态错误，索引为空但不阻塞插件启动。此后 `_match_a_layer()` 因 `_EMBEDDING_INDEX` 为空退化为关键词匹配——准确率从 embedding 的预期水平跌至 auto-gen 的 10%。

**正确做法：**
1. 每次存活验证时必查 `embeddings.json` 是否存在
2. 不存在 + nomic-embed-text 可用 → 重启 Hermes（完整重启，不是 /new）触发 register() 重建
3. 重启后检查注册日志是否含 `emb:` 字段及数值 >0
4. 如果多次重启仍无索引 → 手动调用 `_build_embedding_index()` 或检查 Ollama embedding API 延迟

### 坑点："重启"≠完整重启——register() 只跑一次，/new 不触发（2026-06-09 发现）

**症状：** 用户说"重启了，看看ssr"。AI 查当前会话日志无 SSR 注册，误判为"SSR 没加载"，花大量工具调用排查一个不存在的问题。实际上用户可能只是 `/new`（新会话），SSR hook 从上次 Hermes 启动时已注册并持续生效。

**根因：** `register()` 在 Hermes 进程启动时执行一次，后续 `/new` 不会重新调用。新会话中看不到"插件注册完成"日志是正常的——不是故障。

**正确做法：**
1. 先区分"完整重启"（gateway 新连接 + 注册日志）vs "/new"（无 gateway 日志）
2. `/new` 场景下：查上次注册日志确认插件已加载 → hook 持续生效即可
3. 真正需要验证的是 SSR 是否在**工作**（A 层/B 层命中），不是是否在**注册**
4. 用测试消息（如"帮我设计一个导航栏"）验证实际匹配效果，比翻日志更直接

### 坑点：独立 Python 脚本无法测试 SSR——hermes_cli 不可导入（2026-06-09 实战）

**症状：** 用 `python3 -c "import __init__ as ssr; ..."` 跑基准测试，`_embed()` 返回错误维度（如 bge-m3 配置为 1024维 却返回 768维）。`_match_a_layer()` 返回随机 skill（"茅台均线"→songwriting）。基准 0/5 或 2/5——看起来像 SSR 坏了。

**根因：** `_load_ssr_config()` 依赖 `from hermes_cli.config import load_config`。独立 Python 进程没有 hermes_cli → except 块返回 `cfg = {}` → 所有配置项取默认值（embedding model 默认 nomic-embed-text 768维）。索引由 Hermes 进程 build（bge-m3 1024维）→ 维度不匹配 → 余弦相似度随机。

**正确做法：**
1. **不要用独立 Python 脚本测 SSR 语义匹配。** 唯一正确方式：在 Hermes 会话中发送测试消息，查 agent.log 验证命中。
2. 如果必须验证 embedding 可用性 → 直调 Ollama API（`curl http://localhost:11434/api/embeddings`），不走 SSR 的 `_embed()`。
3. 判定方法：脚本中 `_embed_model()` 返回 `nomic-embed-text` 而非配置的模型名 → `_load_ssr_config()` 已降级。

**本会话教训：** 花 6 次工具调用排查 "SSR embedding 坏了"——实际只在独立脚本中坏，生产环境 bge-m3 1024维正常工作。详见 `references/2026-06-09-bge-m3-standalone-test-pitfall.md`。

### 坑点：precision-upgrade plan 声称的进度与代码实际不一致（2026-06-09 发现）

**症状：** plan 中 Phase 1 列了去上限改动（B 层 1-3→3-8、A 层 5→10），但 `__init__.py` 实测：A 层两处 `break` 仍在、B 层 prompt 仍是 "3-8 个"、max_tokens 仍是 200。Plan 的 progress.md 标 ✅ 的项实际未完成。

**根因：** plan 文件和代码独立维护，无自动验证机制。修改代码后 plan 的"已完成"标记靠人工更新，容易脑补。

**正确做法：** 分析任何 plan 的可行性前，必须逐条对照代码验证 plan 声称的改动是否真的存在。不可信 plan 文件的 ✅ 标记。

### 坑点：patch replace_all 在 Python 转义字符上会炸（2026-06-09 实战）

**症状：** 用 `replace_all: true` 替换 Python 源码中含 `\u300c`（Unicode 转义）的字符串时，替换结果多了层反斜杠——`\u300c` → `\\u300c`，Python 语法报错。

**根因：** `replace_all` 不区分 Python 字符串的转义语义。它在纯文本层匹配 `\u300c`，替换后新字符串中的反斜杠被追加转义。

**正确做法：**
1. Python 源码中涉及 `\uXXXX` 等转义序列的替换，**禁用 `replace_all`**
2. 每处用唯一上下文做单次 `patch`（不用 `replace_all`）
3. 如果多行需要改，用 `python3` 脚本直接操作，不用 patch 工具的 `replace_all`
4. 改完后立即 `python3 -m py_compile` 验证

**本会话教训：** 两处 openai/main 端点的 user message 改 "匹配 3-8 个技能" → "匹配技能"，第一遍用 `replace_all` 炸了，第二遍用唯一上下文单次 patch 成功。

**症状：** `ollama pull nomic-embed-text` → TLS handshake timeout 到 registry.ollama.ai。

**影响：** Phase 2（本地 Embedding 粗筛）完全无法推进。nomic-embed-text 是计划中唯一指定的 embedding 模型。

**替代方案：**
- 方案 A：挂代理拉取（274MB）
- 方案 B：国内镜像（hf-mirror.com 有 nomic-embed-text GGUF，需手动转换）
- 方案 C：SiliconFlow embedding API 替代（收费，但无网络问题）

**当前缓解：** B 层已有 `_prefilter_skills`（第 540 行）做关键词粗筛到 top-20，Phase 2 的"降低成本"声称被高估——实际上已经不把 294 个 skill 全送 LLM 了。

## 基准测试已知限制

### GREEN 验证（2026-06-09，合并架构 · 真实会话 · 2026-06-09 force 模式更新）

合并架构（关键词 || Embedding 并行）下的 5 场景验证：

| 模式 | 结果 | 方法 | 说明 |
|------|:--:|------|------|
| 真实会话 (06-09) | 4.5/5 | 用户逐条发送 → agent.log | 测试4 paper-spine≈research-paper 功能等效 |
| **Force 模式 (06-09 v2)** | **5/5** | execute_code regex 直接对 a_rules.json | 测试4 已修复：research-paper-writing 加入 A 层规则 |

详见 [`references/2026-06-09-green-verification.md`](references/2026-06-09-green-verification.md)。

| # | 消息 | 期望 | 实际 | |
|---|------|------|------|:--:|
| 1 | 响应式导航栏 | ui-ux-pro-max, popular-web-designs | 双命中 | ✅ |
| 2 | Python KeyError | diagnose | 命中 | ✅ |
| 3 | ASCII 猫咪 | ascii-art | 命中 | ✅ |
| 4 | 论文 Related Work | research-paper-writing | paper-spine-research | 🟡 |
| 5 | 茅台均线 | technical-analysis | technical-analysis + tushare-finance | ✅ |

**5 次全部 A 层关键词命中，Embedding 和 B 层未介入。** Force 模式 5/5 全通过——测试4 `research-paper-writing` 已加入 A 层规则，不再依赖 `paper-spine-research` 功能等效。

### autogen 基准（2026-06-09，纯 A 层关键词 · 无 Embedding · 已过时）

**核心教训：A 层 auto-gen 不能独立工作。** description 语言与用户自然语言不匹配（如 "茅台股票" vs `tushare-finance`）、高频词噪音、中文词提取粗糙。正确模式是 **A 层快速精确路径 + B 层 LLM 语义兜底**。

### 测试 2：子串匹配漏网

测试消息「这段 Python 代码报 KeyError 帮我看看」不命中 A 层规则 `debug|修复|报错|bug|异常|不工作|调试`。

**根因：** "报 KeyError" 中 "报" 和 "错" 被空格+英文隔开，`报错` 作为子串不匹配。这是 A 层子串匹配的固有局限——A 层负责快速精确命中，表达变形由 B 层语义兜底。

**判定标准修正：** 测试 2 的 A 层不命中不算 SSR 故障。A 层目标 4/5 即通过。如果 B 层可用且能命中测试 2，则双层协同正常。

**可选的 A 层规则增强（降噪）：**

```json
"debug|修复|报错|报.*错|bug|异常|不工作|调试|KeyError|Traceback|Exception|出错|错误": {
    "skills": [...]
}
```

但需注意：`报.*错` 正则会匹配所有含「报」和「错」的语句，误报风险高。**建议保持当前子串匹配，依赖 B 层兜底。** 除非 A 层命中率显著低于 80%。

### 测试报告中处理 B 层 warmup 噪音

agent.log 中 `B 层 Ollama 调用失败（降级跳过）` 是 warmup 代码遗留（坑点 43），不代表 B 层实际状态。测试报告必须区分：

- **B 层真实状态**：看 `grep -A 10 'b_layer:' config.yaml` 的 provider + API 直连测试
- **日志噪音**：忽略 "Ollama 调用失败"——这是 `__init__.py` 硬编码预热路径的输出

报告格式：先验证 provider → 再 API 直连 → 最后在结论中标注日志噪音已忽略。

### 坑点：JSON 数据结构验证先于查询（2026-06-13 实战）

**症状：** 检查 SSR 索引时，用 `data.get('skills', {})` 读取 embeddings.json → 返回空 → 误报"SSR 索引为空"。实际数据结构是扁平 dict `{skill_name: vector}`，不是 `{"skills": {...}}`。同类错误重复两次——第二次读 a_rules.json 时用 `data.get('rules', [])` 同样返回空。

**根因：** 凭经验假设 JSON 结构，不先 `print(list(data.keys())[:5])` 看一眼。

**正确做法：**
```python
import json
with open('embeddings.json') as f:
    data = json.load(f)
# 先看结构，再查数据
print(type(data).__name__, len(data))
if isinstance(data, dict):
    print("Sample keys:", list(data.keys())[:3])
```

**教训：** 任何 JSON 文件，读完后第一件事是检查顶层结构和键名。不要假设 `data['skills']`、`data['rules']` 等固定键存在。

## 格式迁移审计（v2.0.0+ 升级后必做）

v2.0.0 将 A 层规则从硬编码 skill 名迁移为 `keywords` 动态匹配。每次格式升级后必须全量 grep 审计，防止以下漂移。

### 审计四步

```bash
cd ~/.hermes/plugins/ssr

# ① 版本号一致性 —— 所有文件必须与 plugin.yaml 一致
CANONICAL_VERSION=$(python3 -c "import yaml; print(yaml.safe_load(open('plugin.yaml'))['version'])")
echo "规范版本: $CANONICAL_VERSION"
grep -rn 'v[0-9]\.[0-9]' *.py *.yaml *.md 2>/dev/null | grep -v '.bak\|__pycache__' | grep -v 'CHANGELOG\|README'
# ⚠️ CHANGELOG.md 和 README.md 含历史版本号，排除——只检查活跃源码文件
# 每个不匹配项都需修正

# ② 格式残留 —— a_rules.json 中不能有旧格式 (skills[{name, phase}])
python3 -c "
import json
with open('a_rules.json') as f: rules = json.load(f)
old = sum(1 for v in rules.values() if isinstance(v,dict) and 'skills' in v)
new = sum(1 for v in rules.values() if isinstance(v,dict) and 'keywords' in v)
print(f'Total: {len(rules)}, Old(skills): {old}, New(keywords): {new}')
if old:
    for k,v in rules.items():
        if isinstance(v,dict) and 'skills' in v: print(f'  OLD: {k[:80]}')
"

# ③ 死引用 —— 旧格式中引用的 skill 是否还存在
python3 << 'PYEOF'
import json, os
with open('a_rules.json') as f: rules = json.load(f)
names = set()
for v in rules.values():
    if isinstance(v,dict) and 'skills' in v:
        for s in v['skills']:
            if isinstance(s,dict) and 'name' in s: names.add(s['name'])
for name in sorted(names):
    found = os.system(f"find ~/.hermes/skills -name SKILL.md -exec grep -l '^name: {name}$' {{}} \; 2>/dev/null | head -1 | grep -q .")
    print(f'  {name}: {"EXISTS" if found == 0 else "DEAD"}')
PYEOF

# ④ CMG 文档同步 —— CMG SKILL.md 中 SSR 版本引用是否滞后
grep -n 'SSR v[0-9]' ~/.hermes/skills/software-development/canon-mnemonic-guard/SKILL.md
```

### 坑点：格式迁移后版本号全盘漂移（2026-06-23 v2.0.0 实战）

**症状：** plugin.yaml 升到 v2.0.0，但 `__init__.py` 头部 v0.7.0、行内注释 v0.6.5/v0.7.0/v1.5.2、dashboard.py v0.3.0、test_ssr.py v1.0、README badge v1.6.0。7 处不一致。

**根因：** 版本号散布在 plugin.yaml / `__init__.py` 开头 docstring / 行内注释 / dashboard.py / test_ssr.py / README.md badge / CHANGELOG.md 标题。升级时只改了 plugin.yaml，其余全部滞后。

**正确做法：** 每次版本号变更后，执行审计四步的 ① — `grep -rn 'v[0-9]\.[0-9]'`，逐条对比 plugin.yaml 规范版本号，不一致立刻修正。

**本会话修复清单：**
| 文件 | 行 | 旧值 | 新值 |
|------|-----|------|------|
| __init__.py | 2 | v0.7.0 | v2.0.0 |
| __init__.py | 9 | v0.6.5 | v2.0.0 |
| __init__.py | 1487 | v0.7.0 | v2.0.0 |
| __init__.py | 1851 | v1.5.2 | v2.0.0 |
| README.md badge | 9 | v1.6.0 | v2.0.0 |
| dashboard.py | 2 | v0.3.0 | v2.0.0 |
| test_ssr.py | 3,460 | v1.0 | v2.0.0 |

### 坑点：LLM 富化嵌入描述（Domains/Triggers 标签后缀）降分 30 个百分点（2026-06-23 实测）

**症状：** 自认为「嵌入描述太短=召回不够」，用 LLM 对每个 skill 生成 Domains/Triggers 中英混合标签后缀→嵌入 85%→55%，反降 30%。30 条中文信号查询 top-5 命中从 17/20 掉到 11/20。

**根因：** bge 1024 维对短文本更敏感。加标签后缀稀释了核心语义——「analyzes stock market technical indicators」精准命中「均线走势」，加「Domains: technical analysis, stock trading. Triggers: 均线, K线, ...」后向量泛化。

**正确做法：**
1. 嵌入富化是伪需求——当前 85% 信号召回已够用
2. 嵌入评分 49.3 是被噪音指标拖的——嵌入只管信号召回，噪音交给门控
3. 97% 的 skill 没有 tag/category——不改外部 skill 的元数据方案不可行
4. 真正提分点在：① gate prompt 信号判定 ② A 层关键词补盲区 ③ 自循环学习(用户习惯追踪→偏好 boost)

### 自循环学习方向（v2.1 目标）

不改外部 skill。三层信号：
- 用户采纳推荐 → +1 置信度
- 用户手动加载（不用推荐用别的）→ 此场景应加此 skill
- 用户忽略 → -1 置信度

> 详见 plan: `~/.hermes/plans/ssr/master-status.md` 第五章

## v1.8.0 架构定论：关键词是死路，LLM 做主决策 ← 已过时

**2026-06-21 用户定论：** 「关键词只是个样子。反复改关键词也没有多大意义。因为他没有智慧——优化这个词有时候被推荐是正确的，有时候就是错误的。跟词没关系，要真实理解语境。」

**2026-06-22 v2.0.0 收敛架构（本会话实测确认·关键词解耦）：**

```
消息
 ↓
噪音白名单(9条正则, 0 token)
 ↓ 未命中
embedding语义匹配(bge, 0 token)
 ↓
LLM判断+匹配(DeepSeek v4-pro, 1次调用)
 ├── need_skill: false → 直接出
 └── need_skill: true → 推荐技能
```

**关键变化：** 去掉了意图门控独立LLM调用（embedding已是零成本门控）。去掉了LLM筛查单独过滤（LLM一次搞定判断+匹配）。A层108条规则从硬编码skill名解耦为keywords运行时匹配。

**准确率：** 51条极限测试 80%，12条测试 92%，噪音 9/9 完美拦截。纯LLM方案 54%，LLM+emb 85-92%。

详见 `~/.hermes/plans/ssr/master-status.md`。

### ✅ 降噪已执行

**方案：** 手动清洗 a_rules.json（非代码过滤）。理由：代码过滤只能删单英文词，手动清洗可同时去掉 paper-spine/huashu-nuwa/perspective 等非单字噪声。

**结果：**
```
61→6 条全手动规则
56 条 auto-gen 单字噪声清零
work→writing-skills 误报消失
GREEN 基准: 5/5 全通过（A层 4/5 + B层兜底 1/5）
备份: a_rules.json.bak (9.5KB)
```

```

## SSR 推荐位置控制（position fix · v0.6.3+）

SSR v0.6.3 支持 `position` 配置项，控制推荐注入位置：

| 值 | 行为 |
|----|------|
| `append` (默认) | 推荐追加到回复末尾（长回复可能被截断） |
| `prepend` | 推荐前置到回复开头（`post_llm_call` hook 注入） |

### 配置方法

```bash
hermes config set ssr.position prepend
```

### 验证三步

```bash
# ① 确认 config.yaml 有 position: prepend
grep 'position:' ~/.hermes/config.yaml

# ② 确认 plugin.yaml 声明了 post_llm_call hook
grep 'post_llm_call' ~/.hermes/plugins/ssr/plugin.yaml

# ③ 确认 __init__.py 通过语法检查
python3 -c "compile(open('$HOME/.hermes/plugins/ssr/__init__.py').read(), '__init__.py', 'exec'); print('OK')"
```

**⚠️ 配置后必须重启 Hermes（完整重启，非 /new）。** `register()` 只在进程启动时执行一次。

### 坑点：位置修复代码已写但插件加载崩溃

代码（`_post_llm_call` hook + `_ssr_position()`）已实现，但若插件因语法错误加载失败 → 位置修复不生效。先 `grep 'Failed to load plugin.*ssr' ~/.hermes/logs/agent.log | tail -1` 确认无加载错误。

### 坑点：`_ssr_position()` 插入到模块 docstring 内部导致 SyntaxError（2026-06-20 实战）

**症状：** 用户手动将 `_ssr_position()` 函数插入 `__init__.py` 顶部，恰好落在模块 docstring 的 `"""`...`"""` 之间。Python 把函数定义当作文档字符串内容，后续的裸文字变成非法语句 → 整个插件无法加载。

**检测：**
```bash
python3 -c "compile(open('$HOME/.hermes/plugins/ssr/__init__.py').read(), '__init__.py', 'exec')" 2>&1
```

**修复：** 函数必须放在模块 docstring 闭合 `"""` 之后、所有 `from __future__` import 之后、`_load_ssr_config()` 定义之后（因为函数体内调用了它）。安全位置：常量区（`A_RULES_PATH`）和配置区之间。

**⚠️ `from __future__ import annotations` 必须是文件第一条实际语句。** 任何代码（含函数定义）放在 `from __future__` 之前都会报 `SyntaxError: from __future__ imports must occur at the beginning of the file`。

### 坑点：全角标点（`：` `（）`）在 Python 源码中的风险（2026-06-20 实战）

**症状：** docstring 中含全角冒号 `：` (U+FF1A) 和全角括号 `（）` → Python 3.12 在某些编码条件下报 `SyntaxError: invalid character '：' (U+FF1A)`。

**修复：** docstring 和注释中用半角标点（`:` `()`）。全角标点只用于面向用户的消息字符串。代码（含 docstring）→ 半角。

### 坑点：Embedding 富化反效果 — 不要用 LLM 扩写 skill 描述（2026-06-23 实测）

**测试：** 对 28 个 skill 用 DeepSeek 生成 Domains+Triggers+中英描述后缀 → embedding 信号召回从 **85% 跌至 55%**（20 条查询）。

**根因：** bge 1024 维对短文本更敏感。加 Domains/Triggers 后缀把向量推向泛化方向——原来一句"analyzes stock market indicators"精准命中"茅台均线"，加了标签后缀反而不准。

**教训：** 基础单句 description 就是最好的 embedding 文本。不要画蛇添足。

### 坑点：SILENT 前缀是障眼法 — `display:false` 直接 return None（2026-06-23 修复）

**旧行为：** `[SSR:SILENT]` 前缀注入推荐文本。Hermes 不认识这个标签，推荐照样进上下文。

**新行为：** `display: false` → `return None`。完全不注入推荐。

```bash
# ── v2.1.1 存活检查（含 meta_detection）──
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# 期望：emb: N (N>0), A层: N+0

# ── meta_detection 必查 ──
grep -A3 'meta_detection:' ~/.hermes/config.yaml | head -5
# 期望：enabled: true。false → B层噪音洪水

# ── 架构路径确认 ──
grep 'B 层命中\|LLM 筛查: 语境无关\|独立匹配' ~/.hermes/logs/agent.log | tail -5

# ── v3 规则验证 ──
python3 -c "import json; r=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(f'{len(r)} rules, v3={\"keywords\" in list(r.values())[0]}')"
# 期望：108 rules, v3=True

# ── Embedding 索引验证 ──

# ── 区分重启 vs /new ──
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1   # register() 最后执行时间
ls -la ~/.hermes/plugins/ssr/__init__.py                  # 代码最后修改时间
# 如果 register() 时间 < 修改时间 → 代码更新了但未重启 Hermes

# ── Embedding 索引验证（v0.5.0+）──
python3 -c "import json; d=json.load(open('$HOME/.hermes/plugins/ssr/embeddings.json')); print(f'{len(d)} skill' if d else '无索引，需重建')"

# ── B 层配置 ──
grep -A 8 'b_layer:' ~/.hermes/config.yaml

# ── Embedding 配置（v0.5.0+）──
grep -A 5 'embedding:' ~/.hermes/config.yaml

# ── 可配项（v0.5.1+）──
grep 'prefilter_candidates\|display_max\|max_total_recommendations' ~/.hermes/config.yaml

# ── Phase 3 验证（v1.13.0+）──
# 描述富化效果
grep 'embedding 增量\|embedding 索引构建' ~/.hermes/logs/agent.log | tail -1
# 命中率统计
grep '会话统计' ~/.hermes/logs/agent.log | tail -3
# Dashboard 统计 API
curl -s http://localhost:8766/api/stats | python3 -m json.tool
# Dashboard 模型诊断 API（v1.6.0+）
curl -s http://localhost:8766/api/model-info | python3 -m json.tool
# Dashboard 一键基准测试（Phase 4）
curl -s -X POST http://localhost:8766/api/benchmark | python3 -m json.tool
# 中文扩展测试（在 Hermes 会话中发送"帮我设计一个暗色仪表盘"→ 查日志）

# ── 去上限分析 ──
# 详见 SKILL.md "去上限全局分析"章节

# ── a_rules.json 恢复（空覆盖后）──
# 详见 smart-skill-router skill 的 references/a_rules-recovery.md
ls -lt ~/.hermes/plugins/ssr/a_rules.json.bak* | head -3
cp ~/.hermes/plugins/ssr/a_rules.json.bak ~/.hermes/plugins/ssr/a_rules.json

# ── 计划文件 ──
cat ~/.hermes/plans/ssr/precision-upgrade/task_plan.md

# ── 插件源码 ──
wc -l ~/.hermes/plugins/ssr/__init__.py
```

### 手动重建索引（无需重启 Hermes）

代码更新后 Hermes 未重启 → `register()` 未重新执行 → 索引文件不存在。手动构建：

```bash
cd ~/.hermes/plugins/ssr && python3 -c "
import sys, os, logging, time
sys.path.insert(0, '.')
os.environ['HERMES_HOME'] = os.path.expanduser('~/.hermes')
logging.basicConfig(level=logging.INFO, format='%(message)s')
import __init__ as ssr
# Skill 索引
ssr._SKILL_INDEX, ssr._BROKEN_SKILLS = ssr._build_skill_index()
print(f'Skills: {len(ssr._SKILL_INDEX)}')
# Embedding 索引（~20s，246 次 API 调用）
start = time.time()
emb = ssr._build_embedding_index()
print(f'Embedding: {len(emb)} skill, {os.path.getsize(ssr.SSR_DIR / \"embeddings.json\"):,} bytes, {time.time()-start:.1f}s')
# A 层规则（合并 B 层升级 + auto-gen）
existing = ssr._load_a_rules()
auto_gen = ssr._auto_gen_a_rules()
added = sum(1 for k, v in auto_gen.items() if k not in existing)
for k, v in auto_gen.items():
    if k not in existing: existing[k] = v
ssr._save_a_rules(existing)
print(f'A层规则: {len(existing)} (B层升级 + {added} auto-gen), {os.path.getsize(ssr.SSR_DIR / \"a_rules.json\"):,} bytes')
"
```

磁盘文件就绪后，重启 Hermes 时 `register()` 会直接加载已有文件（跳过全量构建，只做增量同步），接近零等待。

**⚠️ 如果 `_build_embedding_index()` 全部返回 404：** 用 curl + subprocess 绕过（本 session 验证：388 skill · 20s · 零错误）：

```bash
cd ~/.hermes/plugins/ssr && python3 << 'PYEOF'
import json, subprocess, numpy as np, time, os

with open('embeddings.json.bak.06211808') as f:
    old = json.load(f)

def emb(text):
    r = subprocess.run(['curl','-s','--max-time','30',
        'http://localhost:11434/api/embeddings',
        '-d', json.dumps({'model':'bge-large-zh-v1.5','prompt':text})],
        capture_output=True, text=True, timeout=35)
    return np.array(json.loads(r.stdout)['embedding'])

new = {}
for name in old:
    desc = old[name].get('description', name)
    new[name] = {'embedding': emb(str(desc)).tolist(), 'model': 'bge-large-zh-v1.5'}

with open('embeddings.json','w') as f:
    json.dump(new, f, ensure_ascii=False)
print(f'{len(new)} skill, {os.path.getsize("embeddings.json"):,} bytes')
PYEOF
```

### 坑点：echo bug — f-string `\\n` 字面量导致 skill 名不显示（2026-06-14 确认根因+修复 v0.6.3）

**症状：** B 层命中时用户看到 `[SSR] 建议加载:\n` —— skill 名完全不显示，`\n` 是字面量反斜杠-n。

**根因：** `__init__.py` L1424-1427，Python 字符串转义错误：

```python
# ❌ "\\n" = 两个字面字符（反斜杠+n），不是换行
body = "\\n".join(lines)           # L1424
return f"{prefix}\\\n{body}"       # L1427
```

Python 中 `"\\n"` 是两个字面字符，`"\n"` 才是换行。f-string 同理——`\\n` = 字面量。

**修复（v0.6.3）：**
```python
# ✅ "\n" = 实际换行
body = "\n".join(lines)
return f"{prefix}\n{body}"
```

3 行改动（L1424/1426/1427），归入 v0.6.3 Task 1（P0）。

### 坑点：修改 SSR 插件代码必须委 Reasonix(acp)（2026-06-14 两次被纠正）

**症状：** v0.6.3 迭代中，4 次裸 `patch` 直接改 `__init__.py`，被用户两次追问「又手动patch？又不用reasonix？」。

**根因：** CMG 规则要求「改 skill/plugin 须委 Reasonix(acp)，禁裸 patch/write_file」。但这条规则不在 SSR 运维 skill 里——AI 做 SSR 改动时加载的是 `ssr-operations`，看不到 CMG memory 里的规则。

**正确做法：**
```
delegate_task 委 Reasonix(acp)，goal 描述改动 + context 给精确行号
```

**例外：** 纯机械替换（echo bug 的 `\\n→\n`、版本号字符串）可先向用户说明「机械替换，不用 Reasonix 可以吗？」，允许后再动手。不问就动手 = 违规。

**教训：** CMG 规则跨 skill 不可见 → 必须落到每个相关 skill 的坑点里。

### 坑点：plugin.yaml 版本号滞后 3 个大版本（2026-06-14 发现）

**症状：** `__init__.py` 头部标 v0.6.2，但 `plugin.yaml` 的 `version:` 字段仍为 `0.3.0`。plugin.yaml 是 Hermes 识别插件版本的权威来源，0.3.0 = 发布系统对版本的认知完全错误。

**修复：** 发布前 `grep version plugin.yaml` 确认与 `__init__.py` 一致。每次版本号变更必须改两个文件——`__init__.py` 头部注释 + `plugin.yaml` version 字段。

### 坑点：SSR 状态变更后 plan 文件数字漂移（2026-06-14 实战）

**症状：** A 层 100→6、embedding 246→370 后，3 个 precision-upgrade plan 文件仍有旧数字。master-status.md 版本号未同步。

**根因：** plan 文件里硬编码了 A 层规则数、embedding 索引数、版本号——SSR 状态变化后这些数字不会自动更新。

**正确做法：** 每次 SSR 状态变更（A 层清洗、版本升级、embedding 重建）后：
```bash
# 1. 找出所有过时数字
grep -rn 'A 层.*[0-9]\\+ 条\\|100 手动\\|246 skill\\|296 skill\\|emb=296\\|rules=100' ~/.hermes/plans/ssr/

# 2. 对比实际状态
python3 -c "import json; r=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); e=json.load(open('$HOME/.hermes/plugins/ssr/embeddings.json')); print(f'A层:{len(r)} emb:{len(e)}')"

# 3. 逐个修正 + 更新 master-status.md 基线表
```

**常见漂移点：** precision-upgrade 三件套（task_plan/findings/progress）含最多硬编码数字。smart-skill-router 和 noise-reduction 的 plan 较少过期。

## 噪音诊断：A 层宽泛命中 vs Bug

SSR 推荐了与当前话题无关的 skill → 不一定是故障。先判定：

| 现象 | 判定 | 动作 |
|------|:--:|------|
| A 层命中 10-30 条，大部分无关 | 🟢 设计特征 | A 层关键词宽泛匹配 |
| 100% 命中率 | 🟡 设计缺陷 | 每条消息都产生推荐 = 噪声率极高，非健康状态（2026-06-13 实测 40/40 命中） |
| 同一关键词持续命中同一组 skill（无关话题） | 🟢 残留规则 | A 层规则积累的历史关键词 |
| A 层命中 0 且 B 层超时 | 🔴 故障 | SSR 形同虚设 |

**A 层噪音不需修复** — 这是关键词匹配的代价。噪音无害——AI 看到建议后自行判断是否相关，不相关的忽略。B 层（embedding 语义）才是精准层。

**信号判断**：用户说"SSR 建议和当前任务毫无关系" → 确认 A 层噪音设计特征，不需修。用户说"SSR 完全没推荐" → 查存活验证三步。

### ⚠️ 2026-06-13 生产环境发现：100% 命中率 = 全噪音

**生产状态（2026-06-13 验证）**：311 skill · 100 A层正则 · bge-m3 311 emb · B层 main · 会话 40/40 命中率 100%。

**但是**——整个会话中 SSR 推荐几乎全部跑偏：
- 聊 CMG → 推金融（tushare-finance, stock-screen-monitor）
- 检查 SSR bug → 推视频制作（code-to-video, manim-video）
- 讨论 nature skills → 推感情分析（tong-jincheng-perspective, relationship-conflict）
- 聊 Clypra 视频编辑器 → 推 facefusion + ai-short-film-production（方向勉强对但按关键词泛推）

**根因不是 bug——是 SSR 架构性矛盾：** A 层 100 条正则用宽泛关键词做到了不漏（100% 命中），但代价是每一条消息都命中多条规则。"debug|修复|报错" 命中任何含 bug 的对话，"设计.*页面|UI|界面" 命中任何含设计关键词的消息。100% 命中率 = SSR 永远不会闭嘴。

**正确预期管理：SSR 的推荐不应该被当作"建议"——应该被当作"可能有用的提示，大概率无关"。AI 看到 [SSR] 推荐后必须自行判断相关性，不相关就直接跳过。用户看到 AI 展示的 [SSR] 行时，应该预期 80% 是不相关的。

## 升级安全评估三档

修改 SSR 前，按风险分级：

| 档位 | 条件 | 本 session 实例 |
|------|------|---------------|
| ✅ 零风险可推 | 纯增强/只加新功能/不改匹配逻辑 | 3.1 描述富化、3.2 中文增强、4.1 Dashboard、4.2 日志 |
| ⚠️ 需回归 | 改排序/匹配/会话行为 | 3.3 混合权重、5.1 任务切换冷却 |
| ❌ 不能推 | 缺数据/高风险/依赖外部不稳定 | 4.3 误报降权、5.2 分阶段冷却、6.x 增量索引 |

**每次修改后验证**：`grep '插件注册完成' agent.log | tail -1` 确认 emb/A层规则数 >0 → 发一条测试消息 → `grep 'A 层命中' agent.log | tail -3` 确认仍在匹配。

## 参考

- [SSR 噪声模式与升级路线](references/ssr-noise-patterns-and-upgrades.md) — 2026-07-22：embedding 噪声（nature-citation+storage-analyzer 误绑）+ 升级路径全景（auto_gen_rules / embedding swap / threshold / reranker / feedback loop）
- [local-model-gate-testing.md](references/local-model-gate-testing.md) — qwen3.5 门控：think:false 参数 + 模型大小 vs 可用内存（2026-06-22）
- [standalone-ssr-import.md](references/standalone-ssr-import.md) — 独立导入 SSR plugin 用于 benchmark：_CONFIG_CACHE 预填充（2026-06-22）
- [signal-noise-test-20260621.md](references/signal-noise-test-20260621.md) — v1.7.0 10信号+5噪音实测：金融4/4·学术7/8精准，设计自驾D档弱（2026-06-21）
- [format-migration-audit.md](references/format-migration-audit.md) — v2.0.0 格式迁移后全量 grep 审计清单（版本号/格式残留/死引用/CMG同步，2026-06-23）
- [v2.1-upgrade-20260623.md](references/v2.1-upgrade-20260623.md) — v2.0→v2.1 升级实录：版本号同步清单 + 三项功能实现 + config 新增段（2026-06-23）
- [ssr-audit-v2.2.0.md](references/ssr-audit-v2.2.0.md) — v2.2.0 全量 grep 审计：7项发现 + 8项检查清单 + 2个诊断陷阱（2026-07-04）
- [ssr-v2.2.0-audit-20260704.md](references/ssr-v2.2.0-audit-20260704.md) — v2.2.0 审计续篇：元对话正则盲区修复 + 极短噪音 stealth 拦截日志 + benchmark 120s超时诊断 + 审计命令模板（2026-07-04）
- [noise-gate-plan.md](references/noise-gate-plan.md) — B 层门控噪音治理：2026-06-21 50条中文基准(77%综合), Embedding裸奔噪音100%, 方案: B层YES/NO做主门控
- [llm-gate-success.md](references/llm-gate-success.md) — B 层 LLM gate 成功方案：max_tokens=200，6/6 全对，¥0.0002/条（2026-06-21）
- [llm-gate-failure.md](references/llm-gate-failure.md) — LLM gate 失败：DeepSeek/qwen3.5 reasoning 吃光 max_tokens，content 永远为空。改 A 层正则门控
- [hook-registered-but-not-fired.md](references/hook-registered-but-not-fired.md) — SSR Hook 注册成功但未触发：完整重启后 session 零日志的诊断流程（2026-06-14）
- [silent-miss-path.md](references/silent-miss-path.md) — SSR 假性沉默：A 层 0 规则 + B 层 miss → 零日志（代码缺陷：miss 路径无 logger）（2026-06-14）
- [2026-06-09-v0.5.0-code-changes.md](references/2026-06-09-v0.5.0-code-changes.md) — v0.5.0
- [auto-gen-architecture.md](references/auto-gen-architecture.md) — v0.4.0 动态规则生成架构
- [2026-06-09-code-changes.md](references/2026-06-09-code-changes.md) — 去上限/auto-gen保护/B层prompt优化全部代码改动
- [2026-06-09-plan-feasibility-analysis.md](references/2026-06-09-plan-feasibility-analysis.md) — precision-upgrade plan 可行性分析（plan vs 代码对照、Phase 2 网络阻塞、假设误差）
- [2026-06-09-bge-m3-standalone-test-pitfall.md](references/2026-06-09-bge-m3-standalone-test-pitfall.md) — bge-m3 独立脚本测试误报：hermes_cli 不可导入致维度不匹配
- [chinese-embedding-benchmark.md](references/chinese-embedding-benchmark.md) — bge-large-zh-v1.5 50条中文查询基准（Top-5: 46%, Top-10: 68%, 2026-06-21）
- [6-rule-green-baseline-2026-06-14.md](references/6-rule-green-baseline-2026-06-14.md) — 降噪后 6 规则 GREEN 基准：5/5 全通过（2026-06-14）
- [embedding-model-benchmark-20260621.md](references/embedding-model-benchmark-20260621.md) — bge-m3 vs bge-large-zh-v1.5 中文 20 条基准：60% vs 55%（2026-06-21）
- [embedding-model-comparison-20260623.md](references/embedding-model-comparison-20260623.md) — bge vs qwen3-embedding:0.6b 15条逐条对比：持平 66%（2026-06-23）
- [post-restart-checklist.md](references/post-restart-checklist.md) — 重启后三步验证（echo bug → A 层 → GREEN）+ 备份+plan更新（2026-06-14）
- [multi-embedding](~/.hermes/plans/ssr/multi-embedding/task_plan.md) — 多语言 Embedding 模型支持 + Dashboard 诊断面板计划（2026-06-21）
- [master-status.md](~/.hermes/plans/ssr/master-status.md) — SSR 总状态追踪 + v2.2 路线图 + 设计原则 + 发布清单
- [calibrate_floor.py](~/.hermes/plugins/ssr/tests/calibrate_floor.py) — 无极阈值校准脚本：实测 embedding 分布 → 写入 calibrated_floor
- [model_scores.json](~/.hermes/plugins/ssr/model_scores.json) — 4 模型评分数据 + 校准字段，Dashboard 读取

### 坑点：config 写的是模型 A，embeddings.json 实际是模型 B 建的（2026-06-21 实战）

### 坑点：config 写的模型 ≠ embedding 索引实际用的模型（2026-06-21 实战）

**症状：** `config.yaml` 写 `qwen3-embedding`，Ollama 里也有，但 embeddings.json 索引是 1024 维且 `model: ?`（旧 bge-m3 建的）。用户问「换了新模型效果怎样」才发现从未生效。

**根因：** 只改了 config + 重启，但旧索引文件（`embeddings.json`）仍在磁盘。`register()` 优先加载已有文件，不重建。

**正确做法——切换 embedding 模型四步验证（缺一不可）：**
```bash
# ① 模型在 Ollama 中
ollama list | grep <模型名>
# ② API 直调可用（不等 register 静默吞错）
curl -s --max-time 15 http://localhost:11434/api/embeddings \
  -d '{"model":"<模型名>","prompt":"test"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'embedding' in d else f'FAIL: {d}')"
# ③ config.yaml 一致
grep 'embedding:' -A 3 ~/.hermes/config.yaml | grep model
# ④ 删旧索引 + 手动重建
cp embeddings.json embeddings.json.bak.$(date +%m%d%H%M)
rm embeddings.json
# 用 curl 手动重建（SSR 内部 httpx 可能 404，curl 始终可用）
python3 references/curl-rebuild-embedding.py
```

**⚠️ 模型大小警告：** 8GB Mac 上 qwen3-embedding (4.7GB) 和 qwen3.5:9b (6.6GB) 同时加载会触发 swap 风暴（单次会话 200GB+ swap I/O，load 涨到 14-19，14 进程卡死）。推荐 bge-large-zh-v1.5 (202MB)，中文基准 20 查询 Embedding 75% 准确率。详见 `references/chinese-benchmark.md`。
```

**不可用模型记录：** `nn200433/text2vec-bge-large-chinese` — Ollama GGML 断言崩溃。

### 坑点：GREEN 基准 5 个场景不够——中文匹配需要 30+ 场景才看得出模型差距（2026-06-21 实战）

**症状：** AI 声称「1024 维 bge-m3 和 4096 维 qwen3-embedding 对 SSR 匹配质量差别很小」，理由是两个模型在 GREEN 5 场景下都能命中。用户当场纠正：
1. 5 个场景太少了——两个模型都能过 5/5 不等于没差距
2. bge-m3 是多语言模型不是中文模型，qwen3-embedding 是中文优化
3. 需要 30+ 条真实中文查询做排名对比（top-5 命中率、平均排名位置），不是 5 条 pass/fail

**正确做法：**
1. GREEN 5 是快速冒烟测试（≥3/5 = SSR 在运行），不是模型质量评估
2. 模型对比需要 ≥30 条中文查询覆盖设计/调试/金融/旅行/学术/办公/地图/社交等域
3. 对测方法：两个模型各建一份索引 → 每条查询对两个索引各算 top-5 → 比较命中率和平均排名
4. 有数据再下结论——禁止凭模型规格（维数/大小/是否中文优化）推测匹配质量

**症状：** 卸载 headroom（本地代理，监听 localhost:8787）后，SSR B 层仍报 `500 Internal Server Error for url 'http://localhost:8787/v1/chat/completions'`。模型直连已恢复（`base_url: https://api.deepseek.com/v1`），但 B 层继续打旧代理地址。

**根因：** SSR B 层 `provider: main` 复用 Hermes 主模型的 `base_url`。如果代理工具安装时改了 `model.base_url`，卸载后只恢复了主 `base_url`，B 层可能缓存旧值或 `_load_ssr_config()` 读取了过期配置。

**正确做法——卸载任何代理/中转工具后的四步验证：**

```bash
# ① 确认主模型 base_url 已恢复
grep 'base_url:' ~/.hermes/config.yaml | head -1
# 期望: https://api.deepseek.com/v1（非 localhost 类地址）

# ② 确认 B 层配置
grep -A 8 'b_layer:' ~/.hermes/config.yaml
# 如果 b_layer.base_url 写死了代理地址 → 清掉

# ③ 重启 Hermes（完整重启，非 /new）

# ④ 验证 B 层连通——发一条会触发 B 层的消息，检查日志
grep 'B 层' ~/.hermes/logs/agent.log | tail -3
# 不应出现 localhost:8787 或代理地址
```

### 坑点：`_match_b_main()` 读不到 api_key —— config 嵌套 key 盲区（2026-06-21 实战）

**症状：** B 层 provider=main，日志报 `Illegal header value b'Bearer '`（空 key）。config.yaml 的 `model.curator.api_key` 有值，但 B 层请求的 `Authorization: Bearer ` 后面是空的。

**根因：** `_match_b_main()` 两处路径（读 config.yaml + hermes_cli）都只读 `model_cfg.get("api_key", "")`。但 config.yaml 里 `api_key` 不在顶层 `model:`，而是嵌套在 `model.curator.api_key` 和 `model.triage_specifier.api_key`。`model.api_key` 不存在 → 返回空字符串 → `Bearer ` 后无内容 → `Illegal header value`。

**修复（v0.6.6）：**

```python
api_key = model_cfg.get("api_key", "")
# api_key 可能在子节点（curator / triage_specifier 等）
if not api_key:
    for sub_key in ("curator", "triage_specifier", "title_generation"):
        sub = model_cfg.get(sub_key, {})
        if isinstance(sub, dict) and sub.get("api_key"):
            api_key = sub["api_key"]
            break
```

两处路径都要加此回退逻辑。

**预防：** 任何从 config.yaml 读凭据的代码，不能假设 key 在顶层。Hermes config 的 `model.api_key` 通常为空，真实 key 在子配置中。检查命令：
```bash
grep -E 'api_key:|model:' ~/.hermes/config.yaml | head -5
# model.api_key 不存在 ≠ 没 key。检查 curator/triage_specifier 子节点。
```

### 坑点：Embedding 模型对测必须分阶段运行——单次 execute_code 必超时（2026-06-21 实战）

**症状：** 40 skill × 30 query × 2 模型 = 140+ Ollama embedding 调用，单次 execute_code 300s 超时。缩减到 15×15 仍超时。每次调用 qwen3-embedding (4.7GB) 需 3-5s。

**正确做法：**
1. **分阶段运行** — 索引构建和查询测试必须在不同的 execute_code 调用中完成，索引结果持久化到文件
2. **优先选轻量模型** — bge-large-zh-v1.5 (202MB) 每次调用 <1s，qwen3-embedding (4.7GB) 每次 3-5s
3. **先用 curl 测单次延迟** — `time curl ...` 确认模型加载状态后再跑批量
4. **分模型分别测试** — bge 和 qwen3 的索引构建分开跑，各把结果存 JSON，第三步再加载对比

### 坑点：config 写的模型 ≠ embedding 索引实际用的模型（2026-06-21 实战）

**症状：** `config.yaml` 写 `qwen3-embedding`，Ollama 里也有，但 embeddings.json 索引是 1024 维且 `model: ?`（旧 bge-m3 建的）。用户问「换了新模型效果怎样」才发现从未生效。

**根因：** 只改了 config + 重启，但旧索引文件（`embeddings.json`）仍在磁盘。`register()` 优先加载已有文件，不重建。

**正确做法——切换 embedding 模型四步验证（缺一不可）：**
```bash
# ① 模型在 Ollama 中
ollama list | grep <模型名>
# ② API 直调可用（不等 register 静默吞错）
curl -s --max-time 15 http://localhost:11434/api/embeddings \
  -d '{"model":"<模型名>","prompt":"test"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'embedding' in d else f'FAIL: {d}')"
# ③ config.yaml 一致
grep 'embedding:' -A 3 ~/.hermes/config.yaml | grep model
# ④ 删旧索引 + 手动重建
cp embeddings.json embeddings.json.bak.$(date +%m%d%H%M)
rm embeddings.json
# 用 curl 手动重建（SSR 内部 httpx 可能 404，curl 始终可用）
python3 references/curl-rebuild-embedding.py
```

**⚠️ 模型大小警告：** 8GB Mac 上 qwen3-embedding (4.7GB) 和 qwen3.5:9b (6.6GB) 同时加载会触发 swap 风暴（单次会话 200GB+ swap I/O，load 涨到 14-19，14 进程卡死）。推荐 bge-large-zh-v1.5 (202MB)，中文基准 20 查询 Embedding 75% 准确率。详见 `references/chinese-benchmark.md`。

| 模型 | 大小 | 维度 | 中文质量 | 延迟 | 推荐 |
|------|------|:--:|:--:|:--:|:--:|
| **bge-large-zh-v1.5** | 202MB | 1024 | ★★★★★ 纯中文 | <1s | ✅ **首选** |
| qwen3-embedding | 4.7GB | 4096 | ★★★★★ 中文原生 | 3-5s | ⚠️ 重 |
| bge-m3 | 437MB | 1024 | ★★★★ 多语言 | ~1s | 备选 |

> bge-large-zh-v1.5 体积是 qwen3-embedding 的 1/24，维度是 1/4，但 SSR skill 匹配场景（~400 skill）下差异可忽略。优先用轻量模型。

**症状（第一层）：** 卸载 headroom 后，SSR B 层仍报 `500 Internal Server Error for url 'http://localhost:8787/v1/chat/completions'`。主 `base_url` 已恢复 `api.deepseek.com`，B 层 `base_url: ''`（空），provider=main 应自动继承主 URL，却仍打代理地址。

**症状（第二层）：** 第一层修完后（基于本 session 更早的修复），新错误出现——`Illegal header value b'Bearer '`。表面看像 key 丢失，实际是 `_match_b_main()` 读 `model.api_key` 不存在，而 key 在 `model.curator.api_key`。

**根因：** 卸载代理工具需要**同时修复两个配置维度**：
1. `model.base_url` — 主模型直连地址（已恢复 ✓）
2. SSR `_match_b_main()` 的 api_key 提取逻辑 — 只读 `model.api_key` 顶层字段（未修复 ✗）

**正确做法——卸载任何代理/中转工具后的完整验证：**

```bash
# ① 确认主模型 base_url 已恢复
grep 'base_url:' ~/.hermes/config.yaml | head -1

# ② 确认 B 层配置（无代理残留 URL）
grep -A 8 'b_layer:' ~/.hermes/config.yaml

# ③ 验证 B 层实际使用的 URL —— 通过代理日志
grep 'B 层.*chat/completions' ~/.hermes/logs/agent.log | tail -3
# 不应出现 localhost 或代理地址

# ④ 验证 API key 提取 —— 检查 Bearer 头
grep 'B 层' ~/.hermes/logs/agent.log | tail -3
# 不应出现 "Illegal header" 或 "Bearer "（空）
```

### 坑点：Dashboard /api/stats 用 subprocess grep 阻塞服务器（2026-06-21 实战）
### 坑点：Dashboard /api/stats 用 subprocess grep 阻塞服务器（2026-06-21 实战）

**症状：** Dashboard 页面完全空白。`/api/stats` 请求超时（10s+）。`curl http://localhost:8766/api/stats` 无响应。但 `/api/rules` 和 `/api/model-info` 正常。

**根因：** `_get_stats()` 函数每次请求调用 `subprocess.run(["grep", "-c", "ssr.*命中", agent_log])` 扫描 2.7MB/15K 行 agent.log。`BaseHTTPRequestHandler` 是单线程——一个请求的 grep 阻塞，后续所有请求排队等待。subprocess timeout=3s 应能兜底，但 grep 在 2.7MB 文件上可能触发 kernel IO 锁，大于 timeout 仍不返回。

**修复：** 去掉 subprocess grep，stats 只返回静态数据（rules_count + embedding_count + health）。命中率数据改为仅在 model-info 面板中展示。

```python
# ❌ 旧：每次请求 grep agent.log
result = subprocess.run(["grep", "-c", "ssr.*命中", str(log_path)], ...)
stats["total_hits_log"] = int(result.stdout.strip() or 0)

# ✅ 新：直读数据文件，零阻塞
stats["total_hits_log"] = -1
stats["last_hit_rate"] = 0
```

**预防：** Dashboard API 端点禁止任何 subprocess/网络调用——只读本地 JSON/YAML 文件。DNS、Ollama API、grep 全部走 `/api/model-info`（独立的非 stats 端点，阻塞影响可控）。

**关联：** 如果 Dashboard 仍然空白但 API 返回正常 → JS 被 `read_file` 行号污染 → 见 [`references/dashboard-js-validation.md`](references/dashboard-js-validation.md) 的两步诊断（`node --check` + 行号清洗）。

### 坑点：JS forEach 中变量名重复覆盖外层作用域（2026-06-21 实战）

**症状：** Dashboard 模型面板的「推荐场景」行显示 CSS class 名（如 `m-status-active`）而非场景描述文字（如 `Best for Chinese users`）。

**根因：** `renderModelPanel` 函数中 `sc` 变量被两次使用：外层存 `d.scenario_en`（场景文字），内层 `forEach` 回调用 `sc` 存 CSS class（`m-status-active`）。JS 的 `var` 声明不限定块作用域——内层赋值覆盖外层值。

```javascript
// ❌ 旧：sc 被内外两层复用
var sc = d.scenario_en || "";
// ... later in forEach:
(d.models||[]).forEach(function(m){
    var cls=..., sc=m.status==="active"?"m-status-active":...;  // ← 覆盖外层 sc！
    s+='<span class="m-status '+sc+'">';  // sc 现在是 CSS class，不是场景文字
});
s+='<div class="model-scenario">'+t("model-scenario")+": "+sc+'</div>';  // sc 已变质

// ✅ 新：内层改名 stc
(d.models||[]).forEach(function(m){
    var cls=..., stc=m.status==="active"?"m-status-active":...;  // 不同名
    s+='<span class="m-status '+stc+'">';
});
```

**预防：** JS 中嵌套 forEach/循环时，每个变量检查是否与外层重名。`var` 无块作用域 → 重名即覆盖。外层用 `let` 可避免（块作用域保护），但 dashboard.html 全用 `var` 保持 ES5 兼容。
