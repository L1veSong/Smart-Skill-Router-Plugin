# ~/.agents/skills/ 嵌入索引缺口 + B层幻觉风险

## 问题

2026-07-22 实战发现：`trip-website-generator`、`trip-planner-generator` 等 skill 存在于 `~/.agents/skills/` 但不在 `embeddings.json`（438 条索引中没有它们）。

**这不是一个 skill 的问题——是整个 `~/.agents/skills/` 目录的嵌入覆盖缺口。**

## 影响链

```
embedding API 正常时:
  用户消息 → A层匹配 → B层预过滤(embedding cosine, top-N) → skill 不在索引中 → 漏掉

embedding API 挂时:
  用户消息 → A层匹配 → B层 LLM直推(全量438 skill prompt) → 可能推不存在的 skill 名
```

当前 B 层能推到 `trip-website-generator` 纯靠 LLM 直推模式（deepseek-v4-pro 把全量 skill 列表塞 prompt，line 2021-2029）。一旦 embedding 路径恢复（预过滤截断 top-N），这些 skill 会被静默漏掉。

## B 层 LLM 直推的幻觉风险

`_match_b_main()` line 2021-2029：当 embedding 不可用时，**438 个 skill 名全量塞入 prompt**，无预过滤。LLM 可能返回：
- 不存在的 skill 名（幻觉）—— prompt 中没给它验证手段
- 引号包围的名称（`"trip-website-generator"`）——格式异常但能通过解析
- 模糊匹配的名称（用户说"旅行网站"但 skill 不叫这个名字）

### 如何验证 B 层推荐是否有效

```bash
python3 -c "
import json
with open('$HOME/.hermes/plugins/ssr/embeddings.json') as f:
    emb = json.load(f)
index_names = list(emb.keys())
# 检查 B 层返回的 skill 名是否真的在索引中
targets = ['trip-website-generator', 'claymorphism', 'planning-pipeline']
for t in targets:
    print(f'  {\"✅\" if t in index_names else \"❌\"} {t}')
print(f'索引总数: {len(index_names)}')
"
```

## 确认 `~/.agents/skills/` 是否被扫描

`_auto_gen_a_rules()` 从 `_SKILL_INDEX` 读 skill description 生成规则。如果 `_SKILL_INDEX` 的构建源码不扫描 `~/.agents/skills/`，则需要：
1. 扩展 `_build_skill_index()` 扫描路径
2. 重建 `embeddings.json`

```bash
# 找到 _build_skill_index 的扫描路径
grep -n 'skills\|_SKILL_INDEX\|agent.*skill\|walk.*skill' ~/.hermes/plugins/ssr/__init__.py | head -15
```

## 重建嵌入索引（将 ~/.agents/skills/ 纳入）

```bash
# 备份当前索引
cp ~/.hermes/plugins/ssr/embeddings.json ~/.hermes/plugins/ssr/embeddings.json.bak.$(date +%m%d%H%M)

# 删除索引 → 重启 Hermes → SSR 自动重建（覆盖所有扫描路径）
# 前提：__init__.py 不缓存旧索引，或改代码强制全量重建
```

**⚠️ 风险：embeddings.json 38.7MB，重建需要全量调用 embedding API（硅基流动 Qwen3-Embedding-8B），耗时约 5-10 分钟，消耗 token。**

## 重建后验证

```bash
python3 ~/.hermes/plugins/ssr/test_ssr.py 2>&1 | grep -A 5 "GREEN\|embedding\|Embedding"
```
