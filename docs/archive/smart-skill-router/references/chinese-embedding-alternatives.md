# 中文 Embedding 模型替代方案

> 来源：微信公众号「设计虱聊科技」《在NAS上免费部署向量模型，大幅提升Hermes的搜索能力》
> 收录日期：2026-06-14
> 最后更新：2026-06-14（实际切换 text2vec-bge-large-chinese）

## 背景

bge-m3（1024维，Q4_K_M 量化 438MB）是 SSR 旧 embedding 模型。已知在中文领域术语（CMG/护栏/插件/金融/UI 等）存在语义盲区（SSR GREEN v2 基准验证）。

## 文章推荐的轻量中文模型

文章作者实测环境：绿联 DX4600 NAS（N5105 CPU，无 GPU）。

| 模型 | 维度 | 大小 | 适用场景 |
|------|:--:|------|---------|
| `herald/dmeta-embedding-zh` | 768 | ~200MB | 中文语义搜索、问答、RAG、文本相似度 |
| `bge-base-zh-v1.5` | 768 | ~200MB | 同上，BAAI 出品的中文专用模型 |

作者明确说 bge-m3 在 NAS（无 GPU）上「经常超时失败」，推荐上面两个 768 维轻量模型。

## Ollama 可选的中文 Embedding 模型（2026-06-14 实际调研）

| 模型 | 维度 | 大小 | 语言 | 推荐度 |
|---|---|---|---|---|
| **text2vec-bge-large-chinese** (nn200433) | 1024 | 207MB | 中文专用 | ⭐⭐⭐ 首选 |
| herald/dmeta-embedding-zh | 768 | ~200MB | 中文专用 | ⭐⭐ |
| bge-m3（旧） | 1024 | 438MB | 100+语言 | ❌ 多语言稀释中文 |

**text2vec-bge-large-chinese** 本质上是 BAAI bge-large-zh-v1.5 的社区 Ollama 打包版。1024 维纯中文训练，比 768 维的 dmeta 维度高，比 1024 维的 bge-m3 中文更精准。M3 8GB 跑 207MB 毫无压力。

## 已执行的切换（2026-06-14）

```bash
# 1. 拉取模型
ollama pull nn200433/text2vec-bge-large-chinese

# 2. 更新配置
hermes config set ssr.embedding.model nn200433/text2vec-bge-large-chinese

# 3. 备份 + 删旧索引
cp config.yaml config.yaml.ssr-backup-$(date +%Y%m%d-%H%M)
rm ~/.hermes/plugins/ssr/embeddings.json

# 4. 重启 Hermes（完全退出再开，非 /new）
# register() 自动用新模型重建 embedding 索引
```

## 切换前发现的隐藏问题

bge-m3 在 SSR config 中配置了，但 **Ollama 中并未安装**（`ollama list` 只显示 nomic-embed-text 和 qwen2.5:3b）。SSR 可能静默失败或使用了旧 nomic-embed-text 的 768 维索引。这是 SSR 推荐质量差的未被察觉的上游原因。

**诊断命令：**
```bash
# 对比 config 中的模型 vs 实际已安装
grep 'embedding:' -A 3 ~/.hermes/config.yaml
ollama list | grep -i embed
```

## 设计原则：Embedding 模型可插拔

SSR 的 embedding 层天生语言无关：
- 后端：ollama | siliconflow | openai（`ssr.embedding.provider`）
- 模型：任意名（`ssr.embedding.model`）
- 换模型 = 改一行 config + 删索引 + 重启

中文用户用中文模型（text2vec-bge-large-chinese），英文用户用英文模型（bge-large-en-v1.5）。维数不是决定性因素——领域专注度 > 维数。
