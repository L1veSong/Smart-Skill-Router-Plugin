# SSR Benchmark 解读指南

> 2026-07-04：三步验证中 #3 噪音静默未达标（11/20 vs ≥18/20），根因是 benchmark 模式误解。

## 三种模式

| 模式 | 测什么 | 噪音路径 | 适用场景 |
|------|--------|---------|---------|
| `--mode embedding` | 裸 embedding 层 | 仅 floor 过滤 | 模型选型对比 |
| `--mode gate` | 意向门控 | 本地 LLM 二分类 | 门控模型选型 |
| `--mode total` | 全链路 | 关键词→embedding→LLM筛选 | 生产精度 |

## Embedding 模式的物理极限

Qwen3-Embedding-8B + floor=0.58 实测数据（2026-07-04）：

| 噪音 | 相似度 | 命中 |
|------|--------|------|
| "ok" | 0.7058 | caveman |
| "..." | 0.6969 | planning-with-files |
| "帮我写作业" | 0.6562 | planning-with-files |
| "周末去哪玩" | 0.6117 | travel-skill |
| "能行吗" | 0.5933 | using-superpowers |
| "确定吗" | 0.5877 | using-superpowers |
| "这个颜色好看吗" | 0.5902 | ui-ux-pro-max |
| "？？？" | 0.5851 | agent-reach |

**结论：** 11/20 是 floor=0.58 的物理极限。要达 18/20 需 floor≈0.70+，会杀信号。剩余噪音需意向门控+LLM筛选解决。

## 不要做的事

- **不要**因为 `--mode embedding` 的噪音静默不达标就去修改 `__init__.py` 生产代码
- **不要**在 merge 阶段加 `emb_confirmed` 门控——关键词命中是 SSR 的核心价值，不应该被 embedding floor 二次过滤
- **不要**给 `_match_a_layer_keyword` 加 ≤3 字符门控——生产代码和 benchmark 脚本的职责不同

## 该做的事

- `--mode embedding` 结果 = 模型选型参考，非生产精度指标
- `--mode total` 是生产精度指标——包含完整管线
- benchmark 脚本读 `calibrated_floor` 是正确的——让它反映生产 floor
- 生产代码 `__init__.py` 的 merge 逻辑是正确的——不要改
