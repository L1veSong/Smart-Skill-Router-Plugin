# SSR 噪声基准查询集

> 用于校准任意新 embedding 模型的 floor 阈值。
> 20 条中文日常废话（无明确 skill 意图），2026-07-03 手写。

## 查询列表

```python
NOISE_QUERIES = [
    "今天天气怎么样",
    "我喜欢吃苹果",
    "推荐一部电影",
    "你好啊，最近怎么样",
    "这个周末去哪玩",
    "晚饭吃什么",
    "给我讲个笑话",
    "你叫什么名字",
    "什么是对",
    "帮我算一下1+1",
    "能不能唱首歌",
    "你觉得人生有意义吗",
    "地球是圆的吗",
    "中国的首都是哪里",
    "NBA冠军是谁",
    "谁的男朋友",
    "今天星期几",
    "帮我查一下时间",
    "我家的猫叫什么",
    "随便聊聊",
]
```

## 使用方法

```python
import sys, json
from pathlib import Path

ssr_dir = Path.home() / ".hermes" / "plugins" / "ssr"
sys.path.insert(0, str(ssr_dir))
import __init__ as ssr

# 填充索引（离线模式下 register() 未跑）
emb_path = ssr.SSR_DIR / "embeddings.json"
emb_data = json.loads(emb_path.read_text())
emb_idx = {k: v for k, v in emb_data.items()
           if k != '_meta' and isinstance(v, dict) and 'embedding' in v}
ssr._EMBEDDING_INDEX = emb_idx

# 跑噪声基准
import numpy as np
noise_tops = []
for q in NOISE_QUERIES:
    q_emb = ssr._embed(q)
    if not q_emb:
        continue
    scores = [(ssr._cosine_sim(q_emb, e["embedding"]), n) for n, e in emb_idx.items()]
    scores.sort(reverse=True)
    noise_tops.append(scores[0][0])
    print(f"{q:<20s} {scores[0][0]:.4f} → {scores[0][1]}")

noise_tops.sort(reverse=True)
print(f"\n噪声 top-1: min={min(noise_tops):.4f}, max={max(noise_tops):.4f}")
print(f"P50={np.percentile(noise_tops,50):.4f}")
print(f"P75={np.percentile(noise_tops,75):.4f}")
print(f"P90={np.percentile(noise_tops,90):.4f}")
print(f"P95={np.percentile(noise_tops,95):.4f}")
```

## 校准公式

推荐 floor = P90 + 0.02（约等于 P95 的安全上界）。

对 Qwen3-Embedding-8B（2026-07-03 实测）：
- P75=0.557, P90=0.590
- `calibrated_floor: 0.58` — 噪声静默 17/20，信号全保留

## 信号验证查询（3 条）

```python
SIGNAL_QUERIES = [
    "帮我写一个Python脚本处理CSV文件",   # 期望命中：xlsx, codex, jupyter-live-kernel
    "如何部署我的Go程序到服务器",          # 期望命中：go-api-deploy-mac, go-api-deployment
    "帮我设计一个网页界面",               # 期望命中：image-to-code, frontend-design, ui-ux-pro-max
]
```

用同样的 embedding 索引跑信号 top-1 → 确认所有信号查询的 top-1 ≥ floor。

## 换模型时

1. 跑本噪声集，取 top-1 的 P90
2. P90 + 0.02 → 写入 `model_scores.json` 的 `calibrated_floor`
3. 跑信号验证查询，确认 top-1 ≥ floor
4. 如果 niche skill 被砍 → 降到 P75 + 0.02

## 注意

- 不同 embedding 模型 cosine 分布完全不同（本地 1024D vs API 4096D）
- **不可跨模型移植 floor 值**
- "这个周末去哪玩" → travel-skill 0.629 本质是真实意图，不是纯噪音。这类边缘 case 是 floor 的下界参考
