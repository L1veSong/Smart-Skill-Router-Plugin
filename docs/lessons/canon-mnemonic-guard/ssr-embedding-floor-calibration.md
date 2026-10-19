# SSR Embedding Floor 校准方法论

> 2026-07-03 实战：Qwen3-Embedding-8B cosine 被压缩到 0.50-0.75 窄带，`calibrated_floor: 0.25` 形同虚设，A 层零可观测性。

## 问题

SSR A 层 embedding 路径始终无日志输出。诊断发现：

1. **floor 0.25 = 没有 floor。** Qwen3-Embedding-8B 的 cosine 分布被压缩到 0.50-0.75。0.25 意味着 86-100% 的 skill 通过 embedding 门槛，A 层完全失去过滤作用，所有决策交给 B 层 LLM。
2. **零可观测性。** `_match_a_layer()` 内部没有任何 logger 调用——命中/未命中都是静默的。
3. **model_scores.json 的 `overall: 5` 查表 → floor 0.25。** 有极查表映射对高压缩模型不适用。

## 根因

`_SCORE_FLOOR_MAP` 映射：

```python
_SCORE_FLOOR_MAP = {5: 0.25, 4: 0.30, 3: 0.35, 2: 0.40, 1: 0.45}
```

score=5 被映射到 0.25。但 Qwen3-Embedding-8B（4096 维 API 模型）的 cosine 分布与本地小模型完全不同——最低分也在 0.39 以上。

## 校准方法

### Step 1: 跑噪声基准

用 20 条日常废话（无明确 skill 意图）测噪声 top-1 cosine 分布：

```
"今天天气怎么样" "我喜欢吃苹果" "推荐一部电影" "晚饭吃什么"
"给我讲个笑话" "你叫什么名字" "地球是圆的吗" ...
```

### Step 2: 算分位数

```python
import numpy as np
noise_tops = [0.5368, 0.4390, 0.5417, ...]  # 20条噪声的 top-1
print(f"P75={np.percentile(noise_tops,75):.4f}")   # 0.557
print(f"P90={np.percentile(noise_tops,90):.4f}")   # 0.590
print(f"P95={np.percentile(noise_tops,95):.4f}")   # 0.598
```

### Step 3: 候选 floor 对比

用 3 条典型信号查询验证 recall：

| floor | 噪声静默 | 信号通过 | 推荐 |
|-------|---------|---------|------|
| 0.55  | 14/20   | 3/3     | 偏松 |
| 0.58  | 17/20   | 3/3     | ✅ 推荐 |
| 0.60  | 19/20   | 3/3     | 偏紧 |
| 0.63  | 20/20   | 3/3     | 太紧 |

### Step 4: 写入 model_scores.json

在对应模型条目加 `calibrated_floor` 字段：

```json
"Qwen3-Embedding-8B": {
    ...
    "calibrated_floor": 0.58,
    ...
}
```

无极模式：`_similarity_floor()` 检测到 `calibrated_floor` → 直接返回，跳过有极查表。

### Step 5: 加 A 层日志

```python
# _match_a_layer() 末尾
if result:
    logger.info("[ssr] A 层命中: %d 条 (%d kw + %d emb) → %s", ...)
else:
    logger.debug("[ssr] A 层无命中")
```

### Step 6: 验证

1. 重启 Hermes，`grep "自动 floor" agent.log` 确认无极模式生效
2. 发真实任务，确认 `[ssr] A 层命中` 出现
3. 跑 `ssr_scoring_benchmark.py --mode embedding` 验证噪音静默 ≥18/20

## 坑点

- **不同 embedding 模型 cosine 分布完全不同。** 本地 bge-m3(1024D) 和 API Qwen3-8B(4096D) 不可共用同一 floor。
- **有极查表对 API 模型不适用。** `overall: 5 → 0.25` 是给本地模型设计的。
- **必须用该模型自己的噪声分布校准。** 不能从其他模型移植 floor 值。
- **0.58 可能偏紧。** 如果 niche skill 被砍，降到 0.55。P75=0.557 是安全下界。

## 本次实测数据（Qwen3-Embedding-8B, 2026-07-03）

噪声 top-1 分布：min=0.3924, max=0.6291, P50=0.5325, P75=0.5569, P90=0.5900

信号 top-1：Python CSV=0.6454, Go部署=0.7042, 网页设计=0.7418

选 floor=0.58：噪声静默 17/20，信号全通过。
