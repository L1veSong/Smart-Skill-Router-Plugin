# V3 迁移完整性审计 (2026-06-22)

## 背景

SSR v2.0.0 将 A 层规则从 v2 `skills` 格式升级到 v3 `keywords` 格式。但迁移只覆盖了主流程（`_match_a_layer_keyword`、`_pre_llm_call`），维护函数全部残留 v2 代码。

## 审计结果

grep `"skills"` 引用 → 逐个判定是否 v2 残留：

| 行 | 函数 | 状态 |
|---|------|:--:|
| 739 | `_cleanup_a_rules` | ✅ 已补 v3 兼容 |
| 752 | `_cleanup_a_rules` | ✅ v2 向后兼容 |
| 832 | `_auto_gen_a_rules` | ✅ 已改为 v3 keywords |
| 1115-1120 | `_hot_remove_skill` | ✅ 已补 v3 兼容 |
| 1099 | `_promote_to_a` | ✅ 已改为 v3 |

## 修复内容

1. **`_promote_to_a`**: v2 `skills` → v3 `keywords` + `phases`。关键词从 `regex.split(pattern)` 提取，不拆 skill 名。

2. **`_hot_remove_skill`**: 新增 v3 分支：检查 `rule["keywords"]` 中存在该 skill 名则移除。

3. **`_auto_gen_a_rules`**: `"skills": [name]` → `"keywords": [kw]`。

4. **`_cleanup_a_rules`**: 新增 v3 分支：检查关键词是否匹配任何 _SKILL_INDEX skill，零匹配标记为死规则。

## 预防

v3 迁移后必须 `grep -n '"skills"' __init__.py | grep -v SKILL_INDEX` 全量审计，确认仅剩 v2 向后兼容代码（cleanup/hot-remove 中）和 LLM prompt 文本（非存储格式）。

## 本地规则 (a_rules.local.json)

- `_load_a_rules()` 自动合并 local 覆盖 public
- local 只读不写，B→A 升级写入 public
- Dashboard 规则管理只操作 public
- 发行包不含 local（`.gitignore`）
