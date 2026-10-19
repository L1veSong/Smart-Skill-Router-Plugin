# SSR A 层静默失败诊断模式

> 记录于 2026-07-03。诊断方法而非特定环境状态。

## 症状组合

出现以下**全部**症状 → A 层 embedding 管线静默死亡：

- agent.log 中零条 `A 层命中`（所有会话、所有重启后持续性为零）
- 所有推荐走 B 层（`B 层命中` 日志正常但 `A 层命中` 从未出现）
- benchmark 超时（`ssr_scoring_benchmark.py --mode all` 180s timeout）
- `自动 floor` 日志仍正常输出（**误导信号** — 见下）
- A 层规则数正常（100 条加载），注册信息正常（423 skill, emb: 423）

## 根因链

```
_match_a_layer()
  ├── keyword path → _match_a_layer_keyword() → 100 条规则无关键词命中 → returns None
  └── embedding path → _embed() 返回 None（API key 失效/端点挂/超时）
      → 整个 embedding 分支被跳过
      → emb_result = []
      → 合并后 result 为空
      → A 层返回 None
      → 坠落 B 层
```

## 关键误导信号

`自动 floor` 日志来自 `_similarity_floor()`，该函数是**纯本地配置查询**：

```python
# _similarity_floor() 只做: 读 config.yaml + 读 model_scores.json
# 从未调用 embedding API
# 看到此日志 ≠ embedding API 存活
```

日志示例（看起来正常，实际 API 已死）：
```
[ssr] 自动 floor (有极): Qwen3-Embedding-8B (得分 5) → 0.25
```

此日志仅证明 `model_scores.json` 可读 + config 中写了模型名。**不**证明 key 有效。

## 诊断步骤

### Step 1: 确认零命中

```bash
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -20
# 零条 → 继续
```

### Step 2: 直测 embedding API

```bash
# SiliconFlow
curl -s --max-time 10 https://api.siliconflow.cn/v1/embeddings \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-Embedding-8B","input":"测试"}'
# "Api key is invalid" → 死 key
# 返回 embedding 向量 → key 正常，问题在别处

# OpenAI 兼容端点
curl -s --max-time 10 <base_url>/embeddings \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"<model>","input":"测试"}'
```

### Step 3: 确认配置

```bash
grep -A 6 'ssr.embedding\|embedding:' ~/.hermes/config.yaml | head -20
# 确认 api_key / base_url / model / provider 均有效
```

### Step 4: 验证恢复

换 key + 重启 Hermes 后，发一条真实任务查询，然后：

```bash
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -5
# 应出现匹配日志
```

## 修复

1. 去 SiliconFlow（或当前 embedding provider）生成新 API key
2. 更新 `~/.hermes/config.yaml` → `ssr.embedding.api_key`
3. 验证 key 存活（Step 2 curl）
4. 重启 Hermes
5. 发真实查询 → 抓日志确认 A 层恢复
6. 跑 benchmark 确认 embedding 裸分正常

## 不在本文档范围的

- 具体 API key 值（环境状态，不是知识）
- floor 调优（等 A 层恢复后有数据再说）
- B 层诊断（B 层正常 → 问题不在 B 层）
- keyword 路径优化（keyword 路径零命中可能也需要调整，但那是独立问题）
