# qwen3-embedding:4b — bge 与 8b 之间

2026-06-22 会话发现：qwen3-embedding 有三个规格，4b 是中间档。

| 模型 | 维度 | 大小 | 8GB 适配 |
|------|------|------|:--:|
| bge-large-zh-v1.5 | 1024 | 202MB | ✅ |
| qwen3-embedding:4b | 2560 | 2.5GB | ⚠️ 紧 |
| qwen3-embedding:8b | 4096 | 4.7GB | ❌ |

4b 在 8GB 机器上需 2.5GB + bge 202MB ≈ 2.7GB。空闲 3.2GB → 勉强可装。

**安装：** `ollama pull qwen3-embedding:4b`
**切换：** 改 `ssr.embedding.model` → `rm embeddings.json` → 重启 Hermes

2560 维是 1024 的 2.5 倍，语义区分度应有明显提升。
