# 智配路由 · Smart Skill Router Plugin

<p align="center">
  <b>让 Hermes Agent 自动匹配最合适的 Skill</b><br>
  <sub>A 层关键词 + Embedding 语义 + B 层 LLM · 三层漏斗 · 自学习升级</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.6.1-emerald" alt="version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license">
  <img src="https://img.shields.io/badge/platform-Hermes%20Agent-orange" alt="platform">
</p>

---

## 为什么需要？

Hermes Agent 可安装大量 Skill，但 AI **不会主动加载**——每次都要手动指定用哪个。

SSR 在每次对话前自动分析用户意图，推荐该用的 Skill。

```
用户: "帮我设计一个响应式导航栏"
  → SSR A层(0ms):  关键词精确命中
  → SSR Embedding(~50ms): 语义匹配排序
  → 推荐注入: [SSR] 建议加载: skill-a (DISCOVER) | skill-b (BUILD) | skill-c (BUILD)
```

只推荐**已安装**的 Skill。不强制安装任何特定 Skill。

---

## 快速安装

```bash
# 1. 复制到插件目录
cp -r ssr ~/.hermes/plugins/

# 2. 编辑 config.yaml，在 plugins.enabled 中添加:
#    - ssr

# 3. 重启 Hermes
```

**零配置可用。** B 层默认 `main` 模式，复用主模型。

---

## 架构

```
                   用户消息
                       |
                       v
              +------------------+
              | SSR pre_llm_call |  ← 插件钩子，每次对话前触发
              +--------+---------+
                       |
          +------------+-------------+
          |            |             |
          v            v             v
   +------------+ +----------+ +----------+
   |  A  层     | |Embedding | |  B  层   |
   | 关键词+正则 | | 语义匹配 | | LLM 精排 |
   | ~0ms       | | ~50ms    | | 1-2s     |
   +------------+ +----------+ +----------+
    > 零延迟精确      > 向量召回   > 五后端兜底
         |            |             |
         +---- 合并去重 + 冷却制 ----+
                       |
                       v
              [SSR] 推荐注入对话上下文
```

**降级路径：** A 层失效 → Embedding 补充 → B 层兜底 → 无推荐不阻塞对话。

---

## 功能清单

| 功能 | 说明 |
|------|------|
| A 层关键词匹配 | 正则规则，零延迟精确命中 |
| Embedding 语义匹配 | 向量召回，补充关键词盲区 |
| B 层 LLM 精排 | 五后端（main/openai/ollama/lmstudio/llamacpp） |
| 自学习 B→A 升级 | 连续命中 → 自动固化到 A 层 |
| 结果缓存 | B 层结果缓存复用 |
| 推荐/强制模式 | suggest（建议）| enforce（强制加载） |
| 暂停开关 | 一键停用 SSR |
| 智能冷却 | 自适应冷却（已加载延后、未加载加速、紧急加速） |
| 增量索引 | 自动检测新增/删除/变更 skill |
| Dashboard | Web 管理面板：规则管理 + 引擎配置 + 实时统计 |

---

## Dashboard

```bash
python3 ~/.hermes/plugins/ssr/dashboard.py
# → http://localhost:8766
```

### 功能

**规则管理**
- 实时统计面板
- 搜索过滤
- 增删改查 A 层规则

**引擎配置**
- 暂停开关
- 推荐模式切换
- 扫描策略
- B 层后端可视化配置

**交互**
- 亮/暗主题切换
- 中/英文切换

---

## B 层后端

| 后端 | 说明 | 配置量 |
|------|------|:--:|
| **main** | 复用 Hermes 主模型 | 零 |
| **openai** | 兼容 API | api_key+url |
| **ollama** | 本地 Ollama | model+url |
| **lmstudio** | LM Studio | model+url |
| **llamacpp** | llama.cpp server | model+url |

---

## Embedding 层（可选）

安装本地 Embedding 模型可提升语义匹配精度。不装也能用——B 层 LLM 兜底。

```bash
# 推荐：多语言 Embedding 模型
ollama pull <embedding-model>

# 配置
hermes config set ssr.embedding.provider ollama
hermes config set ssr.embedding.model <embedding-model>
```

---

## 配置参考

```yaml
# ~/.hermes/config.yaml

plugins:
  enabled:
    - ssr

ssr:
  mode: suggest
  scan_mode: startup
  auto_gen_rules: false

  b_layer:
    provider: main
    timeout: 30

  embedding:
    provider: ollama
    model: <embedding-model>
    timeout: 15
```

---

## 版本历史

| 版本 | 日期 | 核心变更 |
|------|------|------|
| v0.6.1 | 2026-06-10 | 智能冷却 + 增量索引 + Dashboard 美化 |
| v0.6.0 | 2026-06-10 | 描述富化 + 中文增强 + /api/stats |
| v0.5.0 | 2026-06-09 | Embedding 层 + TDD 基准 |
| v0.4.0 | 2026-06-06 | B→A 升级 + 结果缓存 |
| v0.3.0 | 2026-06-06 | 暂停开关 + 中英文 + 亮暗主题 |
| v0.2.0 | 2026-06-05 | 推荐/强制模式 + Dashboard Tab |
| v0.1.0 | 2026-06-05 | 首次发布 |

---

## License

MIT · Author: [L1veSong](https://github.com/L1veSong)
