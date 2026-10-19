# LLM Gate 失败记录

> 2026-06-21 会话实测

## 问题

想用 B 层 LLM 做轻量 gate：判断用户消息"需要 skill 吗"→ YES/NO。门控 Embedding 噪音。

## 测试结果

### DeepSeek v4-pro (thinking=enabled)

- max_tokens=80: reasoning_content 吃掉全部 80 token，content 为空
- max_tokens=200: reasoning=366 字，content 为空
- max_tokens=400: reasoning=144 字，content 开始输出但角色混乱（在设计仪表盘而非判断）
- 即使 prompt 要求只输出 YES/NO，模型仍生成长篇 reasoning + 设计建议
- `extra_body: {"thinking": {"type": "disabled"}}` 不生效

### qwen3.5:9b (Ollama)

- max_tokens=5: 全部 5 token 被 `reasoning` 占用，content 为空
- max_tokens=50: 同样 reasoning 吃光，content 为空
- Ollama 返回 `"reasoning": "Thinking Process:\n\n1. Analyze..."` + `"content": ""`

### 根因

两个模型都是 thinking/reasoning 架构。max_tokens 上限同时限制 reasoning_content + content。reasoning 天然比 answer 更占 token，导致 content 永远吃不到配额。

## 解决方案

放弃 LLM gate，改用 A 层正则门控：
- A 层零命中 → 全层静默（噪音归零）
- A 层有命中 → 放行 Embedding 补充
- A 层从 6 条扩展到 30 条精确中文规则

详见 `~/.hermes/plans/ssr/2026-06-21_180000-noise-gate.md`
