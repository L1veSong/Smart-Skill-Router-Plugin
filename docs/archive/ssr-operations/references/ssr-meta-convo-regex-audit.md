# SSR 元对话正则盲区审计 (2026-07-04 实战)

## 症状

SSR 内部询问（"现在信号命中率怎么样""benchmark 测过了吗"）未被 `_META_CONVO` 正则拦截，进入完整 embedding 匹配 → 浪费 API 调用 + 产生噪声推荐。

## 根因

旧正则（v2.1）的领域词汇表只覆盖 `ssr|cmg|guard|canon|mnemonic|skill系统|plugin|provider|config.yaml|.env`，但不认识 SSR 运维的日常词汇：

| 缺失词 | 典型问题 |
|--------|----------|
| 信号 | "现在信号怎么样" |
| 命中率 | "信号命中率怎么样" |
| benchmark | "benchmark测过了吗" |
| A层/B层 | "A层命中率""B层怎么样" |
| 准确率 | "推荐准确率" |
| 推荐质量 | (同上) |
| embedding/嵌入 | "embedding模型怎么样" |

旧正则第二分支（`怎么|如何|为什么...配|改|换`）要求右侧有 SSR 关键词——但"信号命中率怎么样"不含 `ssr|cmg|guard` 等词 → 两个分支都匹配失败 → 放行。

## 修复（2026-07-04）

扩展 `_META_CONVO` 正则，domain 关键词列表补全 SSR 运维词汇：

```python
_META_CONVO = re.compile(
    r'^/(?:moa|model|learn|skills|config|plan|goal|reset)\b|'
    r'^hermes\s|'
    r'(?:ssr|cmg|guard|canon|mnemonic|skill系统|plugin|provider|config\.yaml|\.env|'
    r'信号|命中率|benchmark|准确率|推荐质量|A层|B层|embedding|嵌入)'  # ← 新增
    r'.*?(?:改|修|调|配|设置|怎么|如何|为什么|问题|bug|报错|噪音|静默|规则|匹配|阈值|推荐|怎么样|测|跑|验证|效果|高|低|对|准不准)|'  # ← 新增测/跑/验证/效果/高/低/对/准不准
    r'(?:怎么|如何|为什么|帮我|能不能|有没有|调整|修改|配置|设置|配|改|换)'
    r'.*?(?:ssr|cmg|guard|canon|mnemonic|skill系统|plugin|moa|模型|model|provider|预设|preset|'
    r'信号|命中率|benchmark|推荐|embedding|A层|B层)',  # ← 新增
    re.IGNORECASE
)
```

## 边界风险

"帮我写个 benchmark 测试"含 `benchmark` + `帮我` → 会被拦截。但 `_STRONG_TASKS` 安全阀检测到 `写` → 放行。如果安全阀漏过 → 误杀。

安全阀关键词：`设计|写|生成|部署|画|创建|构建|实现|修复|制作|开发|搭建|规划|design|write|create|build|deploy|make|develop|implement|fix|generate|plan`

## 验证

```python
import re

META = re.compile(...)  # 新正则

tests = [
    "现在信号命中率怎么样",    # ✅ 应拦截
    "benchmark测过了吗",       # ✅ 应拦截
    "SSR推荐准确率如何",       # ✅ 应拦截 (含 SSR)
    "A层命中率",              # ✅ 应拦截
    "帮我写个benchmark测试",   # ❌ 应放行 (含"写"=安全阀)
    "信号和噪音怎么样",         # ✅ 应拦截
]

for msg in tests:
    hit = bool(META.search(msg))
    print(f"{'✅拦截' if hit else '❌放行'} | {msg}")
```

## 相关文件

- `~/.hermes/plugins/ssr/__init__.py`: `_META_CONVO` 正则 (line ~1704)
- `~/.hermes/plugins/ssr/__init__.py`: `_STRONG_TASKS` 安全阀 (line ~1713)
