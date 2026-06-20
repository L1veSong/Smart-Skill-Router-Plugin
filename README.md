# Smart Skill Router (SSR)

> 智配路由 — 自动匹配用户意图到最合适的 skill 并推荐加载。

[![version](https://img.shields.io/badge/version-1.5.0-blue)](https://github.com/L1veSong/Smart-Skill-Router-Plugin)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)

## 是什么

SSR 是 Hermes Agent 的 pre_llm_call 插件，在每次 LLM 推理前自动分析用户意图，推荐最合适的 skill。**不让用户手动说「用 brainstorming」「用 ui-ux-pro-max」——系统自动匹配。**

## 怎么工作

```
用户消息 → 中文查询增强 → A 层关键词精确匹配 → A 层 Embedding 语义匹配 → 合并去重 → 注入推荐 → LLM 推理
```

- **A 层（零延迟）：** 关键词正则 + bge-m3 Embedding（1024维，371 skill）
- **B 层（兜底）：** LLM 语义匹配，A 层无结果时激活
- **B→A 升级：** 连续 3 次同一匹配自动固化到 A 层

## 快速安装

```bash
# 1. 安装 bge-m3 embedding 模型（Ollama）
curl -L -o ~/Downloads/bge-m3-q4_k_m.gguf \
  "https://hf-mirror.com/groonga/bge-m3-Q4_K_M-GGUF/resolve/main/bge-m3-q4_k_m.gguf"
ollama create bge-m3 -f <(echo "FROM ~/Downloads/bge-m3-q4_k_m.gguf")

# 2. 复制插件文件
cp plugin/__init__.py ~/.hermes/plugins/ssr/
cp plugin/plugin.yaml ~/.hermes/plugins/ssr/
cp plugin/a_rules.json ~/.hermes/plugins/ssr/

# 3. 安装 skill 文档
cp -r SKILL.md references/ tests/ ~/.hermes/skills/software-development/smart-skill-router/

# 4. 启用插件
hermes config set plugins.enabled '["ssr", ...]'
```

## 配置

```yaml
ssr:
  hooks:
    pre_llm_call: true
    post_llm_call: true
  embedding:
    provider: ollama
    model: bge-m3
    timeout: 15
  b_layer:
    provider: main
    timeout: 30
  auto_gen_rules: false
```

## 测试

```bash
# TDD 基线测试（RED→GREEN→REFACTOR）
python3 tests/ssr_tdd_baseline_test.py

# 存活验证
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
```

## 基线性能

| 场景 | A 层 | bge-m3 | 排名 |
|------|:--:|:--:|------|
| 设计导航栏 | ✅ | ✅ | ui-ux-pro-max #23 |
| 调试 KeyError | ✅ | ✅ | diagnose #60 |
| ASCII 猫咪图 | ✅ | ✅ | - |
| 论文 Related Work | ✅ | ✅ | research-paper-writing #26 |
| 茅台均线分析 | ✅ | ✅ | technical-analysis #1 |

## 文件结构

```
Smart-Skill-Router-Plugin/
├── SKILL.md              # skill 文档
├── README.md             # 本文件
├── CHANGELOG.md          # 版本历史
├── LICENSE
├── references/           # 参考文档
├── tests/                # TDD 测试
└── plugin/               # Hermes 插件
    ├── plugin.yaml       # 插件元数据
    ├── __init__.py       # 插件代码
    └── a_rules.json      # A 层规则（初始种子）
```

## 许可证

MIT
