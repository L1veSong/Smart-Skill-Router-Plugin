# Phase 2: Embedding 语义匹配架构

> 创建时间: 2026-06-09
> 对应计划: `~/.hermes/plans/ssr/precision-upgrade/task_plan.md`
> 当前状态: 规划中

## 背景

A 层 auto-gen 关键词匹配准确率仅 10%（基准测试 1/10）。从 skill description 提取的英文单词和中文双字词与用户自然语言几乎不匹配——"茅台股票"不会命中 `tushare-finance`，"帮我设计导航栏"不会命中 `ui-ux-pro-max`。

关键词方案已到天花板。Phase 2 用语义 embedding 替代。

## 多后端设计（用户明确要求）

用户纠正（2026-06-09）：SSR 是开源项目，不能绑定 SiliconFlow（"那我ssr开源后其他用户也要用硅基流动？"）。

**正确做法：和 B 层一样的多后端模式。**

### config.yaml 扩展

```yaml
ssr:
  embedding:
    provider: ollama           # 默认
    ollama:
      model: nomic-embed-text  # 768维，274MB
      timeout: 10
    siliconflow:
      model: BAAI/bge-large-zh-v1.5  # 1024维，免费
      api_key: sk-xxxxx
    openai:
      model: text-embedding-3-small   # 付费
      api_key: sk-xxxxx
```

### 后端对比

| 后端 | 模型 | 维度 | 成本 | 依赖 | 适用 |
|------|------|------|------|------|------|
| ollama | nomic-embed-text | 768 | 免费 | 本地 Ollama | 默认，通用 |
| siliconflow | bge-large-zh-v1.5 | 1024 | 免费 | API key | 国内用户网络好 |
| openai | text-embedding-3-small | 1536 | $0.02/1M tokens | API key | 已有 OpenAI key |

### 代码结构

```python
def _embed(text: str) -> list[float]:
    """多后端 embedding 路由。"""
    provider = _embedding_provider()  # ollama|siliconflow|openai
    if provider == "ollama":
        return _embed_ollama(text)
    elif provider == "siliconflow":
        return _embed_siliconflow(text)
    elif provider == "openai":
        return _embed_openai(text)

def _build_embedding_index() -> dict:
    """启动时向量化全部 skill description → embeddings.json"""
    index = {}
    for name, info in _SKILL_INDEX.items():
        desc = info.get("description", "")
        if desc:
            vec = _embed(desc)
            index[name] = {"embedding": vec, "desc": desc, "phase": _infer_phase(desc)}
    with open(SSR_DIR / "embeddings.json", "w") as f:
        json.dump(index, f)
    return index

def _match_by_embedding(user_message: str, top_k: int = 30) -> list[dict]:
    """用 embedding 替代关键词匹配。"""
    user_vec = _embed(user_message)
    # 余弦相似度排序
    scores = []
    for name, info in _EMBEDDING_INDEX.items():
        sim = cosine_similarity(user_vec, info["embedding"])
        scores.append((sim, name, info))
    scores.sort(reverse=True)
    # Top-K 候选 → 喂给 B 层精排
    return [{"name": n, "phase": i["phase"]} for _, n, i in scores[:top_k]]
```

## 启动流程变更

```
register():
  1. _build_skill_index()       # 已有
  2. _build_embedding_index()   # 新增：向量化全部 skill
  3. _load_a_rules()            # 保留（B 层升级规则保留）
  4. _auto_gen_a_rules()        # 保留但降级为冷启动种子
```

## 匹配流程变更

```
pre_llm_call:
  1. A 层 embedding 匹配 (替代关键词) → Top-30 候选
  2. B 层 main 模型精排 → 最终推荐
  3. B→A 升级机制保留
```

## 关键教训

### 不要绑定单一供应商

SSR 的 embedding 层必须像 B 层一样支持多后端。默认用 Ollama（本地免费），用户可切到 SiliconFlow（国内网络好）或 OpenAI（有余额）。这是开源项目的基本要求——不能假设用户有某个特定 API key。

### 140MB GGUF 可通过 hf-mirror 下载

nomic-embed-text 的 `ollama pull` 在某些网络环境下失败（TLS 握手超时 registry.ollama.ai）。hf-mirror.com 提供 Q8_0 GGUF（~140MB），下载后用 `ollama create` 导入即可。

```bash
curl -L -o ~/nomic-embed-text.Q8_0.gguf \
  "https://hf-mirror.com/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q8_0.gguf"
ollama create nomic-embed-text -f - <<'EOF'
FROM ~/nomic-embed-text.Q8_0.gguf
EOF
```

### B 层已有预过滤，不是 294 全量

精度升级计划假设 B 层面对 294 个 skill，但代码 `_prefilter_skills()` 已用关键词预过滤到 top-20。Phase 2 的 "Token 成本降低 90%" 被高估——已是 20→N，embedding 的价值是提升匹配质量，不是降成本。
