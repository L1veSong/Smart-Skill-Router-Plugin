# 本地模型门控测试 — 2026-06-22 实战

## think:false 参数

qwen3.5 全系的 `<think>` 标签占用 `max_tokens`。Ollama `/api/generate` 顶层参数 `think: false` 关闭思考：

```python
resp = httpx.post(f"{OLLAMA_URL}/api/generate",
    json={"model": model, "prompt": prompt, "stream": False, "think": False},
    timeout=timeout)
```

错误放法: `options.think`（无效）, `raw: true`（只跳模板，不关思考）, `num_predict`（被 think 吃光）

## DeepSeek v4-pro thinking:disabled

非 ollama 路径加 `"thinking": {"type": "disabled"}`：

```json
{"model": "deepseek-v4-pro", "messages": [...], 
 "max_tokens": 3, "temperature": 0, "thinking": {"type": "disabled"}}
```

## 模型大小 vs 可用内存

8GB Mac 实测：
- qwen3.5:9b Q4 6.6GB → 按装不下 → swap 风暴
- qwen3.5:4b Q4 3.4GB → 擦边，macOS 压缩勉强跑
- qwen3.5:2b Q4 ~2GB → 轻松

诊断：`vm_stat | head -4` 算空闲页 → ×16384 = 可用内存。`ollama ps` 看当前加载。

## 门控 prompt

英文 prompt 对所有模型更稳定：

```
Does this user message need an AI skill to complete the task? Answer only YES or NO.
Message: {msg}
Answer:
```

中文 prompt 某些模型答 "否" → 不含 "YES" → 判 NO → 全拦。
