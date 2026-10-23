# SSR 多语言 Embedding 支持 + Dashboard 模型诊断面板

> 创建: 2026-06-21 | 更新: 2026-06-21 (Phase 1+2 完成, Phase 4 plan) | 状态: ✅ Phase 1+2 已实现，Phase 3+4 待定

## 背景

当前 SSR 强制使用单一 embedding 模型（`bge-large-zh-v1.5`，纯中文）。虽然面向中文用户推荐是合理的默认值，但硬编码限制了：
1. **英文用户无法获得匹配质量** — 纯中文模型对英文 query 的语义区分度差
2. **无法展示模型能力** — 用户不知道当前模型强在哪、弱在哪
3. **切换模型无验证** — 改了 config 不知道新模型实际效果如何

**不暴露隐私** — Dashboard 面板只展示模型能力维度评分，不展示用户本地 skill 集、命中数据等个人信息。

## 目标

### Phase 1: 多模型可配置 + SKILL.md 推荐指南
- SKILL.md 列出 3 种推荐模型（中文/英文/多语言），附安装命令
- 用户 `hermes config set ssr.embedding.model <model>` 自由切换
- 切换后 `rm embeddings.json` + 重启 Hermes 自动重建

### Phase 2: Dashboard 模型诊断面板
- 新增 `/api/model-info` 端点 → 返回当前模型元数据 + 评分
- 前端渲染模型诊断卡片：维度、大小、中英文评分、综合评分、推荐场景
- 支持模型列表对比（已安装 vs 可安装）

### Phase 3 (未来): 双模型自动路由
- `_detect_language()` 检测用户输入语言
- 中文 → zh 模型，英文 → en 模型
- 索引文件分存 `embeddings_zh.json` + `embeddings_en.json`
- 仅当双模型都已安装时启用

## 设计决策

### 模型评分体系

不在代码里硬编码评分——评分数据存为 JSON 配置文件，Dashobard 读取展示。用户可自维护：

```json
// ~/.hermes/plugins/ssr/model_scores.json
{
  "bge-large-zh-v1.5": {
    "dimension": 1024,
    "size_mb": 202,
    "chinese_score": 5,
    "english_score": 2,
    "overall": 4,
    "scenario": "中文用户首选",
    "training_languages": ["zh"],
    "install_cmd": "curl ... | ollama create ..."
  },
  "bge-large-en-v1.5": {
    "dimension": 1024,
    "size_mb": 219,
    "chinese_score": 2,
    "english_score": 5,
    "overall": 4,
    "scenario": "英文用户首选",
    "training_languages": ["en"]
  },
  "bge-m3": {
    "dimension": 1024,
    "size_mb": 437,
    "chinese_score": 3,
    "english_score": 3,
    "overall": 3,
    "scenario": "多语言均衡",
    "training_languages": ["zh", "en", "multilingual"]
  },
  "nomic-embed-text": {
    "dimension": 768,
    "size_mb": 146,
    "chinese_score": 1,
    "english_score": 4,
    "overall": 2,
    "scenario": "轻量英文，中文不推荐",
    "training_languages": ["en"]
  }
}
```

**评分维度：**

| 维度 | 满分 | 依据 |
|------|:--:|------|
| 中文语义 | 5 | 训练语言是否含中文、中文 benchmark 实测 |
| 英文语义 | 5 | 训练语言是否含英文 |
| 速度/大小 | — | 维度 + 文件大小，越小越好 |
| 综合 | 5 | 中英文加权 + 实际 GREEN 基准命中率 |

### Dashboard 设计体系

**设计 skill**: `dashboard` — 暗色云平台美学，模块化网格，玻璃面板，数据层级。

**设计 token**（来自 `dashboard` skill）：

| Token | 值 | 用途 |
|-------|-----|------|
| `--surface` | `#09090b` | 页面底色 |
| `--surface-elevated` | `#18181b` | 面板底色 |
| `--text-primary` | `#fafafa` | 主文字 |
| `--text-secondary` | `#a1a1aa` | 次文字 |
| `--accent` | `#0C5CAB` | 强调色（评分条、链接） |
| `--success` | `#10b981` | 高分/在线 |
| `--warning` | `#f59e0b` | 中分 |
| `--danger` | `#ef4444` | 低分/离线 |
| `--radius` | `12px` | 面板圆角 |
| `--grid` | `8px` | 基准间距 |

