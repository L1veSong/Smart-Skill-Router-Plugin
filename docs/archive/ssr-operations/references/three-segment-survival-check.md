# SSR 三段式存活快速诊断 (2026-06-09)

> **用途：** 快速确认 SSR 插件是否在运行并产出推荐。不能替代 GREEN 基准测试——这只回答"活着吗"，不回答"推得准吗"。

## 三段命令

```bash
# ① 存活确认 — SSR 插件是否注册成功？
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# 期望: [ssr] 插件注册完成 | skill: 296 | 残骸: 0 | A层: 100+2010 | emb: 246 | B层: main

# ② 实时命中 — A 层是否在匹配用户消息？
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -3
# 期望: [ssr] A 层命中: ['brainstorming', 'writing-plans', ...]

# ③ 合并效果 — Embedding 双路径是否在工作？
grep 'embedding' ~/.hermes/logs/agent.log | tail -3
# 期望: [ssr] embedding 索引: 246 skill（增量同步）
```

## 判定标准

| ① | ② | ③ | 结论 |
|:--:|:--:|:--:|------|
| ✅ | ✅ | ✅ | SSR 存活，双路径工作。但准确率未知——需跑 GREEN 基准 |
| ✅ | ✅ | ❌ | A 层关键词工作，Embedding 索引缺失。降级运行 |
| ✅ | ❌ | ❌ | 插件注册但未匹配——可能用户消息无匹配 skill |
| ❌ | ❌ | ❌ | SSR 未加载——检查 config.yaml 的 plugins.enabled |

## 不能回答的问题

- 推荐给用户的 skill 是否用户需要的？（→ GREEN 基准）
- auto-gen 规则的 10% 准确率是否被 Embedding 弥补？（→ GREEN 基准）
- B 层语义兜底是否生效？（→ GREEN 基准 + 独立 B 层 API 测试）

## 实战教训

2026-06-09：AI 跑完三段式后暗示"SSR 全部通过"，用户纠正——"走基准测试了吗？"。三段式全绿只能证明插件在运行，不能证明推荐质量。存活验证 ≠ 质量验证。
