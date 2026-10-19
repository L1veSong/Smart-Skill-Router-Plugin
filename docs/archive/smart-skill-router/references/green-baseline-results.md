# SSR GREEN 基准测试结果

> 最新测试: 2026-06-05 17:45（TDD RED→GREEN 完整循环）
> 被测对象: SSR v0.1.0 (config: b_layer.provider=main)
> 通过标准: ≥3/5 | 目标: ≥4/5 | 本次: 5/5 🎉

## 测试环境

- A 层: 11 条种子规则
- B 层: `provider: main` → DeepSeek API
- 配置: `b_layer.timeout=30`
- 测试方法: TDD 自动化脚本 `tests/ssr_tdd_baseline_test.py`

## 最新结果: 5/5 ✅ 满分（2026-06-05 TDD 循环）

| # | 用户消息 | 期望命中 | A 层 | 结果 |
|---|---------|---------|------|:--:|
| 1 | 帮我设计一个响应式导航栏 | brainstorming, ui-ux-pro-max, popular-web-designs | ✅ 全部命中 | ✅ |
| 2 | 这段代码一直报 KeyError 帮我看看 | diagnose, systematic-debugging | ✅ 全部命中 | ✅ |
| 3 | 生成一个 ASCII 猫咪图 | ascii-art | ✅ 全部命中 | ✅ |
| 4 | 帮我写论文的 Related Work 部分 | research-paper-writing, planning-with-files | ✅ 全部命中 | ✅ |
| 5 | 分析贵州茅台的均线走势 | technical-analysis, tushare-finance | ✅ 全部命中 | ✅ |

**5/5 (100%) — 满分通过。** A 层 11 条规则覆盖全部 5 个基准场景。

## 历史结果

| 时间 | 得分 | 测试方式 | 备注 |
|------|:--:|------|------|
| 2026-06-05 TDD 循环 | **5/5** | TDD 脚本 | A 层 debug 规则修复后满分 |
| 2026-06-05 重启后 | 4/5 | 手动 | 场景 2 失败（debug 规则不支持 KeyError） |
| 2026-06-05 首次 | 2/5 | 手动 | 场景 2/5 未通过 |

## 本次改进

上次 GREEN 4/5，场景 2（"报 KeyError"）失败。根因：debug 规则 pattern 不含 `KeyError`。

修复后 debug 规则 pattern:
```
debug|修复|报错|bug|异常|不工作|调试|KeyError|Traceback|Error|报.*Error|代码.*报错|报错.*代码
```

`KeyError` 和 `报.*Error` 覆盖了「报 KeyError」「Python 报 KeyError」等中英混合错误信息。

## B 层状态

`provider: main` B 层仍不可用（warmup 路径 bug：硬编码 Ollama `/api/generate` 端点）。但 A 层 11 条规则已覆盖全部 5 个基准场景，B 层降级不影响 GREEN 结果。

## 修复建议（优先级排序）

1. ~~**A 层 debug 规则补缺口**：加 `Error|报.*错|Traceback|Exception`~~ ✅ 已修复
2. **B 层 warmup 路径修复**：`_match_b_layer()` 仅 Ollama provider 时走 `/api/generate`，其他 provider 跳过
3. **A 层种子规则扩充**：加常见变体（设计类加 `responsive|响应式`，ASCII类加 `cat|猫咪`）
