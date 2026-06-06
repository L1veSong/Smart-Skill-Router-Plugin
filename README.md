# 智配路由 · Smart Skill Router Plugin

<p align="center">
  <b>让 Hermes Agent 自动匹配最合适的 Skill</b><br>
  <sub>A 层零延迟关键词 + B 层 LLM 语义 · 三后端 · 自学习</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue" alt="version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license">
  <img src="https://img.shields.io/badge/platform-Hermes%20Agent-orange" alt="platform">
</p>

---

## 为什么需要？

Hermes Agent 可以安装数百个 Skill，但 AI **不会主动加载**——每次都要手动说「用 brainstorming」「用 ui-ux-pro-max」。

SSR 在你的每次对话前自动分析意图，推荐该用的 Skill。

```
用户: "帮我设计一个响应式导航栏"
  → SSR:  🔍 brainstorming | 🔨 ui-ux-pro-max | ✅ popular-web-designs
```

只推荐你**已经安装**的 Skill。不推荐安装任何特定 Skill。

---

## 快速安装

```bash
# 1. 复制到插件目录
cp -r ssr ~/.hermes/plugins/

# 2. 编辑 config.yaml，在 plugins.enabled 添加:
#    - ssr

# 3. 重启 Hermes
```

**零配置可用。** B 层默认 `main` 模式，复用主模型。

---

## 架构

```
                   user message
                       |
                       v
              +------------------+
              | SSR pre_llm_call |
              +--------+---------+
                       |
            +----------+----------+
            |                     |
            v                     v
     +------------+        +------------+
     |  A  layer  |        |  B  layer  |
     |  keyword   |------->|  semantic  |
     |  0ms       |        |  1-2s      |
     +------------+        +------------+
      > A 层: 零延迟精确        > B 层: 兜底长尾
      > 自学习升级 <---------  > 连续 3 次命中
```
---

## 工作模式

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| 🔵 **推荐**（默认） | `[SSR] 建议加载: ...` AI 自主决定 | 日常使用 |
| 🔴 **强制** | `[MUST-LOAD] 必须加载: ...` AI 强制读取 | 严格工作流 |

在 Dashboard 一键切换。

---

## B 层后端

| 后端 | 说明 | 谁适合 |
|------|------|--------|
| **main** | 复用 Hermes 主模型 | 零配置用户 |
| **openai** | 自定义 API key + URL | 有 API 的用户 |
| **ollama** | 本地 Ollama 服务 | 有 GPU 的用户 |
| **lmstudio** | LM Studio 本地推理 | LM Studio 用户 |
| **llamacpp** | llama.cpp server 模式 | 自部署用户 |

Dashboard 可视化配置，无需手动改文件。

---

## Dashboard

```bash
python3 ~/.hermes/plugins/ssr/dashboard.py
# → http://localhost:8766
```

- 📋 **规则管理**：增删改查 A 层规则，查看命中统计
- ⚙️ **引擎配置**：模式切换 + 扫描策略 + B 层后端

---

## 扫描策略

| 策略 | 优点 | 缺点 |
|------|------|------|
| **启动时扫描**（默认） | 零延迟 | 新装 Skill 需重启 |
| **每次提问扫描** | 新装 Skill 即时感知 | 每次 ~200ms 延迟 |

---

## 配置参考

```yaml
ssr:
  mode: suggest          # suggest | enforce
  scan_mode: startup     # startup | every_turn
  b_layer:
    provider: main       # main | openai | ollama | lmstudio | llamacpp
    model: deepseek-chat
    base_url: https://api.deepseek.com/v1
    timeout: 30
    api_key: sk-xxx      # main 模式留空
```

---

## 技术细节

- A 层：正则匹配，延迟写盘（每 5 次命中），60s 冷却去重
- B 层：预过滤 223→20 候选 → LLM 精排，60s 结果缓存
- 自学习：B 层连续 3 次命中 → 升级到 A 层
- 降级：插件崩溃不阻塞对话，B 层不可用时 A 层独立工作

---

## License

MIT
