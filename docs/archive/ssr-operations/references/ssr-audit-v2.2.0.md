# SSR 全量审计 v2.2.0 (2026-07-04)

## 命令

```bash
cd ~/.hermes/plugins/ssr

# 1. 版本号 — 对外文件零 v2.1.0 残留（CHANGELOG/README 历史条目除外）
grep -rn 'v[0-9]\.[0-9]\.[0-9]' __init__.py plugin.yaml dashboard.py test_ssr.py README.md CHANGELOG.md

# 2. 硬编码 — 对外文件零 bge/qwen/1024/4096
grep -rnIE 'bge|qwen|1024维|4096维' __init__.py plugin.yaml dashboard.py test_ssr.py README.md

# 3. benchmark — 零 skills 残留
grep -rn 'rule.get.*skills\|rule\[.skills.\]' tests/

# 4. 死文件 — dashboard.html.bak 保留，其余全删
find . -name '*.bak*' | grep -v 'dashboard.html.bak' | xargs rm -f

# 5. CHANGELOG 声称 vs 代码实际
grep -n 'similarity_floor\|_similarity_floor\|gate_prompt\|llm_screen\|_llm_screen\|display\|meta_detection' __init__.py

# 6. a_rules.json — 全 keywords 零 skills
python3 -c "import json; d=json.load(open('a_rules.json')); bad=[k for k,v in d.items() if 'skills' in v]; print(f'规则={len(d)} skills残留={len(bad)}')"

# 7. 硬短路日志覆盖 — 确保每个 len<X 短路有 logger.info
grep -n 'len.*< [0-9].*return' __init__.py

# 8. intent_gate providers 非空验证
grep -A 20 '^  intent_gate:' ~/.hermes/config.yaml | grep -A 10 'providers:'
```

## 审计发现

| # | 等级 | 问题 | 修复 |
|---|:---:|------|------|
| 1 | 🔴 | CHANGELOG.md 缺 v2.2.0 条目（最新停 v2.1.0） | 插入 v2.2.0 条目 |
| 2 | 🔴 | README.md / dashboard.py / test_ssr.py (2处) 版本号 v2.1.0 未同步 | → v2.2.0 |
| 3 | 🟡 | ssr-operations SKILL.md version 2.3.0 vs plugin 2.2.0 | 跳过 — skill 版本独立于 plugin 版本 |
| 4 | 🔴 | 10 个 .bak 残留（CHANGELOG 声称"5个已清理"不实） | 删 9 个，保留 dashboard.html.bak |
| 5 | 🟡 | `_similarity_floor()` 函数仍存在 — CHANGELOG 说"删除"不精确 | CHANGELOG 措辞修正：语义变更非字面删除 |
| 6 | 🟡 | embeddings.json `model: ?` — 无模型记录，换模型后无从判断 | 建议编码模型名到索引元数据 |
| 7 | 🟢 | ssr-operations SKILL.md 大量模型名（bge/qwen/1024/4096） | 运维文档故意保留，非对外发布 |

## 教训

### dashboard.html.bak 保留规则

dashboard.html 无 git 版本控制。审计清单第 4 项明确规定：
- `find . -name '*.bak*'` → 全删
- **唯一例外** `dashboard.html.bak`：改前备份、改后保留（回滚安全网）

本条例外在审计清单中已存在，但过去被忽略（6/23 审计误删了 dashboard.html 的所有备份）。

### CHANGELOG "删除" ≠ 代码删除

v2.2.0 CHANGELOG 写"删 explicit similarity_floor"——但代码中 `_similarity_floor()` 函数仍存在，只是语义从"必填配置项"变为"无极校准优先+显式 override"。CHANGELOG 措辞应精确区分：
- **删除** = 函数/变量/配置项从代码中移除
- **语义变更** = 函数存在但行为改变

### 版本号所有权

ssr-operations SKILL.md version 2.3.0 是 **运维 skill 的自身版本**，不是 SSR 插件版本。审计时不应将二者混淆——运维文档可以比被运维的插件版本高。

### .bak 根因分析

本会话 10 个 .bak 中有 3 个是当日生成的（0703/0704）——每次修改前 cp 备份，改后忘记删。`.bak` 不是非零即死的二元问题——需持续管理。

## 诊断陷阱

### 陷阱 1: `len(msg) < 4` 硬短路零日志

`_intent_gate()` line 1687：`len(msg) < 4` 直接 `return False`，无 `logger.info()` 输出。

**症状：** 用户发 "谢谢" (2字) → 被正确拦截 → 但 `grep "噪音过滤|意图门控" agent.log` 返回空 → 运维误判功能未生效。

**实际：** 拦截正确，只是没打日志。`len(msg) < 4` 发生在 noise_filter regex 之前——短词直接短路，从不进入过滤层。

**速查：**
```bash
# ❌ 短词被硬短路拦截，零日志
echo "谢谢" | wc -m         # 2 → len < 4 → return False (无日志)

# ✅ 长词进 noise_filter，日志可见
echo "谢谢你啊" | wc -m     # 5 → 进 noise_filter regex → [ssr] 噪音过滤 → 静默
```

**修复建议：** 给硬短路加 `logger.debug("[ssr] 噪音过滤 → 硬短路 (len<4)")`。info 级别会被正常任务消息刷掉，debug 即可。

### 陷阱 2: `intent_gate.providers` 为空 → 门控跳过

`_intent_gate()` line 1750：`providers` 列表为空 → 直接 `return True` → 所有消息过 gate，无任何 LLM 筛查。门控在 config 中声明了 2 个 provider（ollama/main），但代码只读 `providers` 字段——如果 config 的 provider 用错 key 名（如 `active` 有值但 `providers` 是空列表），门控静默失效。

**验证：**
```bash
grep -A 20 '^  intent_gate:' ~/.hermes/config.yaml | grep -A 10 'providers:'
```

期望 `- model:` / `- provider:` 子项。空 = 门控不生效 = 所有消息直通 embedding 匹配。

**修复建议：** providers 为空时输出 `logger.warning("[ssr] intent_gate enabled 但 providers 为空，门控跳过")`。静默失效是运维噩梦——必须打 warning。
