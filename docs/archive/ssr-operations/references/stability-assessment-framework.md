# SSR 升级安全评估框架

> 2026-06-09 会话总结。用户要求"先备份，然后持续更新"，AI 对 precision-upgrade plan 剩余 10 个 task 做了三档风险评估。

## 背景

SSR v0.5.0 核心能力已闭环（100 关键词 + 296 embedding + 双阈值 + Dashboard）。precision-upgrade plan 剩余 Phase 3-6 共 10 个 task。用户问"一个版本稳定的情况下能更多少？"

## 三档框架

### ✅ 零风险可推（纯增强，改完不影响现网）

条件：只加新功能、不改现有匹配/排序/会话逻辑、无外部依赖风险。

| Task | 说明 | 理由 |
|------|------|------|
| 3.1 描述富化 | `_get_skill_info` 多取 3-5 句正文 | 纯改善 embedding 输入质量 |
| 3.2 中文增强 | 查询前追加同义词扩展 | 纯预处理，不影响匹配逻辑 |
| 4.1 Dashboard 监控 | dashboard.html 加统计面板 | 纯前端，零风险 |
| 4.2 命中率日志 | 结构化 log | 纯输出，不改行为 |

### ⚠️ 需回归测试（改排序/匹配/会话）

条件：改变现有匹配路径或推荐顺序 → GREEN 5 场景必须重跑。

| Task | 风险点 | 回归方法 |
|------|--------|---------|
| 3.3 混合权重 | 改排序逻辑 → 可能让优质结果沉底 | Force 模式对 a_rules.json 跑 GREEN 5 |
| 5.1 任务切换冷却 | 改 session 行为 → 可能误清冷却 | 同 session 连续切换 3 个话题验证 |

### ❌ 不能推（缺数据/复杂/高风险）

| Task | 阻塞原因 |
|------|---------|
| 4.3 误报降权 | 需要至少数周真实使用数据（用户点了多少次"忽略"） |
| 5.2 分阶段冷却 | 30s/60s/120s 调参无依据，当前 60s 固定冷却够用 |
| 6.1 文件监听 | macOS fsevents 跨平台兼容坑、文件锁竞争 |
| 6.2 热更新索引 | embedding 索引 246 skill × 1024维 × 4B = ~1MB，重建仅 18s，热更新收益 << 风险 |

## 实施顺序

1. 备份：`cp __init__.py a_rules.json plugin.yaml *.bak.$(date +%Y%m%d_%H%M)`
2. 推 4 个零风险（3.1 → 3.2 → 4.2 → 4.1）
3. 每个完工 → `grep '插件注册完成' agent.log` 验证
4. 全部推完 → 跑 GREEN 5 force 模式确认不退化
5. 再评估 3.3 / 5.1（等 4 个零风险稳定后）

## 备份清单

```bash
# 2026-06-09 23:45 已完成
cp ~/.hermes/plugins/ssr/__init__.py ~/.hermes/plugins/ssr/__init__.py.bak.$(date +%Y%m%d_%H%M)
cp ~/.hermes/plugins/ssr/a_rules.json ~/.hermes/plugins/ssr/a_rules.json.bak.$(date +%Y%m%d_%H%M)
cp ~/.hermes/plugins/ssr/plugin.yaml ~/.hermes/plugins/ssr/plugin.yaml.bak.$(date +%Y%m%d_%H%M)
```
