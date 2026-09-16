---
name: smart-skill-router
description: "智配路由 (SSR) 插件 v3.0.1 — 三层漏斗路由：关键词高召回 + 语义匹配高精准 → LLM 语境理解。MoE 域路由（34 域），运行时动态对齐，不依赖具体 skill 名。"
version: 3.0.1
author: L1veSong
license: MIT
metadata:
  hermes:
    tags: [skill-matching, routing, plugin, auto-load]
    related_skills: [writing-skills, verification-before-completion]
---

# 智配路由 (SSR) — Smart Skill Router v3.0.1

> 插件本体：`plugin/`（复制到 `~/.hermes/plugins/ssr/` 即用）
> 配置：`plugin/plugin.yaml` + `plugin/a_rules.json`（规则库，运行时加载）
> 语义索引：首次运行自动构建并缓存（本地生成，不随仓库分发）
> 历史文档：`references/`

## 它做什么

每次 LLM 推理前，SSR 分析用户意图，从已安装 skill 中推荐最合适的组合，以 `[SSR]` 单行注入上下文。三层漏斗——一层高召回、一层高精准、一层懂语境：

```
用户消息
  ├─ A 层 · 关键词匹配（高召回，零延迟）—— 规则运行时动态对齐
  ├─ A 层 · 语义匹配（高精准，本地索引）—— 补充关键词未覆盖的 skill
  ├─ 合并去重 → 冷却去重 → 按阶段输出 [SSR] 推荐
  └─ B 层 · LLM 语境理解（A 层无结果时兜底；连续命中自动升级为 A 层规则）
```

## MoE 域路由

- 34 个领域词干表：机械提取 + Golden 校验（55 项全绿），零手写
- 词干命中 → 激活域 → 域内匹配；每词干仅鉴别 1–2 域，歧义交 A 层正则裁决
- 规则运行时动态对齐，换机器 / 换 skill 集自动适配，不依赖任何 skill 名

## Dashboard（可选）

`dashboard.py` + `dashboard.html` — 推荐统计、规则管理与参数配置。

## 安装

```bash
git clone https://github.com/L1veSong/Smart-Skill-Router-Plugin.git
cp -r Smart-Skill-Router-Plugin/plugin/ ~/.hermes/plugins/ssr/
# 重启 Hermes 生效
```

## 测试

```bash
python3 tests/test_ssr.py --quick   # 文件 + 规则 + GREEN 基准
python3 tests/test_ssr.py           # 全量
```

## 版本历史（近期）

| 版本 | 日期 | 说明 |
|---|---|---|
| v3.0.1 | 2026-09-15 | 注册流程重写：一次性索引 + 缓存，修复大量 skill 下的加载耗时 |
| v3.0.0 | 2026-07-23 | MoE 词干表定稿（34 域 272 词干，Golden 全绿） |
| v2.5.0 | 2026-07-23 | MoE 词干表扩展（34 域；原子化去歧义） |
| v2.4.0 | 2026-07-23 | MoE 架构升级（域路由 + skills 直推） |

完整历史见 `CHANGELOG.md`。

## 许可

MIT License — 见 `LICENSE`。
