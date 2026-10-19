# CHANGELOG 措辞精度：删除 ≠ 语义变更（2026-07-04 SSR v2.2.0 实战）

## 症状

CHANGELOG 写"删 explicit similarity_floor"，审计 grep 发现 `_similarity_floor()` 函数仍存在于代码中。CHANGELOG 声称与代码实际不一致——但这不是 bug，是措辞误导。

## 根因

SSR v2.2.0 的真实变更是**语义变更**：
- **之前**：`similarity_floor` 是 config.yaml 的必填配置项，`_similarity_floor()` 从中读取
- **之后**：`similarity_floor` 不再是必填项，`_similarity_floor()` 改为无极校准优先 + 显式 override 兜底

函数没删——它还在且行为变了。但 CHANGELOG 用"删除"这个词，读了 CHANGELOG 的人会以为函数不复存在。grep 发现函数还在 → 怀疑 CHANGELOG 撒谎 → 误判为发布缺陷。

## 正确做法

CHANGELOG 措辞必须精确区分三种操作：

| 措辞 | 含义 | grep 验证 |
|------|------|-----------|
| **删除** | 函数/变量/配置项从代码中物理移除 | `grep -n 'x' __init__.py` → 零命中 |
| **语义变更** | 函数存在，但行为、默认值、优先级链改变 | `grep` 命中是正常的，diff 看实现 |
| **新增** | 之前不存在的函数/变量/配置项 | `grep -n 'x' __init__.py` → 有命中 |

## 判定标准

写 CHANGELOG 的变更描述时，自问：如果别人对代码做 `grep 'function_name'`，会看到什么？

- 看到函数还在 → 不能说"删除"
- 看到函数没了 → 可以说"删除"
- 函数行为变了 → 说"语义变更：xxx"或"重构：xxx"

## 关联教训：embeddings.json model: ? 

v2.2.0 审计同时发现 `embeddings.json` 中 423 skills 索引为 4096 维，但 `model: ?`——无模型名记录。换 embedding 模型后无法判断索引是否过期。这也是"CHANGELOG 说接管了但运行时元数据缺失"的同类问题：声称和实际之间的 gap 不只存在于 CHANGELOG，也存在于运行时数据。

## 关联规则

- 审计清单第 5 项（CHANGELOG 声称 vs 代码实际）的 grep 验证只检测缺失（声称有但代码无），不检测措辞精度
- 措辞精度问题需要**人工审查**——grep 发现函数还在但 CHANGELOG 说删除时，不是程序 bug，是文档措辞 bug
- 这条规则应纳入发布前的 CHANGELOG 审查步骤：逐条变更描述 vs 代码实际状态
