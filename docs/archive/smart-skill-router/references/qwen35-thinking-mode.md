# thinking 模型门控兼容性

> 2026-06-22 实战 | 影响: intend_gate + benchmark gate 测试

## 问题

qwen3.5/v3 (Alibaba)、DeepSeek v4-pro 等 thinking 模型默认启动推理模式。门控任务只需 YES/NO (1 token)，但 thinking 模式在输出前消耗 200+ token。

## 两个分支的修复

### ollama 本地模型

```python
# /api/generate 端点
json={"model": "qwen3.5:4b", "prompt": "...", "think": False}
```

- `think` 是**顶层参数**，不放 `options` 里
- 放 `options.think` 被 ollama 静默忽略 → 仍然 thinking → 空输出
- `raw: true` 无效（只跳过 ollama 模板，不改模型内建 thinking）

### 非 ollama (DeepSeek/OpenAI)

```python
# /v1/chat/completions 端点
json={"model": "deepseek-v4-pro", "messages": [...], "thinking": {"type": "disabled"}}
```

### 英文 prompt 必选

中文 prompt 下 qwen3.5:4b 答「否/不需要」→ 不含 "YES" → 判 NO。
英文 "Answer only YES or NO. Does this user message need an AI skill?" → 准确。

## 8GB 机器门控模型

| 模型 | 大小 | 可用 |
|------|------|:--:|
| qwen3.5:9b Q4 | 6.6GB | ❌ 完全装不下 |
| qwen3.5:4b Q4 | 3.4GB | ⚠️ 勉强(macOS压缩) |
| qwen3.5:2b Q4 | ~2GB | ✅ |

4b 做门控 YES/NO 够用但偏保守（19/20噪音, ~10/28信号通过）。
更好的门控需 8b+ 或 API 模型。
