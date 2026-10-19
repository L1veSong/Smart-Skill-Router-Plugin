# SSR 案例：IF 逼问 8 个设计决策

SSR（智配路由）开发时，IF（Idea Foundry）逼问了 8 个边界场景：

| # | 问题 | 决策 |
|---|------|------|
| 1 | skills_list 扫描失败怎么办？ | 弹窗报错，不静默降级 |
| 2 | skill 描述过期？ | 每次启动重新扫 |
| 3 | qwen2.5:3b 够不够？ | 先做再测 |
| 4 | 推荐 skill 有执行顺序？ | B 层一次推理同时返回阶段标签（DISCOVER→PLAN→BUILD→VERIFY） |
| 5 | 连续消息重复匹配？ | 任务切换检测 + 会话内复用 |
| 6 | A 层规则冲突？ | priority: manual > auto，精确度排序 |
| 7 | 残骸 skill？ | 启动弹窗报告 |
| 8 | 插件崩溃？ | 降级不阻塞 |

## B 层三后端架构

| 后端 | 适用场景 | 默认 |
|------|---------|:---:|
| main | 零配置，复用 Hermes 主模型 | ✅ |
| openai | 自定义 API key + base_url | |
| ollama | 本地模型 | |

## TDD 基准测试

RED（无 SSR）: 0/5 —— AI 不主动加载 skill
GREEN（启用 SSR）: 5/5 —— A 层 11 条规则全命中
REFACTOR: 8 轮修复（延迟写盘、api_key 截断、warmup 分路、global 声明等）
