# SSR v2.1 — Gate 通用化 + 元对话检测 + 自循环

> 创建: 2026-06-23 | 基于 v2.0.0 当前基线 | 当前总分 ~70.6

## 背景

v2.0.0 已收敛三层架构（噪音白名单→keyword+embedding→LLM决策），但存在三个短板：

1. **Gate prompt 硬编码** — 放在 `__init__.py`，不同模型理解力不同，一个 prompt 不可能通用
2. **元对话噪音** — 聊 SSR/CMG/skill 系统时 gate 误判为"需要 skill"，推大量无关推荐
3. **静态推荐** — 推荐质量从安装那天就固定，不随使用习惯进化

## 分项

### P0: Gate prompt 配置化

**问题：** 当前 `_call_llm_intent()` 内 prompt 硬编码。qwen3.5:4b 信号 16/30，DeepSeek v4-pro 可能完全不同。用户换模型时 prompt 也要换。

**方案：**
```yaml
ssr:
  gate:
    prompt: "Does this user message need an AI skill? Answer only YES or NO."
    model: qwen3.5:4b
    timeout: 15s
```

- 默认 prompt 极简，适配大多数模型
- 用户可覆写（config.yaml 暴露）
- 安装时根据检测到的 provider 给出建议 prompt
- 不影响 A 层/Embedding/LLM 筛选，只影响 gate 这一环

### P1: 元对话检测（零成本噪音拦截）

**问题：** 用户聊 SSR 架构、讨论 skill 系统、问"SSR 能不能推荐"时，gate 的 LLM 判断不可靠——模型看到 "SSR" 和 "skill" 就判 YES。

**方案：** gate 前加一层纯正则预检，零 token：

```python
META_PATTERNS = [
    r'ssr.*(优化|怎么样|能不能|有没有|加载|推荐)',
    r'智配路由',
    r'(skill|插件).*(推荐|建议|命中|匹配)',
    r'(门控|gate|embedding|A层|B层).*(怎么|如何|问题)',
]
```

命中任一 → 直接静默，不走 gate LLM。

**代价：** 零。不调 API，不占 token。

**边界：** "SSR 优化后帮我设计个页面"——含元对话词但含任务意图。检测正则需排除含任务动词（设计/写/生成/部署/画）的消息。安全策略：含任务动词 → 放行。

### P2: 自循环学习

**问题：** 当前推荐纯静态。用户用了某个 skill 一百次，SSR 不知。用户习惯用 road-trip-planner 排日程，SSR 永远不推。

**三层信号：**

| 信号 | 触发 | 权重变化 |
|------|------|:--:|
| 采纳 | 用户用了 SSR 推荐的 skill | +2 |
| 手动发现 | 用户手动加载了 SSR 没推荐的 skill | +1（该场景关联此 skill） |
| 忽略 | 推荐了但用户没用 | -1 |

**数据结构（~/.hermes/plugins/ssr/usage.json）：**
```json
{
  "road-trip-planner": {
    "context_signals": {
      "日程计划": {"hits": 8, "last": "2026-06-23"},
      "每日安排": {"hits": 3, "last": "2026-06-20"}
    },
    "total_adoptions": 12,
    "total_ignores": 2
  }
}
```

**学习粒度：** 提取用户消息中 2-4 字中文短语作为 context 关键词。同 skill 同 context 命中 3 次 → 该组合权重提升。

**叠加方式：** 在 LLM 筛选前，偏好 skill 的 embedding 相似度 ×1.3。专业匹配（静态 embedding + keyword）仍然生效，偏好只在已有候选上做 boost。

**冷启动：** 零数据时退化为当前行为。越用越个人，不用不变。

### 不做的

- **嵌入富化（LLM 生成描述）** — 测试 85%→55%，反效果。弃。
- **skill 自声明（ssr_keywords frontmatter）** — 需改外部 skill，不可控。弃。
- **多 embedding 后端** — 当前 bge-large-zh-v1.5 够用。不急。

## 实施顺序

```
1. P1 元对话检测 — ✅ 已落地（_META_CONVO 正则 + _TASK_VERBS 安全阀，零 token，已启用）
2. P0 gate prompt 配置化 — ✅ 已落地（_call_llm_intent 读 intent_gate.prompt，默认英文）
3. P2 自循环 — ✅ stub 已落地（boost_skill API + preferences.json + _SESSION_RECOMMENDED）
```

## 实施记录 (2026-06-23)

### 改动文件
- `__init__.py`: +gate_prompt 参数、+meta_detection 层、+自循环模块（~80 行）
- `config.yaml`: +intent_gate.prompt、+meta_detection 段（7 条正则）
- `plugin.yaml`: 2.0.0 → 2.1.0
- 版本号: 11 文件全量同步

### 自循环 API
```python
boost_skill("road-trip-planner")    # 用户采纳 → +1
_penalize_skill("road-trip-planner") # 用户忽略 → -0.5
```
数据存 `~/.hermes/plugins/ssr/preferences.json`。当前仅 stub，未接入实际推荐排序。

## 效果预期

| 指标 | 当前 | v2.1 目标 |
|------|:--:|:--:|
| gate 信号 | 16/30 (53%) | ≥22/30 (73%) |
| 噪音静默 | 19/20 (95%) | 20/20 (100%) |
| 总分 | ~70 | ≥80 |
| 个性化 | 无 | 使用 30 天后偏好生效 |
