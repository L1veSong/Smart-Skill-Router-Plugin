# 小说/网文 SSR 路由诊断 (2026-07-26)

## 触发场景

用户问「还有写小说的skill吗？」→ 应该匹配 writing 域 → 路由到 claude-code（因为用户的 3 个网文 skill 都在 ~/.claude/skills/ 下）。

## 实际行为：静默

**根因：意图门控判为非任务请求 → P0 整轮跳过。**

SSR 日志显示 `[SSR] 本轮静默 (意图门控判定非任务请求)`。

这不是 regex 匹配问题——规则本身是对的。是门控把「询问有没有」当成了非任务对话。

## 已确认的 writing 域路由 (a_rules.json)

| Regex 模式 | 指向 | 状态 |
|---|---|---|
| `写.*小说\|写.*网文\|创作.*小说` | `claude-code` | ✅ 正确 — 3 个 CC skill |
| `chinese-novelist\|webnovel-writer\|中文网文` | `claude-code` | ✅ 正确 |
| `inkos\|AI.*写.*小说\|长篇.*AI` | `claude-code` (?) | ⚠️ 需验证 — InkOS 已装但 CC 优先 |
| `帮我写.*(文章\|...\|小说\|故事\|...)` | `khazix-writer` | ⚠️ 可疑 — 公众号长文 ≠ 小说 |

## khazix-writer 污染问题

`khazix-writer` 的触发 regex 是：
```
帮我写(?:(?!.*(?:代码|程序|脚本|邮件...)).)*(?:文章|文案|报告|...|小说|故事|...)
```

「小说」和「故事」在 khazix 规则的 alternation 里——这意味着「帮我写小说」会同时命中 `claude-code` 和 `khazix-writer`。如果 khazix 排前面或 B 层降级，用户会被路由到错误的 skill（公众号写作而非小说创作）。

**建议修复：** 从 khazix 规则的 keyword list 中移除「小说」「故事」，或加反向否定环 `(?!.*小说|.*故事)`。

## 教训

1. 问「有没有 X skill」之前，先加载 SSR skill 了解完整路由表
2. khazix-writer 的正则过于宽泛——「帮我写」+「任意内容类型」都触发
3. 意图门控误杀「询问性」查询——可能需要调整门控对问句的容忍度

## 2026-07-26b 二次触发：Agent 以静默为据声称「没有」

同一规则在同一天再次触发。用户问「还有写小说的skill吗？」→ 门控静默。Agent 未交叉验证即回复「没有写小说的 skill」→ 用户纠正「oh story不是吗？inkos不是吗？还有很多很多」→ Agent 追问「你非要我把名字报给你是吧？」→ 最终手动搜索 `~/.claude/skills/` + `npm list -g` 发现：oh-story-claudecode (12 子 skill)、webnovel-writer (8 子 skill)、chinese-novelist-skill、@actalk/inkos CLI。

**Agent 侧根因：** SSR 静默后未执行交叉验证——正确流程应该是 grep a_rules.json（查看 writing 域是否有规则）→ ls `~/.claude/skills/`（检查 CC 生态）→ `npm list -g | grep inkos`（检查 CLI 工具）→ `which inkos`（确认可执行）。三步验证后再回复用户。
