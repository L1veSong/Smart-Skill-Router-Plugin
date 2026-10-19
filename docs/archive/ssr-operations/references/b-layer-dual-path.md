# SSR B 层双路径架构（2026-07-22）

## 背景

SSR B 层有两条完全独立的匹配路径，互为降级。

## 路径 A：Embedding 语义匹配

```
用户消息 → _prefilter_skills() → 223→20 候选 → _embed(候选) → 余弦相似度 → top-N
```

- 后端：siliconflow Qwen3-Embedding-8B
- 优点：token 消耗低、速度快、有相似度分数
- 当前状态：**全挂** — 向量获取失败

## 路径 B：LLM 直推匹配

```
用户消息 → _match_b_main() → 全量 438 skill prompt → deepseek-v4-pro → JSON 输出
```

- 后端：`b_layer.provider: main`（当前 deepseek-v4-pro）
- 优点：不依赖 embedding API，任何 LLM 都能跑
- 缺点：token 消耗大、无预过滤、无相似度分数

## 双路径决策逻辑

```python
# __init__.py line 1270-1278
if provider == "main":
    result = _match_b_main(user_message)      # 路径 B
elif provider == "ollama":
    result = _match_b_ollama(prompt)           # 路径 A (本地)
elif provider in ("openai", ...):
    result = _match_b_openai(user_message)     # 路径 A (远程)
```

## 当前生产状态

- embedding 路径：**全挂**（siliconflow API 不通）
- LLM 直推路径：**运行中**（deepseek-v4-pro 暴力匹配 438 skill）
- 现象：benchmark 全红（测试只测 embedding），但 `[SSR] [P]` 推荐仍在产出

## 影响

1. **confidence_threshold 失效** — LLM 路径无相似度分数，`_compute_confidence` 返回 1.0
2. **token 消耗高** — 438 个 skill description 入 prompt
3. **无预过滤** — 全部 skill 都参与匹配，噪音 skill 可能被推荐
4. **新 skill 自动可用** — LLM 直推看到的 skill 列表来自 `_SKILL_INDEX`，不依赖 `embeddings.json`

## 恢复 embedding 的验证步骤

```bash
# 1. 测试 siliconflow API
curl -s https://api.siliconflow.cn/v1/embeddings \
  -H "Authorization: Bearer $(cat ~/.hermes/tokens/siliconflow)" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-Embedding-8B","input":"test"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['data'][0]['embedding']) if 'data' in d else d)"

# 2. 如果 API 恢复 → 重启 Hermes → _sync_embeddings 自动增量同步
# 3. 验证：test_ssr.py 的 Embedding 测试变绿
```

## 新 skill 入索引

`_sync_embeddings()` 在启动时对比 `_SKILL_INDEX` 和 `embeddings.json`，自动嵌入新增 skill。前提是 embedding API 可用。

当前 `trip-website-generator`、`trip-planner-generator` 均不在 `embeddings.json` 中，等待 API 恢复后自动入索引。
