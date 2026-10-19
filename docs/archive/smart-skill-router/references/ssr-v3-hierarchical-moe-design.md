# SSR v3 — 层级稀疏门控路由设计 (2026-07-23)

## 用户原始洞见

> "从大类匹配到小类再到之后各种细分，一层层匹配下来直到精准的几个有关联的skill或者完美符合要求的几个。如果用户需要完美符合要求就只推完美符合的，没有就不推。如果用户要求有关系就行那推相关的。"

## 与大模型 MoE 的同源性

用户的层级稀疏路由思想，与 Switch Transformer / Mixtral / DeepSeek-V3 的门控机制完全同源：

| MoE 概念 | SSR 对应 |
|---|---|
| 稀疏激活 (Sparse Activation) | 词干激活域，只扫描命中的 |
| Top-K 门控 | 34 域只激活 2-3 个，其余切断 |
| 负载均衡 (Load Balancing) | 冷门域同样有机会被激活 |
| 专家多样性 (Expert Diversity) | 不同域对应的 skill 集合不重叠 |

## 三层架构设计

```
用户: "帮我做产品发布视频，要有字幕"
  │
  ▼
第一层：域路由器 (Domain Router)
  34域词干 → Top-3 Softmax → ["视频", "生图", "写作"]
  激活: 3/34 域 ← 91%的无关域直接切断
  │
  ▼
第二层：子域/方向匹配 (Sub-Domain Matcher)
  "视频"域内 → ["剪辑", "AI生成", "字幕"]
  "生图"域内 → ["海报"]
  "写作"域内 → [未命中→关闭]
  激活: 3个子方向
  │
  ▼
第三层：Skill 精确匹配 (Skill Precision Matcher)
  只在 "视频+字幕" 子域 regex 扫描 → [embedded-captions, remotion]
  只在 "视频+AI生成" → [hyperframes, pixelle-video]
  只在 "视频+剪辑" → [video-use]
  │
  ▼
推荐: [embedded-captions, remotion, video-use]
理由: 字幕嵌入 + 代码生成 + 视频剪辑
```

## 可解释性

每个推荐附带路由路径：
`"视频域→AI生成子域→hyperframes"`

不是黑盒推荐，用户可以看到推理链。

## 精确度控制

三种模式，控制每层置信度阈值：

| 模式 | 触发词 | 行为 |
|---|---|---|
| strict | `!ssr strict` | 只推高置信（完美符合），没匹配就空 |
| normal | `!ssr normal` (默认) | 推高+中置信 |
| related | `!ssr related` | 推高+中+同域备选（有关系就行） |

```
双命中（域+词干）= 高置信 → 直推
单命中（仅域）= 中置信 → 推但标"相关"
零命中 = 静默 → 不推
```

## 与 v2.5.0 的关键区别

| | v2.5.0 | v3 |
|---|---|---|
| ALL_DOMAINS fallback | 存在（兜底全扫） | 删除（无命中=空） |
| 路由层级 | 1层（域→规则） | 3层（域→子域→skill） |
| 置信度 | 无 | 3级（high/medium/low） |
| 用户控制 | 无 | strict/normal/related |
| 解释性 | 无路径 | 完整路由链 |

## 实施计划

### P0: 门控修复（1行代码）
```python
# 现在
return activated if activated else ALL_DOMAINS

# v3
return activated  # 无命中就空。MoE 真正工作。
```

### P1: 三层路由（~50行代码）
- `_route_domains()` — 现有，已修复
- `_route_subdomains(domain, msg)` — 新增，域内子方向匹配
- `_match_skills(subdomain, msg)` — 新增，只在激活子域内扫描

### P2: 置信度分级（~30行代码）
- `_confidence_tier(hits)` — 按命中深度返回 high/medium/low
- 双命中（域+词干）= high
- 单命中（仅域）= medium
- 零命中 = None（静默）

### P3: 用户精确度控制（~20行代码）
- `_PRECISION` 全局配置
- 支持运行时 `!ssr strict/normal/related` 切换

## 不改什么

- a_rules.json — 183条规则全部保留
- Golden 56 用例
- 现有域分类和 stem 表

## 状态

**2026-07-23**: 设计完成。未实施。等待用户确认后执行 P0→P1→P2 顺序。
