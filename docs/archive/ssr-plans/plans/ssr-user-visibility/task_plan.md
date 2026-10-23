# SSR 用户可见性 + AI 汇报接口 Plan

> **For Hermes:** 两个独立功能，可分开实施

**Goal:** 用户能(1)看到 SSR 推荐了什么 (2)知道 AI 用了没

**Architecture:** (1) 已有 display 开关，确认工作正常即可 (2) 新增 report 开关 + CMG 规则，AI 自觉汇报

---

## 现状

| 功能 | 状态 | 代码位置 |
|------|------|---------|
| `ssr.display` 配置 | ✅ 已有 | `__init__.py` L199-202, L2500-2503 |
| display=true → SSR 注入回复 | ✅ 已实现 | post_llm_call L1224-1236 |
| display=false → 完全静默 | ✅ 已实现 | pre_llm_call 返回 None |
| AI 汇报 SSR 使用情况 | ❌ 不存在 | — |

## Task 1: 确认 display 可见性是否正常工作

**Objective:** 验证 `ssr.display: true` 时用户确实能看到推荐

**Step 1: 检查当前行为**

`ssr.display` 已经是 `true`。pre_llm_call 将推荐注入 AI 上下文，post_llm_call 将推荐注入回复开头。

需要验证：用户在 CLI 端实际看到的是：
```
[SSR] [P] brainstorming, plan | [V] ...
---
我的回复
```

如果看不到 → 排查 post_llm_call hook 是否被 CLI 端正确执行

**Step 2: 修（如果需要）**

如果 post_llm_call 在 CLI 端不工作，备选方案：
- 改 pre_llm_call 注入方式（不只是 context，也注入到可见输出）
- 或在 pre_llm_call 里调用通知机制

---

## Task 2: 新增 `ssr.report` 配置 + AI 汇报行为

**Objective:** AI 每次回复明确说明"SSR 推了哪些、用了哪些、没用的为什么"

**Step 1: 定义配置接口**

```yaml
# config.yaml
ssr:
  display: true          # 已有：SSR 推荐是否可见
  report: true           # 新增：AI 是否汇报使用情况（默认 false）
```

**Step 2: CMG 规则（AI 自觉层）**

新增 CMG ban 规则。当 `ssr.report: true` 时：
- AI 每次回复必须包含 SSR 使用汇报
- 格式：`[SSR 使用] 推荐: X, Y, Z | 已用: X | 跳过: Y(原因) Z(原因)`
- 如果 SSR 无推荐：`[SSR 使用] 本轮无推荐`

规则写入 `rules/ban/` 或 `rules/gap/`。

**Step 3: SSR 插件层（可选强化）**

如果想强制而非靠 AI 自觉：
- pre_llm_call 注入时附带指令：`你必须汇报SSR推荐的使用情况`
- 或 post_llm_call 检测回复是否包含汇报，缺失则追加警告

**Step 4: 测试**

开启 `ssr.report: true` → 发一条需要 skill 的消息 → 检查 AI 是否汇报。

---

## 配置总结（实施后）

```yaml
ssr:
  display: true    # false=完全静默, true=注入推荐到回复
  report: true     # false=不汇报, true=AI每轮汇报用了没
```

四象限：
- `display:false + report:false` = 完全静默（当前默认）
- `display:true  + report:false` = 用户看到推荐，AI 不汇报
- `display:false + report:true`  = 用户看不到但 AI 仍汇报（废组合，禁止）
- `display:true  + report:true`  = 全透明（推荐可见 + AI 汇报使用）

---

## Risks

| 风险 | 缓解 |
|------|------|
| post_llm_call 注入 CLI 端不生效 | 先验证，备选 pre_llm_call 方案 |
| AI 汇报太啰嗦，每轮都一大段 | 只用一行紧凑格式 |
| report 纯靠 CMG 自觉，AI 可能忘 | 考虑 SSR 插件层强化（Task 2 Step 3） |
