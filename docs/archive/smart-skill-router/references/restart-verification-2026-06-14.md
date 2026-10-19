# SSR 重启验证报告 — 2026-06-14

> 配置: embedding=text2vec-bge-large-chinese (nn200433, 1024维纯中文, 207MB), B层=main (DeepSeek v4-pro)

## 测1: 重启后 A 层诊断

```
[ssr] 加载 A 层规则: 0 条
[ssr] 清理后 A 层规则: 0 条
[ssr] 单字净化后 A 层规则: 0 条  ← Z=0
[ssr] embedding 索引: 370 skill（增量同步）
[ssr] 插件注册完成 | skill: 370 | A层: 0+0 | emb: 370 | B层: main
```

**结论:** 重启后 A 层关键词规则表归零。embeddings.json 完好（8MB, 370 skill）。v0.6.2 修复的三步诊断日志正常输出，但清空步骤已确认——`register()` 加载时为 0，清理后为 0，单字净化后为 0。a_rules.json 为 `{}`（2 bytes）。

## 测2: GREEN baseline（text2vec-bge-large-chinese + DeepSeek main B层）

| # | 用户消息 | SSR 结果 | 命中 skill | 判定 |
|---|---------|:--:|------|:--:|
| 1 | 帮我设计一个响应式导航栏 | 无匹配 | — | ❌ |
| 2 | 这段 Python 代码报 KeyError 帮我看看 | B层命中 | `investigate`（非真实skill） | ⚠️ |
| 3 | 生成一个 ASCII 猫咪图 | 无匹配 | — | ❌ |
| 4 | 帮我写论文的 Related Work 部分 | 无匹配 | — | ❌ |
| 5 | 分析贵州茅台的均线走势 | B层命中 | `technical-analysis`, `short-term-trader-perspective` | ✅ |

**得分: 2/5（4含无效skill `investigate`，实际有效命中 1/5）。不到 3/5 及格线。**

### 对比历史基准

| 日期 | embedding | B层 | 得分 | 
|------|-----------|-----|:--:|
| 2026-06-09 | bge-m3 | ollama (qwen2.5:3b) | 4.5/5 |
| 2026-06-14 | text2vec-bge-large-chinese | main (DeepSeek v4-pro) | 2/5 |

**退化分析:**
- text2vec-bge-large-chinese 纯中文模型 + DeepSeek main B 层组合对中文短查询覆盖面不足
- 导航栏/猫咪/论文三个常见场景全部漏过
- `investigate` 命中说明 B 层语义匹配有产出，但输出的是标签而非真实 skill 名——映射断裂
- bge-m3 基准（4.5/5）是 A层关键词+B层ollama 的组合，本次是纯 B层裸奔（A层=0）

### SSR echo 格式 bug（新发现）

**症状:** 用户消息中 `[SSR] 建议加载:\n` 冒号后为空，skill 名不显示。

**根因:** echo 输出使用字面量 `\n`（反斜杠+n）而非实际换行符。skill 名在冒号之前被截断或格式处理失败。

**复现:** 消息 2（KeyError）和消息 5（茅台均线）均出现——日志确认 B 层命中，但用户看到的 echo 为空。

## 测3: Reasonix 集成（CMG 非干扰）

`read_file` 读取 `~/.hermes/plugins/ssr/__init__.py` 第 2 行成功，CMG 未拦截。

cmg-guard 日志记录 `ban_vague_answers`/`ban_packaging_missing_files`/`ban_skill_edit_use_right_tool` 均命中对话内容，无一条针对 `read_file` 操作。v1.3.2 读写分流修复生效。

## 待修项

1. **A 层持久化**（v0.6.2 修复未根治）——重启后仍归零
2. **B 层覆盖面**——DeepSeek main 向量对中文短查询命中率低，考虑换 bge-m3 或混合方案
3. **SSR echo 格式**——`\n` 字面量 + skill 名截断
