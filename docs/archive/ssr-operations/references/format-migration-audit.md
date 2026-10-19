# SSR 格式迁移审计（v2.0.0 实战 · 2026-06-23）

v2.0.0 将 A 层规则从硬编码 skill 名（`skills: [{name, phase}]`）迁移为关键词动态匹配（`keywords: [...]` + `phases: [...]`）。迁移完成后必须全量 grep 审计。

## 审计报告模板

```
=== SSR vX.Y.Z 全量 grep 审计 ===

1. 版本号一致性
   plugin.yaml: vX.Y.Z (规范来源)
   __init__.py 行2:   ✅/❌
   __init__.py 行9:   ✅/❌
   __init__.py 行1487: ✅/❌
   __init__.py 行1851: ✅/❌
   README.md badge:   ✅/❌
   dashboard.py 行2:  ✅/❌
   test_ssr.py 行3:   ✅/❌

2. 格式残留
   a_rules.json:   N条 (keywords=N, skills=0) / N条旧格式残留
   a_rules_v3.json: N条 (keywords=N, skills=0)
   a_rules.local.json: N条 (keywords=N, skills=0)

3. 死引用
   [逐个列出旧格式中引用的 skill 是否存在]

4. CMG 文档同步
   CMG SKILL.md 中 SSR 版本引用与实际是否一致
```

## 2026-06-23 v2.0.0 审计实录

**版本号漂移（7 处）：** plugin.yaml 升到 2.0.0，其余全滞后。根因：版本号散布 7 个文件，升级时只改了 plugin.yaml。

**格式残留（2 条）：** a_rules.json 中 2 条自动生成规则仍为旧格式（长 hash key），已自动清理。

**死引用（2 个）：** agent-reach / huashu-nuwa skill 不存在。

**修复记录：** 7 处版本号 + 2 处 CMG 引用 + 2 条旧格式清理。详见 ssr-operations SKILL.md 坑点。
