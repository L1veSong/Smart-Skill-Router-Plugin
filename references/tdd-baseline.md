# SSR TDD 基线测试记录

> 会话: 2026-06-04 ~ 2026-06-05

## RED 基线 (无 SSR)

5 个压力场景，AI 均不主动加载相关 skill：

| # | 场景 | 主动加载 | 
|---|------|:---:|
| 1 | 帮我设计一个登录页面 | ❌ |
| 2 | 这段代码一直报 KeyError | ❌ |
| 3 | 生成一个 ASCII 猫咪图 | ❌ |
| 4 | 帮我写论文的 Related Work | ❌ |
| 5 | 分析贵州茅台的均线走势 | ❌ |

**RED 结果: 0/5 通过**

## GREEN 验证 (SSR 启用)

| # | 场景 | A 层 | 结果 |
|---|------|------|:--:|
| 1 | 设计登录页 | 设计.*登录 → brainstorming, ui-ux-pro-max, popular-web-designs | ✅ |
| 2 | KeyError 调试 | debug\|KeyError → diagnose, systematic-debugging | ✅ |
| 3 | ASCII 猫咪 | ASCII\|ascii → ascii-art | ✅ |
| 4 | 金融分析 | 股票\|均线 → technical-analysis, tushare-finance | ✅ |
| 5 | arXiv 论文 | arXiv\|arxiv → arxiv | ✅ |

**GREEN 结果: 5/5 通过**

## TDD 循环执行记录

### 2026-06-05 17:45 — TDD 自动化脚本

执行 `tests/ssr_tdd_baseline_test.py`，严格 RED→GREEN→REFACTOR：

| 阶段 | 规则集 | 得分 | 说明 |
|------|--------|:--:|------|
| 🔴 RED | 空规则集 | 0/5 | 模拟无 SSR，验证全部失败 |
| 🟢 GREEN | A 层 11 条规则 | 5/5 | 全部命中 |
| 🔵 REFACTOR | — | 无需 | 5/5 满分 |

### 原始开发期间 TDD 循环 (2026-06-04)

| # | 场景 | A 层 | 结果 |
|---|------|------|:--:|
| 1 | 设计登录页 | 设计.*登录 → brainstorming, ui-ux-pro-max, popular-web-designs | ✅ |
| 2 | KeyError 调试 | debug\|KeyError → diagnose, systematic-debugging | ✅ |
| 3 | ASCII 猫咪 | ASCII\|ascii → ascii-art | ✅ |
| 4 | 金融分析 | 股票\|均线 → technical-analysis, tushare-finance | ✅ |
| 5 | arXiv 论文 | arXiv\|arxiv → arxiv | ✅ |

## REFACTOR（6 轮修复）

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | 种子规则被清空 | last_hit: "" 被当过期 | 空值不过期 |
| 2 | B 层全超时 | timeout 5s + 冷启动 | →30s + 预热 |
| 3 | 换任务不推荐 | 永久跳过 | 冷却制 60s |
| 4 | 擅自关 CMG | 未分析影响 | ban_no_disable_without_confirm |
| 5 | B 层只支持 Ollama | 硬编码 | 三后端架构 |
| 6 | 预过滤无效 | 单字匹配 | 双字+名权重+A 层加权 |
