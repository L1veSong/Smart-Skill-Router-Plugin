# llm_screen 安全网 + display 静默反馈 (2026-07-25)

源自与 ssr-operations 同一会话。代码修改在 `~/.hermes/plugins/ssr/__init__.py`。

## llm_screen 安全网

当 `llm_screen: true` 时，LLM 筛查返回 `[]`（空）但 A 层 ≥5 命中 → 不信任 LLM 判定，退回 A 层结果。

## display=true 静默反馈

`display: true` 时，SSR 静默（意图门控拒绝 / LLM 筛查判定无关）会注入可见的反馈消息，告诉用户"为什么没推荐"。

## 相关配置

```yaml
ssr:
  display: true
  llm_screen: true
```

## 诊断

```bash
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -3
grep '信任 A 层' ~/.hermes/logs/agent.log
grep '本轮静默' ~/.hermes/logs/agent.log | tail -3
```
