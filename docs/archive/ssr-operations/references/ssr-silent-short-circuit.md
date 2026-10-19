# SSR 极短噪音沉默拦截 (2026-07-04 实战)

## 症状

用户发"谢谢"，`[ssr]` 日志零输出 → 无法判断是被拦截了还是 hook 没触发。

## 根因

`_intent_gate()` line 1687 有硬短路：

```python
# 极短噪音直截
if len(msg) < 4:
    return False
```

"谢谢" 2 字 → `return False` → `_intent_gate` 返回 `False` → `_pre_llm_call` line 2072 看到 `False` → `return None`。拦截正确，但全程无日志。

## 修复（2026-07-04）

加一行 `logger.info`：

```python
if len(msg) < 4:
    logger.info("[ssr] 极短噪音拦截 → 静默 (%d字: %s)", len(msg), msg)
    return False
```

## 效果

- "谢谢" → `[ssr] 极短噪音拦截 → 静默 (2字: 谢谢)`
- "嗯" → `[ssr] 极短噪音拦截 → 静默 (1字: 嗯)`
- "OK" → `[ssr] 极短噪音拦截 → 静默 (2字: OK)`

## 边界

`len(msg) < 4` 的硬短路在 `noise_filter` 之前执行——即使 noise_filter 有匹配"谢谢"的正则，也不会到达。设计上合理：2-3 字消息不需要走 embedding 匹配。

`len(msg) < 3` 的短路（line 2068 `_pre_llm_call` 入口）是更早期筛选——独立于 `_intent_gate`。这条没有加日志（1-2 字消息太频繁，会刷屏）。

## 相关文件

- `~/.hermes/plugins/ssr/__init__.py`: `_intent_gate()` line 1687
