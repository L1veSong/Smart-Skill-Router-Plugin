# 智配路由 · Smart Skill Router Plugin

<p align="center">
  <b>让 Hermes Agent 自动匹配最合适的 Skill</b><br>
  <sub>A 层关键词 + bge-m3 Embedding 语义 + B 层 LLM 五后端 · 三层漏斗 · 自学习升级</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.6.1-emerald" alt="version">
  <img src="https://img.shields.io/badge/skill%20count-296-orange" alt="skills">
  <img src="https://img.shields.io/badge/A%20rules-100-blue" alt="rules">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license">
</p>

---

## 目录

1. [为什么需要](#为什么需要)
2. [快速安装](#快速安装)
3. [架构](#架构)
4. [完整功能清单](#完整功能清单)
5. [Dashboard](#dashboard)
6. [B 层后端](#b-层后端)
7. [Embedding 层](#embedding-层)
8. [智能冷却](#智能冷却)
9. [增量索引](#增量索引)
10. [配置参考](#配置参考)
11. [关键坑点](#关键坑点)
12. [技术细节](#技术细节)
13. [版本历史](#版本历史)

---

## 为什么需要？

Hermes Agent 可安装 296 个 Skill，但 AI **不会主动加载**——每次都要手动说「用 brainstorming」「用 ui-ux-pro-max」。

SSR 在每次对话前自动分析用户意图，推荐该用的 Skill。

```
用户: "帮我设计一个响应式导航栏"
  → SSR A层(0ms):  design-skill-1 · design-skill-2 · design-skill-3
  → SSR Embedding(~50ms): 匹配度排序 top-30
  → 推荐注入: [SSR] 建议加载: design-skill-1 (DISCOVER) | design-skill-2 (BUILD) | design-skill-3 (BUILD)
```

只推荐**已安装**的 Skill。不强制安装任何特定 Skill。

---

## 快速安装

```bash
# 1. 复制到插件目录
cp -r ssr ~/.hermes/plugins/

# 2. 编辑 config.yaml，在 plugins.enabled 中添加:
#    - ssr

# 3. 可选：安装 bge-m3 Embedding 模型（推荐，提升语义匹配精度）
# curl -L -o ~/Downloads/bge-m3-q4_k_m.gguf \
#   "https://hf-mirror.com/groonga/bge-m3-Q4_K_M-GGUF/resolve/main/bge-m3-q4_k_m.gguf"
# ollama create bge-m3 -f <(echo "FROM ~/Downloads/bge-m3-q4_k_m.gguf")
# hermes config set ssr.embedding.provider ollama
# hermes config set ssr.embedding.model bge-m3

# 4. 重启 Hermes
```

**零配置可用。** B 层默认 `main` 模式，复用主模型（DeepSeek/GPT 等）。Embedding 层可选——不装也能用，但中文语义匹配精度会降低。

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
   | 关键词+正则 | | bge-m3   | | LLM 语义 |
   | ~0ms       | | ~50ms    | | 1-2s     |
   +------------+ +----------+ +----------+
    > 100条正则      > 1024维   > 五后端
    > 零延迟精确      > 296 skill > 兜底长尾
    > 延迟写盘        > 描述富化  > 预过滤→20候选
         |            |             |
         +---- 合并去重 + 冷却制 ----+
                       |
                       v
              [SSR] 推荐注入对话上下文
```

**降级路径：** A 层失效 → Embedding 补充 → B 层兜底 → 无推荐不阻塞对话。

---

## 完整功能清单

| 功能 | 说明 | 版本 |
|------|------|:--:|
| A 层关键词匹配 | 100 条正则规则，零延迟精确命中 | v0.1.0 |
| B 层 LLM 语义 | 五后端（main/openai/ollama/lmstudio/llamacpp） | v0.1.0 |
| 自学习 B→A 升级 | 连续 3 次命中 → 自动固化到 A 层 | v0.4.0 |
| 结果缓存 | B 层结果 60s 复用 | v0.4.0 |
| 冷启动重试 | B 层超时自动 warmup + 重试 | v0.4.0 |
| 推荐/强制模式 | suggest（建议）| enforce（MUST-LOAD） | v0.2.0 |
| 暂停开关 | Dashboard 一键停用，真实写入 config.yaml | v0.3.0 |
| 规则管理 | 增删改查 A 层规则 + 命中统计 | v0.2.0 |
| bge-m3 Embedding | 1024维中文语义，296 skill 索引 | v0.5.0 |
| TDD 基准测试 | RED(0/5)→GREEN(5/5) 自动化 | v0.5.0 |
| auto-gen 关闭 | 配置项开关，避免 10% 准确率噪音 | v0.5.1 |
| 冷却制修复 | shown_recently 标签替代 continue 丢弃 | v0.5.1 |
| 描述富化 | SKILL.md 正文提取（前3段散文） | v0.6.0 |
| 中文查询增强 | 14 域中英映射（金融/UI/调试等） | v0.6.0 |
| 会话命中日志 | 每 10 次调用输出命中率统计 | v0.6.0 |
| Dashboard /api/stats | 规则/Embedding/命中/命中率实时面板 | v0.6.0 |
| 智能冷却 | 自适应（已加载×3、反复未加载×0.5、紧急×0.5、5次跳过） | v0.6.1 |
| 增量索引自动运行 | 每 10 分钟全量 sync + description 变更检测 | v0.6.1 |
| Dashboard 全面美化 | Ethereal Glass 暗色玻璃主题 + 亮暗切换 + 中英文 | v0.6.1 |

---

## Dashboard

```bash
python3 ~/.hermes/plugins/ssr/dashboard.py
# → http://localhost:8766
```

端口 8766。

### 功能页面

**规则管理（Tab 1）**
- 实时统计：活跃规则 / Embedding 索引 / 累计命中 / 命中率
- 搜索过滤：规则 pattern 和 skill 名称模糊搜索
- 增删改查：正则模式 + 技能列表 + 阶段标签
- 批量操作：重置全部规则（二次确认）

**引擎配置（Tab 2）**
- 暂停开关：一键停用 SSR
- 推荐模式：推荐 | 强制
- 扫描策略：启动时 | 每次提问
- B 层后端：五后端可视化配置（provider/model/URL/timeout/key）

### 设计系统

| 属性 | 值 |
|------|-----|
| 设计方向 | Ethereal Glass × Industrial Data Density |
| 字体 | Geist + Geist Mono（Google Fonts） |
| 主色 | Emerald #10b981 |
| 背景 | 暗色 #0c0c0f / 亮色 #f4f4f5 |
| 卡片 | Double-Bezel 双层嵌套（外壳+内芯） |
| 特效 | backdrop-filter 玻璃模糊 + 内高光线 |
| 动画 | 统计卡交错入场 · 卡片 hover 上浮 · 模态弹性缩放 |
| 图标 | SVG 描线（编辑/删除），零 emoji |
| 主题 | 亮/暗切换，localStorage 持久化 |
| 语言 | 中文/English 完整切换，35+ 可翻译元素 |

### 驱动 skill

美化由 4 个 design skill 组合驱动：

| 设计维度 | 来源 |
|------|------|
| 审计现有 UI → 列出 AI slop | 审计 skill |
| Ethereal Glass 视觉 token + Double-Bezel | 高端视觉 skill |
| 数据表 DNA（等宽数字、半透明分割线） | 流行设计 skill |
| 美学方向定调：暗色玻璃 × 工业数据密度 | 前端设计 skill |

---

## B 层后端

| 后端 | 说明 | 配置量 | 推荐场景 |
|------|------|:--:|------|
| **main** | 复用 Hermes 主模型 | 零 | 默认推荐 |
| **openai** | 兼容 API（DeepSeek/SiliconFlow 等） | api_key+url | 有独立 key |
| **ollama** | 本地 Ollama（qwen2.5:3b 等） | model+url | 有 GPU |
| **lmstudio** | LM Studio 本地推理 | model+url | LM Studio 用户 |
| **llamacpp** | llama.cpp server 模式 | model+url | 自部署 |

---

## Embedding 层

**bge-m3**（BAAI 多语言模型，1024 维，q4_k_m 量化 438MB）

| 对比 | nomic-embed-text（旧） | bge-m3（当前） |
|------|----------------------|---------------|
| 维度 | 768 | 1024 |
| 中文语义区分度 | 0.37-0.65 窄带 | 可用级别 |
| 索引 skill 数 | 246 | 296 |
| 设计类 skill 排名（示例） | >100 | **#5** |
| 调试类 skill 排名（示例） | #138 | **#59** |

**安装：** 推荐 hf-mirror 手动下载（ollama pull 太慢），见快速安装章节。

---

## 智能冷却

`_smart_cooldown()` 自适应调整推荐冷却时间：

| 场景 | 冷却调整 |
|------|:--:|
| 用户已加载该 skill | ×3 冷却时间 |
| 同一 skill 推荐 3+ 次未加载 | ×0.5 冷却时间 |
| 同一 skill 推荐 5+ 次未加载 | 跳过（-1） |
| 用户消息含"快/急/马上" | ×0.5 冷却时间 |
| 检测到任务切换词 | 重置全部冷却 |
| 默认 | 标准分阶段冷却 |

追踪字典 `_COOLDOWN_TRACKER` 按 session 记录每个 skill 的推荐次数和加载状态。

---

## 增量索引

`_AUTO_SYNC_INTERVAL = 600`（10 分钟）

每次 `pre_llm_call` 检查距上次全量 sync 时间：
- 超 10 分钟 → 自动 `_sync_embeddings()`
- `_check_skills_changed()` 三路检测：新增 / 删除 / 描述变更
- 变更 skill 自动重建 embedding
- 日志：`热更新: +N -M ΔK skill → 索引 X`

---

## 配置参考

```yaml
# ~/.hermes/config.yaml

plugins:
  enabled:
    - ssr

ssr:
  # 模式：suggest(推荐) | enforce(强制)
  mode: suggest

  # 扫描策略：startup(启动时) | every_turn(每次提问)
  scan_mode: startup

  # 关闭 auto-gen（推荐，避免 10% 准确率噪音）
  auto_gen_rules: false

  # A 层规则上限
  a_rules_max: 100

  # A 层规则有效期（天）
  a_rules_ttl_days: 30

  # B 层 LLM 后端
  b_layer:
    provider: main          # main | openai | ollama | lmstudio | llamacpp
    model: ""               # main 模式留空，其他填模型名
    base_url: ""            # main 模式留空
    timeout: 30
    # api_key: sk-xxx       # openai 模式必填

  # Embedding 语义匹配层（可选，推荐 bge-m3）
  embedding:
    provider: ollama        # ollama | siliconflow | openai
    model: bge-m3           # bge-m3（推荐）| nomic-embed-text（不推荐）
    timeout: 15
```

---

## 关键坑点

| # | 坑点 | 修复状态 |
|:--:|------|:--:|
| 1 | A 层规则反复回退/丢失（多会话内存副本覆盖） | ✅ 延迟写盘系统 |
| 6 | B 层 openai 后端无 api_key 静默失败 | ✅ 三后端路由 |
| 8 | B 层日志 "Ollama调用失败" ≠ Ollama provider | ✅ 日志修复 |
| 11 | 删除 a_rules.json 不备份 → B 层升级规则全丢 | ✅ 已修复 |
| 14 | nomic-embed-text 中文区分度极低 | ✅ 换 bge-m3 |
| 16 | 合并去重 `seen.add(item)` 而非 `seen.add(item["name"])` | ✅ 修复 |
| 17 | 冷却 continue 误杀跨消息匹配 | ✅ shown_recently |
| 18 | auto-gen 准确率仅 10% 噪音淹没手动规则 | ✅ 配置开关 |

---

## 技术细节

| 模块 | 细节 |
|------|------|
| **A 层** | 100 条正则规则，延迟写盘（每 5 次命中 flush） |
| **Embedding 层** | bge-m3 1024 维，余弦相似度 top-30，描述富化（正文前 3 段散文） |
| **B 层** | 预过滤 296→~20 候选 → LLM 精排 → 60s 缓存 |
| **B→A 升级** | 同一 match 连续 3 次 → 自动固化 → 延迟写盘 |
| **冷却** | 60s 基础 × 自适应系数，按 session 追踪 |
| **增量索引** | 每 10 分钟全量 sync，三路变更检测 |
| **降级** | 插件崩溃不阻塞对话，A 层独立工作，B 层不可用则跳过 |
| **Dashboard** | Python HTTP 服务器（8766），纯静态 HTML，API 驱动 |

---

## 版本历史

| 版本 | 日期 | 核心变更 |
|------|------|------|
| v0.6.1 | 2026-06-10 | 智能冷却 + 增量索引 + Dashboard 全面美化 |
| v0.6.0 | 2026-06-10 | 描述富化 + 中文增强 + /api/stats + 会话日志 |
| v0.5.0 | 2026-06-09 | bge-m3 Embedding + TDD 5/5 + auto-gen 关闭 |
| v0.4.0 | 2026-06-06 | B→A 升级 + 结果缓存 + 冷启动重试 |
| v0.3.0 | 2026-06-06 | 暂停开关 + 规则重置 + 中英文切换 + 亮暗主题 |
| v0.2.0 | 2026-06-05 | 推荐/强制模式 + 扫描策略 + Dashboard Tab 导航 |
| v0.1.0 | 2026-06-05 | 首次发布：A+B 双层匹配 |

---

## License

MIT · Author: [L1veSong](https://github.com/L1veSong)
