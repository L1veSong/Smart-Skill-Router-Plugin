# SSR precision-upgrade plan 可行性分析

> 日期: 2026-06-09 | v2 plan | 结果: Phase 2 可行并已实现

## Plan 原始假设 vs 代码实际

| 假设 | 实际 | 影响 |
|-----|------|------|
| B 层面对 294 skill | `_prefilter_skills` 已降到 20 | "成本降90%" 不成立 |
| A 层去上限完成 | `len(result) >= 5: break` 两处仍在 | Phase 1 未完成 |
| B 层 prompt "不限数量" | 仍是 "3-8 个" | Phase 1.2 未做 |
| B 层 max_tokens 500 | 仍是 200 | Phase 1.1 未做 |
| nomic-embed-text 可直接 pull | 用户环境 TLS 超时 registry.ollama.ai | Phase 2 网络阻塞 |

## 精度验证

- nomic-embed-text 768维，329ms/次
- 7 skill 小规模测试：4/5 通过（80%），对比 auto-gen 10%
- 唯一失败：中文查询 vs 纯英文 skill description → 全量索引（295 skill）可缓解

## 设计纠正

1. **不要 SiliconFlow 作为默认**：开源用户需零配置，Ollama 是唯一正确的默认
2. **多后端设计**：和 B 层一样，ollama(默认)/siliconflow/openai
3. **先改 plan 再改代码**：用户明确要求

## Patch replace_all 转义坑

- `replace_all: true` 在 Python 源码含 `\u300c` 等 Unicode 转义字符串上会追加拿层反斜杠
- 正确做法：每处用唯一上下文单次 patch，或 Python 脚本直接操作
- 本会话：两处 openai/main 端点改 "匹配 3-8 个技能" → "匹配技能"，第一遍 replace_all 炸，第二遍单次 patch 成功

## Reasonix 测试

- `reasonix run`：只读推理，不写文件（两次测试确认）
- `reasonix code`：交互式，需 pty，Hermes 非交互调用不可用
- 结论：接入 Hermes 无法写代码，无实际价值
