# SSR 元对话检测 — 正则设计与验证

> 2026-07-03 | SSR P1 | 9/9 测试通过

## 最终正则

```python
_META_CONVO = re.compile(
    r'^/(?:moa|model|learn|skills|config|plan|goal|reset)\b|'
    r'^hermes\s|'
    r'(?:ssr|cmg|guard|canon|mnemonic|skill系统|plugin|provider|config\.yaml|\.env)'
    r'.*?(?:改|修|调|配|设置|怎么|如何|为什么|问题|bug|报错|噪音|静默|规则|匹配|阈值|推荐|怎么样)|'
    r'(?:怎么|如何|为什么|帮我|能不能|有没有|调整|修改|配置|设置|配|改|换)'
    r'.*?(?:ssr|cmg|guard|canon|mnemonic|skill系统|plugin|moa|模型|model|provider|预设|preset)',
    re.IGNORECASE
)
_STRONG_TASKS = re.compile(
    r'(设计|写|生成|部署|画|创建|构建|实现|修复|制作|开发|搭建|规划|'
    r'design|write|create|build|deploy|make|develop|implement|fix|generate|plan)',
    re.IGNORECASE
)
if _META_CONVO.search(msg):
    if not _STRONG_TASKS.search(msg):
        return False  # 静默
```

## 三轮迭代

1. 初版：`\b` 边界 + 单向正则 → "帮我改ssr"漏网，"配一下moa"漏网
2. 加安全阀：`_TASK_VERBS`（30+动词）→ "帮我" "review" 放行了不该放的
3. 终版：去 `\b`、双向正则、`_STRONG_TASKS`（仅强动作动词）→ 9/9

## 关键设计

- **双向**：`关键词→动词` + `动词→关键词`，两个方向不一样的消息都要覆盖
- **安全阀分离**：噪音过滤用 `_TASK_VERBS`（宽），元对话用 `_STRONG_TASKS`（窄）。精度要求不同。
- **去 `\b`**：中文不受 Python `\b` 影响，用上下文限制精度

## 位置

```
_intent_gate() → 极短过滤 → 元对话检测 → 噪音过滤 → LLM gate
```
元对话检测在噪音过滤之前——含 "ssr" 的消息可能不匹配噪音正则，但会触发 LLM gate 的误判。
