# SSR v2.1.0 全量审计 (2026-06-23)

> 审计范围: `~/.hermes/plugins/ssr/` 全部 13 个活动文件
> 审计方法: 全量 grep 版本号 + CHANGELOG 声称 vs 代码实际逐条验证 + config 一致性检查

## 审计结论: 4/5 CHANGELOG 声称已验证通过，2 个文档层面问题待修

### 🔴 必须修复

| # | 问题 | 位置 | 当前值 | 应为 |
|---|------|------|--------|------|
| 1 | README badge 版本滞后 | `README.md:9` | `version-2.0.0` | `version-2.1.0` |
| 2 | 日期不一致 | `__init__.py:9` vs `CHANGELOG.md:3` | `(2026-06-22)` | `(2026-06-23)` |

### 🟡 文档与代码不一致

| # | 问题 | 位置 | 详情 |
|---|------|------|------|
| 3 | docstring 声称不准确 | `__init__.py:5` | 写 "bge-m3 1024维" 但 config 实际用 `Qwen/Qwen3-Embedding-8B`（硅基流动 4096维） |
| 4 | docstring config 示例过时 | `__init__.py:14-22` | 只展示 v2.0 配置（enabled/mode/scan_mode/b_layer），缺 v2.1 新增的 `intent_gate`/`meta_detection`/`noise_filter`/`display` |
| 5 | 注释路径微错 | `__init__.py:1494` | 写 `ssr.gate.prompt`，实际代码用 `ssr.intent_gate.prompt` |

### ✅ CHANGELOG 声称 vs 代码实际

| 声称 | 验证 | 状态 |
|------|------|------|
| Gate prompt 配置化 | `_call_llm_intent()` 接收 `gate_prompt` 参数，来自 `ssr.intent_gate.prompt` (line 1705) | ✅ |
| 元对话检测 | `_intent_gate()` 含正则预检层 (line 1635-1647)，config 中配了 7 条 pattern | ✅ |
| 噪音过滤配置驱动 | 从 `ssr.noise_filter.patterns` 读取 (line 1622-1633)，无 `_NOISE_PATTERNS` 硬编码残留 | ✅ |
| display 控制 | `_display_enabled()` 读 `ssr.display` (line 94-97)，false → `return None` (line 2132) | ✅ |
| 自循环学习 | `boost_skill()` + `_boost_skill()` + `preferences.json` (line 1572-1591) | ✅ |

### 🟢 轻微/建议

| # | 问题 | 详情 |
|---|------|------|
| 6 | 36 个 .bak 备份文件 | 占目录空间。对外发布前应清理 |
| 7 | `a_rules_v3.json` 不在代码路径中 | 108 条规则文件，代码只读 `a_rules.json` (100 条) + `a_rules.local.json`。v2→v3 迁移产物，建议归档到 `migrations/` 或删除 |
| 8 | `meta_detection.enabled: false` | 元对话检测功能已实现但 config 中关闭。若打算默认启用，改为 `true` |
| 9 | `embeddings.json` 36MB | 含 407 个 skill 的 4096维 embedding。对外发布应考虑是否压缩或延迟生成 |

### 📊 文件统计

- 活动文件: 13
- 备份文件: 36
- `__init__.py`: 2,230 行 / 83KB
- `a_rules.json`: 100 条规则
- `embeddings.json`: 36MB / 407 skill

## 审计方法复用指南

```bash
# 1. 全量 grep 版本号
grep -rn 'v[0-9]\.[0-9]\.[0-9]' <target-dir> | grep -v '.bak' | grep -v __pycache__

# 2. CHANGELOG 声称 vs 代码实际逐条验证
#    读 CHANGELOG → 提取每项声称 → grep 代码确认存在

# 3. config 路径一致性
#    grep config 读取路径 → 对比 config.yaml 实际结构

# 4. 备份文件统计
find <target-dir> -name '*.bak*' | wc -l
```

## 关联

- 坑点 57: 版本号 + CHANGELOG 全量更新了但功能代码没落地
- 坑点 17: 发布打包必须逐项审计
- `references/ssr-integration.md`: SSR 与 CMG 协作关系
