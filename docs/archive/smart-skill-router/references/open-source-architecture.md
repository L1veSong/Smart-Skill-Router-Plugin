# SSR 开源架构：通用层 vs 个性化层

> 决策: 2026-07-23 | 状态: 设计完成，待实施

## 问题

a_rules.json 写死了 `L1veSong` 的 skill 名（如 `zy-cinematic-realism`、`travel-plan-request`）。
别人 fork 后 skill 名不同，规则全部失效。需要解耦。

## 双层架构

### 第一层：通用层（发布到 GitHub）

```
ssr/
├── __init__.py           # MoE 架构 — 任何人通用
├── domain_stems.json      # 域词干表 — 中文语义，不绑 skill
├── a_rules.example.json   # 示例规则 — 带注释 "替换为你的skill"
├── README.md              # 安装 + 规则设计指南
└── scripts/scan_skills.py # 扫描本地skill → 按域分组 → 自动归域
```

域词干是通用的——"玩"→旅行、"剪"→视频、"电影感"→生图。这些是中文语义，跟谁装的什么 skill 无关。

### 第二层：个性化层（用户本地）

```
a_rules.json    → 用户自己的规则（skill 名绑定自己的库）
```

### 第三层：用户上手流程

1. 装 SSR → 自带域词干（通用）
2. 跑 `scripts/scan_skills.py` → 扫描本地 400+ skill → 按域词干自动归域
3. 参考 `a_rules.example.json` 写精准规则（或让 AI 根据 scan 结果帮写）
4. 重启 Hermes → A 层生效

**自动归域能到 ~70%。** 剩下的 30%（如"电影那种感觉"→zy-cinematic-realism）需用户看过 skill 后手动配。

## 核心原则

- 域词干 = 通用（中文语义不绑 skill 名）
- 精准规则 = 个性化（用户审核过的映射）
- SSR 发的是架构 + 词干，不是写死 skill 名的规则
