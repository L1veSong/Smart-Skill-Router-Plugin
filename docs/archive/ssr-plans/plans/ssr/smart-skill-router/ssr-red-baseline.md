# SSR 基线测试 (RED Phase)

> 测试时间: 2026-06-04
> 被测对象: AI agent 在没有 SSR 插件时能否主动加载相关 skill
> 方法: 观察当前会话行为 + 构造 5 个压力场景

---

## 场景 1: 复杂 UI 设计任务

**用户请求:** "帮我设计一个旅行网站"
**期望行为:** 加载 ui-ux-pro-max / popular-web-designs / travel-website-generator / brainstorming
**实际行为:** 不会主动加载这些 skill，需要用户明确说"用 ui-ux-pro-max"
**证据:** 本会话中用户多次指出 "为什么不自动匹配合适的skill"

**结果: ❌ 失败**

---

## 场景 2: 代码调试

**用户请求:** "这段代码报错了帮我看看"
**期望行为:** 加载 diagnose / systematic-debugging
**实际行为:** 直接回答，不加载专业调试 skill

**结果: ❌ 失败（预测）**

---

## 场景 3: 创意生成

**用户请求:** "给我画一个 ASCII 艺术图"
**期望行为:** 加载 ascii-art
**实际行为:** 不加载，用手工方式做

**结果: ❌ 失败（预测）**

---

## 场景 4: 学术写作

**用户请求:** "帮我写论文的 Introduction 部分"
**期望行为:** 加载 research-paper-writing
**实际行为:** 不加载，通用方式写

**结果: ❌ 失败（预测）**

---

## 场景 5: 金融分析

**用户请求:** "帮我分析一下这只股票的走势"
**期望行为:** 加载 technical-analysis / tushare-finance
**实际行为:** 不加载，通用分析

**结果: ❌ 失败（预测）**

---

## RED 基线总结

| 场景 | 主动加载？ | 证据 |
|------|:---:|------|
| UI 设计 | ❌ | 本会话用户纠正记录 |
| 代码调试 | ❌ | 预测 |
| 创意生成 | ❌ | 预测 |
| 学术写作 | ❌ | 预测 |
| 金融分析 | ❌ | 预测 |

**RED 基线: 0/5 通过。** 无 SSR 时，AI 在 5 个场景中均不主动加载相关 skill。

---

## GREEN 验证计划（需 Hermes 重启后）

重启后发送以下 5 条消息，观察是否有 [SSR] 推荐注入:

1. "帮我设计一个响应式导航栏" → 期望触发 ui-ux-pro-max / popular-web-designs
2. "这段 Python 代码报 KeyError 帮我看看" → 期望触发 diagnose
3. "生成一个 ASCII 猫咪图" → 期望触发 ascii-art
4. "帮我写论文的 Related Work 部分" → 期望触发 research-paper-writing
5. "分析贵州茅台的均线走势" → 期望触发 technical-analysis

**通过标准:** ≥3/5 命中 SSR 推荐
**目标标准:** ≥4/5 命中
