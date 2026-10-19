# A 层规则生成方案选型

> 决策: 2026-07-23 | 暂定方案①

## 三种方案

| # | 方案 | 准确度 | 维护成本 | 自动程度 | 现状 |
|---|---|---|---|---|---|
| ① regex 手动 | 手写正则+domain+skills | 🟢 最高 | 🔴 每次手写 | 0% | **当前** |
| ② auto_gen | 从 SKILL.md description 提取关键词 | 🟡 依赖作者描述 | 🟢 自动 | 100% | 曾产 6789 垃圾 |
| ③ embedding 语义 | cosine similarity 匹 480 skill description | 🟡 依赖 embedding 服务 | 🟢 零维护 | 100% | 终局方案 |

## ② 为什么不行

auto_gen 从英文 description 提取关键词 → 匹配中文用户意图。这条路上限低：
- `travel` → 匹配 "travel" 而非 "想去玩"
- 中英文 mismatch 是根病，不是过滤问题
- 2026-07-23 清理了 6789 条垃圾规则

## ③ 为什么是终局

- 装新 skill → 自动 embed description → 入索引 → 零配置
- 语义匹配解决近义词问题
- 当前阻塞：硅基流动 embedding 服务不稳定

## 切换条件

1. 硅基流动 embedding 连续 3 天零断连
2. 或切换到本地 Ollama bge 模型
3. 或 Hermes 支持 OpenAI-compatible embedding provider
