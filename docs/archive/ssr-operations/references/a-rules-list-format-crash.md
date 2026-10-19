# a_rules.json 混合格式致 SSR 全轮崩溃

> 日期: 2026-07-26
> 来源: 用户发现 SSR 无推荐 + Dashboard HTML 去 AI 味需求

## 症状

SSR 在整个会话中零推荐，agent.log 每轮输出：

```
WARNING [ssr] pre_llm_call 异常（降级跳过）: 'list' object has no attribute 'get'
```

用户看不到任何 SSR 推荐——display=true 时本应至少输出静默原因，但因为崩溃发生在外层 try/except，不会进入 display 路径。

## 根因

`a_rules.json` 中规则有两种格式并存：

```json
// 旧格式 (dict) — 271 条
{"(?i)pattern": {"keywords": [...], "skills": [...], "domain": "writing"}}

// 新格式 (list) — 24 条  ← 由 SSR 代码自动生成
{"(?i)pattern": [{"name": "skill-name", "phase": "PLAN"}, ...]}
```

`_match_a_layer_keyword()` 和垃圾清理函数遍历 `_A_RULES.items()` 时，对所有 value 无条件调用 `.get()`：

```python
for pattern, rule in _A_RULES.items():
    rule_domain = rule.get("domain", "")   # ← rule 是 list 时崩溃
```

24 条 list 格式规则 ≈ 每次遍历 8% 概率命中 → 几乎每轮都崩。

## 修复（双重保险）

### 1. 加载时归一化（治本）

在 `_load_a_rules()` return 前加：

```python
# 归一化: 把 list 格式的 value 转为 dict 格式
normalized = 0
for k, v in list(rules.items()):
    if isinstance(v, list):
        rules[k] = {"skills": v, "source": "auto", "priority": 1, "hits": 0}
        normalized += 1
if normalized:
    logger.info("[ssr] 归一化 list→dict: %d 条", normalized)
```

### 2. 关键词匹配器加 guard（兜底）

```python
for pattern, rule in _A_RULES.items():
    if isinstance(rule, list):   # ← 双重保险
        continue
    rule_domain = rule.get("domain", "")
```

## 验证

```bash
# 重启后检查：不应再有 "list object has no attribute" 错误
grep "pre_llm_call 异常" ~/.hermes/logs/agent.log | tail -5

# 应看到归一化日志
grep "归一化 list→dict" ~/.hermes/logs/agent.log | head -1
# 期望: [ssr] 归一化 list→dict: 24 条

# 确认 A 层恢复工作
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -3
```

## 教训

1. **JSON 数据文件出现多态格式时，必须在加载层做归一化。** 指望每个消费方各自做类型检查 = 到处埋雷。
2. **SSR 的 `pre_llm_call` 外层 try/except 虽能防止进程崩溃，但也吞掉了用户侧的反馈。** 崩溃时 display=true 无输出，用户不知道是坏了还是没匹配。考虑在 except 分支也注入可见消息。
3. **"display=true 但无输出"本身就是诊断信号。** 下次遇到用户说 SSR 没推荐，第一步就是 `grep 'pre_llm_call 异常'`。
