# CC 网文写作 Skill 生态与 SSR 路由

Hermes → Claude Code → CC 原生 skill 的零损失委托模式。SSR writing 域命中后路由到 claude-code。

## 核心原则

Claude Code skill 深度依赖 hooks/agents/plugins——adapt-to-hermes 会损失 40-70% 功能。
正确做法：装到 ~/.claude/skills/，Hermes 通过 `claude -p` 委托 CC 原生执行。

## 已装 CC 网文 Skill

| Skill | 路径 | 功能 |
|-------|------|------|
| oh-story-claudecode | ~/.claude/skills/ | 13 子 skill: 扫榜/拆文/写作/去AI味/封面 |
| chinese-novelist-skill | ~/.claude/skills/ | 三层问答·偏好记忆·中断续写·自动校验 |
| webnovel-writer | ~/.claude/skills/ | 长篇一致性系统: Story System+RAG+Dashboard(v6.2.1) |

## SSR 路由

writing 域 5 条新规则覆盖：
- 写小说/网文/长篇/短篇 → claude-code
- 扫榜/拆文/黄金三章 → claude-code
- 去AI味/deslop → claude-code
- 续写/连载/大纲/人物设定 → claude-code
- 番茄/起点/晋江/投稿平台 → claude-code

## 委托示例

```bash
claude -p "/story 写一部都市异能小说..." --max-turns 30
claude -p "/story-long-scan 起点热门榜单" --max-turns 10
claude -p "/story-deslop 检查第3章" --max-turns 5
```

## 独立 CLI 工具

| 工具 | 路径 | 功能 |
|------|------|------|
| InkOS | `@actalk/inkos@1.7.1` (npm global) | 多 Agent 小说生产系统: init/book/chapter/write/auto/review |

SSR a_rules.json 中 `inkos` 规则指向 `@actalk/inkos`。与 CC 网文 skill 互补——InkOS 偏结构化多 Agent 流水线，CC skill 偏交互式写作。

## Agent 交叉验证清单

当用户问「有没有 X 工具/skill」且 SSR 静默时，Agent 必须执行三步交叉验证再回复：
1. `grep` a_rules.json 检查是否有对应域规则
2. `ls ~/.claude/skills/` 检查 CC 生态
3. `npm list -g` + `which` 检查 CLI 工具

不得以 SSR 静默为唯一证据声称「没有」。