**字体**: IBM Plex Sans（已在 dashboard.html 中加载）

**不适用**:
- `high-end-visual-design` — Double-Bezel/嵌套玻璃丸/Z轴层叠等代理商语言，与数据 dashboard 冲突
- `design-taste-frontend` — 第 13 节明确排除 dashboard，审美偏营销落地页

### 模型诊断面板（Phase 2 实现）

**位置**: 嵌在 dashboard.html 右侧统计面板下方，作为新 section。

**结构**: 一张卡片，分三段

```
┌─ Embedding Model ───────────────────────────────┐
│                                                  │
│  Current  bge-large-zh-v1.5                     │
│           1024-d · 202 MB                       │
│                                                  │
│  Chinese  ████████████████████████████  5/5      │
│  English  ████████████                  2/5      │
│  Overall  ████████████████████████      4/5      │
│  Scenario  Best for Chinese users               │
│                                                  │
│  ──────────────────────────────────────────     │
│  Models                       Size     Score     │
│  bge-large-zh-v1.5  ○ Active  202MB    ⭐4      │
│  bge-large-en-v1.5  ○ —      219MB    ⭐4      │
│  bge-m3             ○ —      437MB    ⭐3      │
│  nomic-embed-text   ○ Ready  146MB    ⭐2      │
└──────────────────────────────────────────────────┘
```

**交互规则**:
- 评分条：纯 CSS `width: N%` 背景色渐变 `--danger → --warning → --success`
- 当前模型高亮 `--accent` 左边框（2px）
- 模型列表：`display: grid; gap: 8px`，每行 `grid-template-columns: 1fr auto auto auto`
- 状态圆点：`○ Active` = 当前使用模型（accent 色）| `○ Ready` = 已安装 | `○ —` = 未安装
- 30s 自动刷新，主题切换时同步更新评分条颜色

**CSS 要点**:
- 卡片用 `background: var(--surface-elevated); border-radius: var(--radius); border: 1px solid rgb(255 255 255 / 0.06)`
- 评分条用 `<div>` + `style="width: N%"` + `transition: width 0.4s` 平滑过渡
- 不写 `!important`、不用 `setAttribute('style', ...)`
- 暗/亮主题通过 `[data-theme="dark"]` / `[data-theme="light"]` CSS 变量切换
- 移动端 (< 768px): 评分条缩短、模型列表字号 12px

## 实施步骤

### Phase 1: SKILL.md 多模型推荐

**文件**: `~/.hermes/skills/software-development/smart-skill-router/SKILL.md`

**改动**：
1. 配置节改为列出 3 种推荐 + 备选，不再只推荐中文模型
2. 推荐优先级：中文用户→zh-v1.5，英文用户→en-v1.5，多语言→bge-m3
3. 每种模型附安装命令（hf-mirror 路径）

**推荐表：**

| 场景 | 模型 | 维度 | 大小 | 中文 | 英文 | 安装 |
|------|------|:--:|------|:--:|:--:|------|
| 🥇 中文用户 | bge-large-zh-v1.5 | 1024 | 202MB | ⭐5 | ⭐2 | curl hf-mirror |
| 🥇 英文用户 | bge-large-en-v1.5 | 1024 | 219MB | ⭐2 | ⭐5 | curl hf-mirror |
| 🥈 多语言 | bge-m3 | 1024 | 437MB | ⭐3 | ⭐3 | curl hf-mirror |
| 🥉 轻量英文 | nomic-embed-text | 768 | 146MB | ⭐1 | ⭐4 | ollama pull |

### Phase 2: Dashboard 面板

**后端** (`dashboard.py`):
1. 新增 `GET /api/model-info` 端点
   - 读取 `ssr.embedding.model` 配置
   - 读取 `model_scores.json` 获取评分
   - 调用 Ollama API 检测当前模型是否在线
   - 调用 Ollama API 列出所有已安装 embedding 模型
   - 返回 `{current, scores, installed, available}`
