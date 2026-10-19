# llm_screen 安全网 + display 静默反馈 (2026-07-25)

## llm_screen 安全网

**问题：** `llm_screen: true` 时，LLM 筛查可能误判——"帮我写一篇小说"被 DeepSeek v4-pro 判定为"语境无关"，返回 `{"relevant": []}`。A 层明明命中了 31 条候选（claude-code/khazix-writer/writing-shape...），却被 LLM 一条否决。

**代码修复（`__init__.py` ~line 2480）：**

```python
if screened is not None:
    if screened or len(candidates) < 5:
        result = screened   # LLM 有结果，或 A 层太弱 → 听 LLM
    else:
        # LLM 说空但 A 层 ≥5 命中 → 不信 LLM，退回 A 层
        logger.info("[ssr] LLM 筛查否决但 A 层命中 %d ≥ 5，信任 A 层", len(candidates))
        result = candidates
```

**效果：** A 层命中 ≥5 时 LLM 筛查无一票否决权。A 层 <5 时仍听 LLM（防噪音）。

**相关配置：** `ssr.llm_screen: true`（默认 false）

## display=true 静默反馈

**问题：** `display: true` 但 SSR 静默时（意图门控拒绝 / LLM 筛查判定无关），用户看不到任何反馈——不知道 SSR 跑了、为什么不推荐。

**代码修复（两处）：**

1. **意图门控拒绝（~line 2398）：** 不再无声返回 None，注入 `[SSR] 本轮静默 (意图门控判定非任务请求)`
2. **LLM 筛查静默（~line 2502）：** 注入 `[SSR] 本轮静默 (A层 N 条候选，LLM 筛查判定语境无关)`

只在 `display: true` 时生效。`display: false` 保持完全静默。

**相关配置：** `ssr.display: true`

## 诊断命令

```bash
# A 层是否正常命中
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -3

# llm_screen 安全网触发次数
grep '信任 A 层' ~/.hermes/logs/agent.log

# 静默反馈（应看到原因）
grep '本轮静默' ~/.hermes/logs/agent.log | tail -3

# 当前配置
grep -A 3 'llm_screen\|display:' ~/.hermes/config.yaml | grep 'ssr\|llm_screen\|display'
```
