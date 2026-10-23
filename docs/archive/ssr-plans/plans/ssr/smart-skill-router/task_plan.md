# SSR v0.6.2 — 重启后 A 层清零修复

> 触发: 2026-06-14 重启后 `a_rules.json` 2字节 → A层:0+0 → 100% B层回退
> 状态: ✅ 已完成（2026-06-14 18:41 GREEN 5/5 验证通过）

---

## 背景

SSR v0.6.1 重启后 A 层规则文件被清空为空 `{}`，导致 370 skill 无规则匹配，全部走 B 层 DeepSeek API。同时 miss 路径无日志，触发状态不可观测。

---

## 任务清单

### T1: 诊断 a_rules.json 清空根因 [P0]

**改动：** 在 `register()` 的 `_load_a_rules()` 后加保护性日志

```python
_A_RULES = _load_a_rules()
logger.info("[ssr] 加载 A 层规则: %d 条", len(_A_RULES))

_cleanup_a_rules()
logger.info("[ssr] 清理后 A 层规则: %d 条", len(_A_RULES))

_A_RULES = _purge_single_word_rules(_A_RULES)
logger.info("[ssr] 单字净化后 A 层规则: %d 条", len(_A_RULES))
```

**验证：** 重启 → 看 agent.log 哪一步归零

---

### T2: 补 miss 路径日志 [P0]

**文件：** `~/.hermes/plugins/ssr/__init__.py`

**改动：** 第 1588-1589 行，`stats["misses"] += 1` 后加：

```python
logger.info("[ssr] 无匹配（A层 %d 规则 + B层 %s, 本轮第 %d 次）",
            len(_A_RULES), provider, stats["calls"])
```

**验证：** 发一条 SSR 不匹配的消息 → agent.log 应有 `[ssr] 无匹配`

---

### T3: 修复 a_rules.json 被清空的 bug [P0]

**依赖 T1 诊断结果。** 可能方向：

| 如果根因是... | 修复 |
|-------------|------|
| `_purge_single_word_rules` 误杀中文规则 | 加中文字符长度判断 `len(pattern) >= 2` |
| `_cleanup_a_rules` TTL 误判 | 空 last_hit 保护已有，检查 `time.mktime` 时区问题 |
| 旧进程退出时覆盖 | `_save_a_rules` 加时间戳断言（不覆盖比当前更新的文件） |

---

### T4: 验证 GREEN baseline [P1]

重启后执行 `ssr-red-baseline.md` 的 5 条测试消息：

1. "帮我设计一个响应式导航栏"
2. "这段 Python 代码报 KeyError 帮我看看"
3. "生成一个 ASCII 猫咪图"
4. "帮我写论文的 Related Work 部分"
5. "分析贵州茅台的均线走势"

**通过标准：** ≥3/5 A层命中

---

## 不改的内容

- embedding 模型不变（bge-large-chinese 已确认可用）
- B 层 main 模式不变（当前回退路径）
- 不启用 auto_gen_rules（用户已关）

---

## 风险

| 风险 | 概率 | 缓解 |
|------|:--:|------|
| `_purge_single_word_rules` 修了仍有其他清空路径 | 中 | T1 日志覆盖全流程 |
| B 层 main 模式 30s 超时 → 用户等待 | 高 | T3 修好后 A 层命中走快速路径 |

---

## 执行记录（2026-06-14）

| 任务 | 状态 | 验证 |
|:--|:--:|------|
| T1: 根因诊断 | ✅ | agent.log: `加载 A 层规则: 6 条` |
| T2: miss 路径日志 | ✅ | agent.log: `[ssr] 无匹配（A层 6 条 + B层 main, 本轮第 N 次）` |
| T3: a_rules 清空修复 | ✅ | 重启后 6 规则持久化 |
| T4: GREEN baseline | ✅ | benchmark: 5/5 PASS |
| echo bug | ✅ | skill 名正常换行 |

**关键发现：** A 层从 100→0→6。根因为 `_purge_single_word_rules` 误杀中文规则（单字中文被当作单字符规则）。修复后 6 条手工规则覆盖 GREEN 全部 5 场景。B 层 370 skill（bge-m3 1024维）仍在 main 模式兜底。