2. 新增 `model_scores.json` 数据文件

**前端** (`dashboard.html`):
1. 新增 `#panel-model` 面板 DOM
2. 新增 `loadModelInfo()` 函数 → 调用 `/api/model-info`
3. 新增 `renderModelPanel(data)` → 渲染评分条 + 模型列表
4. 随 30s 刷新周期更新

**安全性**: 
- `model_scores.json` 是公共评分数据，不含任何用户信息
- `/api/model-info` 不返回用户 skill 数量、命中率等私人数据
- 只展示"这个模型是什么能力"——通用知识，不是隐私

### Phase 3: 不在此 plan 展开

双模型自动路由 (`_detect_language` → `_embed` 多模型) 留待 Phase 3 单独 plan。

### Phase 4: 一键基准测试按钮

**痛点**：换模型后想知道实际匹配质量，当前需切终端跑 `python3 test_ssr.py`，割裂。

**方案**：模型面板底部加 `[Run Benchmark]` 按钮 → 后端跑 test_ssr.py → 结果渲染到面板。

**改动**：

| 文件 | 改动 | 工作量 |
|------|------|:--:|
| `dashboard.py` | +`POST /api/benchmark` → `subprocess.run` 调 `test_ssr.py` → 解析输出 → JSON | ~30行 |
| `dashboard.html` | +按钮 + 结果区 CSS + `runBenchmark()` + `renderBenchmarkResult(data)` | ~40行 |
| i18n | +3个 key（"run-benchmark"/"benchmarking"/"benchmark-score"） | ~6行 |

**API 响应**：
```json
{
  "ok": true,
  "embedding_model": "bge-large-zh-v1.5",
  "keyword_score": "5/5",
  "embedding_score": "2/5",
  "scenes": [
    {"name": "UI设计", "expected": "ui-ux-pro-max", "hit": true, "skills": ["brainstorming","ui-ux-pro-max"]},
    {"name": "代码调试", "expected": "diagnose", "hit": true, "skills": ["diagnose"]},
    ...
  ]
}
```

**结果展示**（面板下方展开）：

```
┌─ GREEN Benchmark ─────────────────────────────────┐
│  Keyword: 5/5  │  Embedding: 2/5                  │
│                                                    │
│  ✅ UI 设计          → ui-ux-pro-max               │
│  ✅ 代码调试          → diagnose                    │
│  ✅ ASCII 艺术       → ascii-art                   │
│  ✅ 学术写作          → research-paper-writing      │
│  ✅ 金融分析          → technical-analysis           │
└───────────────────────────────────────────────────┘
```

**限制**：需模型已装 + embedding 索引已建。未建索引时提示"请重启 Hermes 重建索引"。

**风险**：`test_ssr.py` 里调了 Ollama embedding API，单线程服务器可能短暂阻塞（~2秒）。单用户场景无影响。

## 改动清单

| 文件 | Phase | 改动 |
|------|:--:|------|
| SKILL.md | 1 | 配置节改为多模型推荐表 |
| model_scores.json | 2 | 新建，4 模型评分数据 |
| dashboard.py | 2,4 | +`/api/model-info` 端点 + `POST /api/benchmark` |
| dashboard.html | 2,4 | +模型诊断面板 + 一键基准测试按钮 |

## 不涉及

- `__init__.py` — 匹配逻辑不改（Phase 3 才改）
- `plugin.yaml` — 不变
- `a_rules.json` / `embeddings.json` — 不变

## 坑点预防

1. **不暴露隐私**: 模型评分是通用知识，不是用户数据。Dashboard 面板不展示 skill 数量、命中率等个人信息。
2. **model_scores.json 手动维护**: 不在代码里硬编码评分——新增模型只需改 JSON，不改 Python。
3. **Dashboard API 轻量**: `/api/model-info` 只查 config + Ollama list + 静态 JSON，无 heavy compute。
4. **i18n 独立**: 中英文切换只影响 UI 文本，不影响评分数据。
