# SSR 噪声模式与升级路线

> 2026-07-22 会话 — 重启后状态诊断 + 精准度评估 + 升级路径全景

## 已知 Embedding 噪声模式

### Qwen3-Embedding-8B: nature-citation + storage-analyzer 误绑

日志复现（2026-07-03，同一会话 3 次）：

```
B 层命中: ['nature-citation', 'storage-analyzer', ...]  ×3
```

两个 skill 语义零相关：
- `nature-citation` — Nature 期刊引用格式（学术写作）
- `storage-analyzer` — macOS 磁盘清理（系统工具）

**根因**：Qwen3-Embedding-8B 对中文领域术语语义区分不足。两个 skill 的 description 可能共享「分析」「数据」等通用中文词 → embedding 向量距离过近。

**影响**：B 层 embedding 匹配时这对总是同时出现。`confidence_threshold: 0.62` 会过滤但不确定是否每次都能拦。

**缓解方案**（按优先级）：
1. 换 embedding 模型到 bge-m3（中文 benchmark 表现更好）
2. 调高 `confidence_threshold` 到 0.65-0.68
3. A 层加负面规则排除这对同时出现

### 通用噪声风险

| 类型 | 举例 | 原因 |
|------|------|------|
| 中英混合查询 | "帮我 debug 一下这个 bug" | embedding 对 code-switching 敏感度低 |
| 短查询 (< 5 字) | "写代码"、"做视频" | embedding 向量稀疏，匹配噪声大 |
| 小众领域术语 | 量化金融、游戏开发 | 训练数据少，语义向量不准 |

## 当前 SSR 升级路径全景

### 一、零代码改动（改配置即生效）

| 改动 | 命令 | 效果 | 风险 |
|------|------|------|------|
| 开 `auto_gen_rules` | `hermes config set ssr.auto_gen_rules true` | A 层 12→200+ 条，覆盖率 12%→~100% | auto-gen 规则质量参差，可能带噪声；source 标记为 auto-gen 可单独回滚 |
| 换 embedding 模型 | 改 `ssr.embedding.model` 为 bge-m3 | 降中文噪声，提升 benchmark 准确率 | 需确认硅基流动有 bge-m3；重建 embeddings.json |
| 调 `confidence_threshold` | `hermes config set ssr.confidence_threshold 0.65` | 压低 B 层噪声 | 多漏一些正确推荐 |
| 调 `similarity_floor` | 改 `ssr.similarity_floor` | 过滤低分 embedding 匹配 | 同上 |

### 二、A 层手工优化

- 扩充覆盖：高频但未覆盖的领域（金融 B 仓、MCP、部署等）
- 收紧正则：现有 12 条规则的 regex 避免过于宽泛
- 加负面规则：hard-code 排除已知噪声对

### 三、架构升级（改代码）

| 方向 | 效果 | 代价 |
|------|------|------|
| reranker 二次排序 | B 层 top-N 再用 LLM 筛一轮 | 多一次 API 调用，延迟 +30% |
| 用户反馈闭环 | 记录用户实际加载的 skill → 纠正 embedding 盲区 | 需周级别数据积累 |
| multi-embedding ensemble | 两个 embedding 模型取交集 | API 成本翻倍 |
| LLM screen 重开 | `llm_screen: true`（v2.1.1 关闭了） | 延迟增加，但精准度提升 |

### 推荐升级顺序

```
1. 开 auto_gen_rules → 观察 1-2 天噪声率
2. 噪声可接受 → 保留；不可接受 → 关掉或加过滤
3. 换 bge-m3 embedding（如硅基流动可用）
4. 微调 confidence_threshold 到 0.65
5. 长期：用户反馈闭环 + reranker
```

## A 层 vs B 层分工与精准度

```
A 层（关键词精确匹配）
  - 12 条规则，25 个 skill，覆盖率 ~12%
  - regex 命中 → 100% 准确，零延迟，零 API 成本

B 层（embedding 语义匹配）
  - Qwen3-Embedding-8B，4096 维
  - confidence_threshold: 0.62 过滤低分
  - 55% benchmark 准确率（裸 embedding，见 bge-m3-embedding-accuracy.md）
  - 中文领域术语有盲区

策略：保守优先
  - A 层命中 → 必对
  - B 层高分 → 大概率对（但有已知噪声如 nature-citation+storage-analyzer）
  - 不确定 → 不推
  - 代价：覆盖率不足，该推的没推
```

## 相关 Reference

- 重启诊断 → `post-restart-checklist.md`
- B 层调试 → `ssr-b-layer-troubleshooting.md`
- Embedding 对比 → `embedding-model-comparison-20260623.md`
- 中文 benchmark → `chinese-embedding-benchmark.md`
- 元对话正则审计 → `ssr-meta-convo-regex-audit.md`
