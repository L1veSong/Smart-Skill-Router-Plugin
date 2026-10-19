# 三维评分系统 — 三种模式

> 2026-06-22

## 核心设计

| 模式 | 命令 | 测什么 | 调用 |
|------|------|--------|------|
| `total` | `--mode total` | 完整 SSR 管线 | import 真实 plugin → _intent_gate → _match_a_layer → _llm_screen |
| `embedding` | `--mode embedding` | 向量模型质量 | 独立 Ollama API，不依赖 SSR 代码 |
| `gate` | `--mode gate` | 本地门控 | 调本地 ollama 模型 YES/NO，不调 API |

## 原则

1. total = import SSR plugin 真实函数，不自己实现。SSR 更新 → benchmark 自动跟上。
2. embedding = 独立 Ollama API。换模型对比分数——bge→qwen3→bge-m3。
3. gate = 本地 ollama。测门控模型能力，不依赖 API。
4. 零硬编码：embedding 模型名/相似度阈值/门控 provider 全读 config.yaml。
5. 50 条基准内置（30信号+20噪音），零隐私。
6. 期望 skill 不存在 → 排除（`applicable`），不扣分。
7. 分类明细输出。

## 评分公式

| | 总评分 | embedding裸分 | 门控裸分 |
|---|:--:|:--:|:--:|
| 信号命中 | 40 | 35 | 30 |
| 噪音 | 30 | 30 | 60 |
| top-3 | 20 | 25 | - |
| 延迟 | 10 | 10 | 10 |
| **总分** | **100** | **100** | **100** |

## 初始化

benchmark 启动时 import SSR plugin → 设置 `_CONFIG_CACHE` 绕过 `hermes_cli` 依赖：

```python
mod._CONFIG_CACHE = ssr_cfg  # 直接注入，不调 hermes_cli
mod._SKILL_INDEX, _ = mod._build_skill_index()
mod._A_RULES = mod._load_a_rules()
mod._EMBEDDING_INDEX = mod._load_embedding_index() or {}
```

否则 `_load_ssr_config()` 回退空配置 → embedding 模型默认 `nomic-embed-text` → 404。
