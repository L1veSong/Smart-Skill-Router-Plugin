# SSR A 层离线诊断方法

> 2026-07-03 实战：SSR `register()` 正常但 A 层零命中。通过外部注入内部状态做离线诊断，定位到 floor 问题。

## 使用场景

SSR 插件注册正常、日志无报错，但 A 层始终不产出推荐（`[ssr] A 层命中` 不在 agent.log 中出现，或 benchmark 信号命中异常低）。

## 诊断流程

### Step 1: 加载 SSR 模块 + 填充内部状态

```python
import sys, json
from pathlib import Path

ssr_dir = Path.home() / ".hermes" / "plugins" / "ssr"
sys.path.insert(0, str(ssr_dir))
import __init__ as ssr

# 关键：register() 初始化了 _EMBEDDING_INDEX（全局变量），
# 但离线导入时不走 register() → 必须手动填充
emb_path = ssr.SSR_DIR / "embeddings.json"
emb_data = json.loads(emb_path.read_text())
emb_idx = {k: v for k, v in emb_data.items()
           if k != '_meta' and isinstance(v, dict) and 'embedding' in v}
ssr._EMBEDDING_INDEX = emb_idx
```

### Step 2: 测单个查询的真实 embedding + cosine 分布

```python
q = "帮我写一个Python脚本处理CSV文件"
q_emb = ssr._embed(q)
if not q_emb:
    print("❌ _embed() 返回 None — embedding API 不可达")
else:
    scores = [(ssr._cosine_sim(q_emb, e["embedding"]), n) for n, e in emb_idx.items()]
    scores.sort(reverse=True)
    print(f"top-1: {scores[0][0]:.4f} → {scores[0][1]}")
    print(f"top-5: {[(f'{s:.4f}',n) for s,n in scores[:5]]}")
    floor = ssr._similarity_floor()
    above = sum(1 for s,_ in scores if s >= floor)
    print(f"≥floor({floor}): {above}/{len(scores)} 条")
```

### Step 3: 测 `_match_a_layer()` 完整链路

```python
result = ssr._match_a_layer("帮我写Python脚本处理CSV")
if result:
    print(f"A 层命中: {len(result)} 条 → {[r['name'] for r in result[:5]]}")
else:
    print("❌ A 层零命中 — 检查 floor 或 embedding 索引")
```

### Step 4: 测 floor 实际值

```python
floor = ssr._similarity_floor()
print(f"_similarity_floor() = {floor}")
# 期望看到 logger 输出："[ssr] 自动 floor (无极): Qwen3-Embedding-8B → 0.580"
# 如果看到 "(有极)" 或值不对 → model_scores.json 的 calibrated_floor 未生效
```

### Step 5: 噪声基准对比

用 20 条中文废话测噪声 top-1 分布（详见 `references/noise-baseline-queries.md`），与信号 top-1 对比——确认信号/噪声分离度。

## 常见故障模式

| 症状 | 可能原因 | 检查方法 |
|------|---------|---------|
| `_embed()` 返回 None | API key 失效/网络不通 | `_embed("测试")` 直接调用 |
| `_EMBEDDING_INDEX` 为空 | embeddings.json 不存在或格式错 | `ssr._load_embedding_index()` |
| embedding 相似度全 > 0.50 | 高压缩模型（如 4096D API 模型）的正常行为 | 噪声基准测试 |
| floor 值还是 0.25 | 有极查表未覆盖，无极校准未设 | `_similarity_floor()` 日志 |
| A 层无日志但 B 层正常 | `_match_a_layer()` 缺少 logger（v2.2.0 之前） | 升级到 v2.2.0+ |

## 局限性

- 离线注入 `_EMBEDDING_INDEX` 绕过了 `register()` / `_sync_embeddings()` 的增量逻辑，不做索引持久化
- 只在当前 Python 进程内有效，每次重新导入需再次填充
