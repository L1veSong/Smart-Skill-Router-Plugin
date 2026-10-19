# SSR Phantom Embedding 诊断 (2026-07-04 实战)

## 症状

`embeddings.json` 中存在条目：`description: N/A` 或 `?`，但 embedding 向量维度正常（如 4096）。

这些条目是旧索引残留——它们有有效维度的随机向量，但没有任何语义关联。余弦相似度对任何查询都会返回随机值，floor 0.58 滤不掉大部分噪音 → 伪匹配。

**本会话实例：** `using-superpowers` 条目 `desc=N/A, model=?, dims=4096`，连续 3 次被错误匹配到完全不同的 SSR 内部询问（"benchmark测过了吗""现在信号命中率怎么样""现在信号和噪音怎么样"）。

## 诊断命令

```python
import json, os

EMB = os.path.expanduser("~/.hermes/plugins/ssr/embeddings.json")
with open(EMB) as f:
    d = json.load(f)

bad = [k for k, v in d.items()
       if v.get("description") in ("N/A", "?", "") or not v.get("description")]

print(f"Phantom entries: {len(bad)}")
for b in bad:
    print(f"  {b}: desc={d[b].get('description')} dims={len(d[b].get('embedding', []))}")
```

## 删除

```python
import json, os

EMB = os.path.expanduser("~/.hermes/plugins/ssr/embeddings.json")
with open(EMB) as f:
    d = json.load(f)

del d["using-superpowers"]  # 替换为实际 phantom 条目名

with open(EMB, "w") as f:
    json.dump(d, f)

print(f"Remaining: {len(d)} skills")
```

## 预防

Hermes 重启后 SSR `register()` 会重建索引，phantom 条目会被正常覆盖。但如果在会话中手动删了 skill 或改了 description，旧 embedding 不会被重建 → phantom 残留。

**根治：** `_sync_embeddings()` 应检测 `description` 字段缺失的条目并自动清除。当前需手动诊断+删除。
