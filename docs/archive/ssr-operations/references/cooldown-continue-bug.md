# SSR 冷却 bug — shown_recently 标签 vs continue 跳过 (2026-06-14)

## 症状
SSR 的智能冷却机制形同虚设。同一 skill 在 60s 内被反复推荐，用户感觉 SSR 永远在推同样的东西。

## 根因
`_pre_llm_call` 的 A 层和 B 层冷却循环（`__init__.py` L1537-1540 和 L1584-1587）中，
冷却检测到技能仍在冷却期时，只设置 `s["shown_recently"] = True` **标签**，但该 skill 仍被 `fresh.append(s)` 加入到推荐列表。

```python
# ❌ 旧代码 — shown_recently 只是标签，不阻止展示
if name in rec_count:
    last_t, _ = rec_count[name]
    if now - last_t < cooldown:
        s["shown_recently"] = True  # 标签，skill 仍然显示！
rec_count[name] = (now, rec_count.get(name, (0, 0))[1] + 1)
fresh.append(s)
```

`shown_recently` 只在后续截断排序中影响优先级（非冷却优先），不阻止展示。
当 `len(fresh) <= max_total` 时所有 skill 全部展示，冷却形同虚设。

## 修复
将 `shown_recently = True` 改为 `continue`，直接跳过仍在冷却期内的 skill：

```python
# ✅ 修复后 — 冷却期内直接跳过
if name in rec_count:
    last_t, _ = rec_count[name]
    if now - last_t < cooldown:
        continue  # 仍在冷却期内，跳过此 skill
rec_count[name] = (now, rec_count.get(name, (0, 0))[1] + 1)
fresh.append(s)
```

同时删除截断排序中的 `shown_recently` 两维排序（已无必要）。

## 影响
- A 层冷却循环: `__init__.py` L1537-1540 + L1548-1550
- B 层冷却循环: `__init__.py` L1584-1587 + L1594-1595

## 验证
重启 Hermes → 发同一条消息两次（间隔 < 冷却期）→ 第二次不应再推荐同 skill。
