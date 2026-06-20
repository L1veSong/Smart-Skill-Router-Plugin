# Smart Skill Router / 智配路由

> 智配路由 — 自动匹配用户意图到最合适的 skill 并推荐加载。

[![version](https://img.shields.io/badge/version-1.6.1-blue)](https://github.com/L1veSong/Smart-Skill-Router-Plugin)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)

## 是什么

智配路由 (Smart Skill Router) 是 Hermes Agent 的 `pre_llm_call` 插件，在每次 LLM 推理前自动分析用户意图，推荐最合适的 skill。**不让用户手动说「用 brainstorming」「用 ui-ux-pro-max」——系统自动匹配。**

## 怎么工作

```
用户消息 → 中文查询增强 → A 层关键词正则 → A 层 Embedding 语义 → 合并去重 → 注入推荐 → LLM 推理
                                                                         ↓
                                                               B 层 LLM 兜底（A 层无结果时）
```

三层匹配漏斗：

| 层 | 机制 | 延迟 | 覆盖 |
|----|------|:--:|------|
| A 层关键词 | 正则精确匹配 | 零 | 100+ 手动规则 |
| A 层 Embedding | 余弦相似度（1024 维） | ~100ms | 全部 380+ skill |
| B 层 LLM | 语义匹配 | ~2-5s | 兜底，A 层无结果时激活 |

B 层连续 3 次命中同一匹配 → 自动固化到 A 层关键词规则。

## v1.6.1 新功能

**静默推荐模式：** `ssr.display: false`（默认）推荐只给 AI，用户不看到推荐输出。设 `true` 恢复展示。

**Dashboard benchmark 修复：** 模型面板 "Run Benchmark" 按钮现已可用，实时跑 TDD 测试并展示结果。

**多模型 Embedding 支持：** 4 模型可选切换，中文用户首选 `bge-large-zh-v1.5`。

## 快速安装

### 1. 安装 Embedding 模型（Ollama）

```bash
# 中文用户首选（202MB，纯中文 1024 维）
curl -L -o ~/Downloads/bge-large-zh-v1.5-q4_k_m.gguf \
  "https://hf-mirror.com/CompendiumLabs/bge-large-zh-v1.5-gguf/resolve/main/bge-large-zh-v1.5-q4_k_m.gguf"
ollama create bge-large-zh-v1.5 -f <(echo "FROM ~/Downloads/bge-large-zh-v1.5-q4_k_m.gguf")

# 英文用户可选（219MB）
curl -L -o ~/Downloads/bge-large-en-v1.5-q4_k_m.gguf \
  "https://hf-mirror.com/CompendiumLabs/bge-large-en-v1.5-gguf/resolve/main/bge-large-en-v1.5-q4_k_m.gguf"
ollama create bge-large-en-v1.5 -f <(echo "FROM ~/Downloads/bge-large-en-v1.5-q4_k_m.gguf")
```

### 2. 安装插件

```bash
# 复制插件文件
cp plugin/__init__.py ~/.hermes/plugins/ssr/
cp plugin/plugin.yaml ~/.hermes/plugins/ssr/
cp plugin/a_rules.json ~/.hermes/plugins/ssr/

# 安装 skill 文档
mkdir -p ~/.hermes/skills/software-development/smart-skill-router/
cp -r SKILL.md references/ tests/ ~/.hermes/skills/software-development/smart-skill-router/

# 启用插件
hermes config set plugins.enabled '["ssr"]' --merge
```

### 3. 重启 Hermes

插件在重启后生效。

## 配置

```yaml
ssr:
  display: false           # 默认静默（只推给 AI）。true = 展示给用户
  hooks:
    pre_llm_call: true
    post_llm_call: true
  embedding:
    provider: ollama
    model: bge-large-zh-v1.5   # 推荐模型（见下表）
    timeout: 15
  b_layer:
    provider: main              # B 层兜底后端（main / ollama / openai）
    timeout: 30
  auto_gen_rules: false
```

### 推荐 Embedding 模型

| 场景 | 模型 | 维度 | 大小 | 中文 | 英文 |
|------|------|:--:|------|:--:|:--:|
| + 中文用户 | `bge-large-zh-v1.5` | 1024 | 202MB | 5 | 2 |
| + 英文用户 | `bge-large-en-v1.5` | 1024 | 219MB | 2 | 5 |
| + 多语言备选 | `bge-m3` | 1024 | 437MB | 3 | 3 |
| + 轻量英文 | `nomic-embed-text` | 768 | 146MB | 1 | 4 |

> 切换模型后必须执行：`rm ~/.hermes/plugins/ssr/embeddings.json` + 重启 Hermes。

### 展示模式切换

```bash
hermes config set ssr.display true   # AI 在回复首行展示推荐
hermes config set ssr.display false  # 静默（默认），用户不看到推荐
```

## Dashboard

Smart Skill Router 自带 Web 管理面板：

```bash
cd ~/.hermes/plugins/ssr && python3 dashboard.py
# 打开 http://localhost:8766
```

功能：
- **A 层规则管理：** 浏览/搜索/编辑/删除关键词规则
- **引擎配置：** 可视化修改 embedding 模型、B 层后端
- **Embedding Model 面板：** 三维评分条（中文/英文/综合）+ 模型对比列表
- **Run Benchmark：** 一键跑 TDD 基准测试，查看各场景命中率
- **中英文切换 + 亮暗主题**

## 测试

```bash
# TDD 基线测试（RED -> GREEN -> REFACTOR）
python3 tests/ssr_tdd_baseline_test.py

# 存活验证
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
```

### 基准性能（bge-large-zh-v1.5）

| 场景 | A 层 | Embedding | 排名 |
|------|:--:|:--:|------|
| 设计响应式导航栏 | OK | OK | ui-ux-pro-max #206, brainstorming #116 |
| 调试 KeyError | OK | OK | diagnose #5, systematic-debugging #3 |
| 生成 ASCII 猫咪图 | OK | OK | - |
| 论文 Related Work | OK | OK | research-paper-writing #10 |
| 茅台均线分析 | OK | OK | technical-analysis #1, tushare-finance #6 |

## 文件结构

```
Smart-Skill-Router-Plugin/
├── SKILL.md              # skill 完整文档（含 38 条坑点）
├── README.md             # 本文件
├── CHANGELOG.md          # 版本历史
├── LICENSE               # MIT
├── dashboard.py          # Dashboard HTTP 服务器
├── dashboard.html        # Dashboard 前端
├── model_scores.json     # Embedding 模型评分数据
├── references/           # 参考文档（15 篇）
├── tests/                # TDD 基准测试
└── plugin/               # Hermes 插件核心
    ├── plugin.yaml       # 插件元数据（v0.6.5）
    ├── __init__.py       # 插件代码（~1730 行）
    └── a_rules.json      # A 层规则（冷启动种子）
```

## 故障排查

**无推荐输出？**
```bash
# 1. 存活确认
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# 预期：skill: N | emb: N | A层: N

# 2. 检查 embedding 模型
grep 'embedding:' -A 3 ~/.hermes/config.yaml
ollama list | grep -i embed
# 两者必须一致

# 3. 重建索引
rm ~/.hermes/plugins/ssr/embeddings.json
# 重启 Hermes
```

**embedding 全部 404？** Ollama 中没有配置的模型 → `ollama pull` 安装或切换模型。

**Dashboard benchmark 一直「索引未建」？** 确认 `tests/ssr_tdd_baseline_test.py` 文件存在。

## 许可证

MIT
