# 门控 Prompt 优化基准 (2026-06-23)

## 测试方法

20 条噪音 + 15 条信号，DeepSeek v4-pro，thinking: disabled。

## 默认 prompt

Does this user message need an AI skill? Answer only YES or NO.

噪音拦截: 95% (19/20) | 信号放行: 93% (14/15)
漏检: "今天天气怎么样" 误判 YES。漏放: "部署网站到Vercel" 误判 NO。

## 优化 prompt

Determine if this message needs a specialized AI skill (code, design, analysis, research, data processing, planning, deployment, debugging, writing, etc.).

Needs skill (YES): user wants a specific task done - building, creating, analyzing, fixing, searching, planning, computing, generating, deploying. No skill needed (NO): pure conversation, chitchat, greetings, simple confirmations, emotional expressions, small talk.

Answer only YES or NO.

噪音拦截: 100% (20/20) | 信号放行: 93% (14/15)
漏放: "发微信给示例用户A" 误判 NO。

## 结论

噪音 +5pp，信号持平。配置到 ssr.intent_gate.prompt，不硬编码。测试后再落地，不硬编 prompt。
