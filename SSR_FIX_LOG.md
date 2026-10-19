# SSR 死引用 & 空规则清理报告
# 2026-07-24 · Hermes重启验证通过 · 219条全部存活

## 根因定位

`_cleanup_a_rules()` 三刀砍规则（非 golden 备份问题）：

1. **死引用 (953-987 行)**: skills 指向不存在的 skill → 整条规则删除
2. **空规则 (997-1001 行)**: skills 空数组 → 删除
3. **上限淘汰 (1006-1040 行)**: config a_rules_max:60 → 超出部分全部删除

## 5 个保护点

| # | 文件 | 行 | 保护 |
|---|------|---|------|
| 1 | __init__.py | 955 | 死引用清理跳过 manual |
| 2 | __init__.py | 957 | keywords死引用跳过 manual |
| 3 | __init__.py | 1002 | 空规则删除跳过 manual |
| 4 | __init__.py | 1381 | 热删除清理跳过 manual |
| 5 | config.yaml | 734 | a_rules_max: 60→300 |

验证: `grep -c "FIX.*manual" ~/.hermes/plugins/ssr/__init__.py` → 应返回 3

## Hermes 升级后必须重打

升级覆盖 `__init__.py` 后，运行 `~/.hermes/scripts/ssr-check.sh` 检测。
如果失败，需重新应用 5 个补丁。

## 备份

- `a_rules.json.bak.golden` — 当前 219 条完整 golden
- `a_rules.json.bak.142` — 修复前 142 条残骸备份
