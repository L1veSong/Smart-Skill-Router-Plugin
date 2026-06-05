# 智配路由 (Smart Skill Router Plugin) v0.1.0

自动匹配用户意图到最合适的 skill 并推荐加载。A 层关键词精确匹配（零延迟）+ B 层 LLM 语义匹配（三后端可选）。

## 为什么需要它

Hermes Agent 有 200+ 个 skill，但 AI 不会主动加载——每次都要手动说"用 brainstorming""用 ui-ux-pro-max"。SSR 在 `pre_llm_call` 阶段自动检测用户意图，推荐该加载的 skill。

## 架构

```
用户消息
    ↓
[SSR pre_llm_call]
    ├── A 层：11 条种子规则，正则匹配 → 零延迟命
    └── B 层：223 skill 语义匹配 → 兜底长尾
         ├── main 后端：复用 Hermes 主模型（零配置）
         ├── openai 后端：自定义 API key + base_url
         └── ollama 后端：本地模型
```

## 安装

```bash
# 1. 复制插件目录
cp -r ssr ~/.hermes/plugins/

# 2. 启用插件（config.yaml）
plugins:
  enabled:
    - ssr

# 3. 配置（可选，默认 zero-config）
ssr:
  b_layer:
    provider: main   # main | openai | ollama
```

## B 层后端配置

| 后端 | 适用场景 | 示例配置 |
|------|---------|---------|
| **main**（默认） | 零配置，复用 Hermes 主模型 | `provider: main` |
| **openai** | 自定义 API | `provider: openai, api_key: sk-xxx, base_url: https://api.openai.com/v1` |
| **ollama** | 本地模型 | `provider: ollama, model: qwen2.5:3b, base_url: http://localhost:11434` |

## A 层种子规则

11 条预置规则，覆盖最高频场景：

| 用户意图 | 推荐 skill |
|---------|-----------|
| 设计页面/UI/导航 | brainstorming, ui-ux-pro-max, popular-web-designs |
| 调试/报错/KeyError | diagnose, systematic-debugging |
| 写代码/功能 | brainstorming, test-driven-development, planning-with-files |
| 写论文/文档 | research-paper-writing, planning-with-files |
| ASCII 艺术 | ascii-art |
| 股票/均线/技术分析 | technical-analysis, tushare-finance |
| 旅行/出行 | trip-planner-generator, road-trip-planner, travel-skill |
| 代码审查 | requesting-code-review, github-code-review |
| 架构/规划 | brainstorming, writing-plans, idea-foundry |
| 发布/部署 | ralph-loop, verification-before-completion |
| arXiv/论文检索 | arxiv |

## Dashboard

规则可视化管理界面（增删改查）：

```bash
python3 ~/.hermes/plugins/ssr/dashboard.py
# → http://localhost:8766
```

## 技术细节

- A 层：正则匹配，零延迟，命中计数 + 冷却去重 + 延迟写盘
- B 层：预过滤 223→20 候选，LLM 语义匹配 + 60s 结果缓存
- 自学习：B 层连续 3 次命中 → 升级到 A 层
- 降级：插件崩溃不阻塞对话，B 层不可用时 A 层独立工作

## 兼容性

- Hermes Agent 任意版本
- B 层 main 模式：零依赖
- B 层 openai 模式：httpx
- B 层 ollama 模式：httpx + 本地 Ollama 服务

## License

MIT
