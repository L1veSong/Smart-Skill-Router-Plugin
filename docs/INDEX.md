# SSR 历史文档存档

智配路由（Smart Skill Router）插件已于 **2026-10-19** 从本机所有 profile 移除，源码末态保存在本仓库
（`main` = default profile v3.0.2，`youhong-v3.0.1` 分支 = you-hong profile 定制版）。

本目录保存插件运行期间产生的 **165 份设计笔记、审计记录与调试日志**，用于回溯设计决策与复用通用经验。
它们不是可执行配置，也**不描述任何当前在跑的组件**。

## 移除依据

数据来自 `~/.hermes/logs/gateway.log`，覆盖 2026-10-07 20:54 至 10-19 11:50。

- 每次启动遍历索引约 875 个 `SKILL.md`，12 天内注册 **414** 次
- `2026-10-19 11:21:53 load timed out after 60s (import + register() never returned)` 直接导致 Gateway 加载失败
- **335** 次推荐事件只产出 **9** 种不同结果；其中 228 次命中数撞上 60 条上限（过滤器失效）
- 固定噪声：`github-pr-workflow` 出现 334/335 次，`idea-foundry` 307/335 次
- 后端长期不可用：`LLM 筛查 HTTP 401` 286 次、`LLM 独立匹配 HTTP 401` 41 次、`Ollama 预热跳过` 412 次

## 目录结构

| 路径 | 文件数 |
|---|---|
| `docs/archive/smart-skill-router/` | 1 |
| `docs/archive/smart-skill-router/references/` | 58 |
| `docs/archive/smart-skill-router/scripts/` | 3 |
| `docs/archive/smart-skill-router/tests/` | 1 |
| `docs/archive/ssr-operations/` | 1 |
| `docs/archive/ssr-operations/references/` | 80 |
| `docs/lessons/ars-deep-research/` | 1 |
| `docs/lessons/canon-mnemonic-guard/` | 12 |
| `docs/lessons/cmg-audit/` | 1 |
| `docs/lessons/hermes-agent-skill-authoring/` | 1 |
| `docs/lessons/hermes-plugin-development/` | 1 |
| `docs/lessons/novel-workflow/` | 1 |
| `docs/lessons/skill-installation-guide/` | 1 |
| `docs/lessons/writing-plans/` | 1 |
| `docs/lessons/writing-skills/` | 2 |

## 内容来源

| 原路径 | 说明 |
|---|---|
| `~/.hermes/skills/.archive/ssr-operations/` | 运维手册与逐次调试记录（v0.1 → v2.3） |
| `~/.hermes/skills/.archive/smart-skill-router/` | 设计演进、基准测试、Dashboard 迭代 |
| `~/.hermes/skills/*/<skill>/references/ssr-*` | 被其他 skill 引用的通用经验（插件开发、发布清单、验证方法） |

## 脱敏说明

部分基准测试文件曾以真实人名作为查询样例，导入本仓库时统一替换为「示例用户A」（共 9 处）。
除此之外未做内容修改。
