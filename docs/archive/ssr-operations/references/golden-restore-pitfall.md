# Golden 备份覆盖陷阱（2026-07-24）

## 问题

`a_rules.json.bak.golden_*` 备份文件 + `cp golden_bak → rules_path` 每次执行会用旧基线覆盖当前规则。本次会话实测丢 40+ 条规则，17 个 `.bak.*` 备份文件互相踩踏。

## 修复

1. 删除所有 golden 备份文件，只保留一个 `.bak.clean`
2. 禁止 `cp <backup> → a_rules.json`——已入 CMG ban `ban_ssr_golden_restore`
3. 改规则只用增量 dict update，不用全量覆盖
4. 新增规则前不自动备份

## 教训

golden 基线恢复是双刃剑。备份留作保险可以，自动恢复逻辑必须删。操作 a_rules.json 前先告知用户影响范围。
