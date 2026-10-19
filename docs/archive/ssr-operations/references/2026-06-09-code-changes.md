# 2026-06-09 SSR Code Changes (v0.3 → v0.4-unlimited)

## B-layer: Unlimited Recommendations

**Before:**
```python
# __init__.py _build_b_prompt
return f"""你是一个技能匹配器。根据用户消息，从以下可用技能中选择最匹配的 1-3 个。"""
# ...
{"max_tokens": 100}
```

**After:**
```python
return f"""你是一个技能匹配器。理解用户任务意图，匹配所有可能相关的技能。按阶段分组（DISCOVER调研→PLAN规划→BUILD实现→VERIFY验证）。只匹配明确相关的，不猜。不确定就少选。"""
# ...
{"max_tokens": 500}
```

## A-layer: Remove Limit

**Before:**
```python
for _pattern, rule in candidates:
    for skill_info in rule.get("skills", []):
        result.append(...)
        if len(result) >= 5:  # ← hard limit
            break
    if len(result) >= 5:       # ← hard limit
        break
```

**After:**
```python
for _pattern, rule in candidates:
    for skill_info in rule.get("skills", []):
        result.append(...)
        # No limit — collect ALL matches
    # No limit
```

## Auto-gen: Don't Overwrite B-layer Rules

**Before:**
```python
_A_RULES.update(auto_gen)  # overwrites existing!
```

**After:**
```python
added = 0
for k, v in auto_gen.items():
    if k not in _A_RULES:
        _A_RULES[k] = v
        added += 1
# Existing rules (B-layer upgraded) preserved
```

## Log Format

**Before:**
```
[ssr] 插件注册完成 | 可用 skill: 293 | A 层规则: 10 | B 层: main/ timeout=30s
```

**After:**
```
[ssr] 插件注册完成 | 可用 skill: 293 | 残骸: 0 | A 层规则: 1204 (B 层升级: 0, auto-gen: +1204) | B 层: main/ timeout=30s
```

## User Corrections (Session Trail)

1. "ssr只推荐5个我记得。那肯定不够用啊" → B-layer prompt 1-3 → 3-8
2. "那为什么还要设限？太多也不好吗？" → max_tokens 100 → 200, A-layer 5 → 10
3. "无限推荐不就好了吗？" → all limits removed, A-layer collects all matches
4. "所有人都能用还是专属于我的？" → auto-gen made dynamic, not hardcoded to local skill set
5. "错误记住" → CMG rule_ban_no_del_a_rules + rule_gap_ssr_no_limit
