# Auto-Gen × Cleanup 执行顺序 Bug

**发现日期**: 2026-07-23
**版本**: SSR v2.3.0
**文件**: `~/.hermes/plugins/ssr/__init__.py`

## 症状

清理 a_rules.json（6789 条垃圾 → 10 条），重启 Hermes 后又回到 6770 条。

```
加载 A 层规则: 10 条
清理后 A 层规则: 10 条
auto-gen: +6760 条 → A 层共 6770 条
```

## 根因

`register()` 中的执行顺序：

```
旧（错误）:
  _load_a_rules()       → 6770 条
  _cleanup_a_rules()    → 10 条（内存）
  _auto_gen_a_rules()   → +6760 条（从 438 skill description 提取关键词）
  _save_a_rules()       → 6770 条写回磁盘  ← 清理成果被覆盖
```

`_auto_gen_a_rules()` STOP_WORDS 只有 18 词（the/and/use/...），而 `_cleanup_a_rules()` GARBAGE_STOP_WORDS 有 50 词。auto-gen 产出大量单英文词（era/gen/art/doc/env/see/new/old…）未被自身 STOP_WORDS 过滤，必须靠 cleanup 的 50 词表拦截。但 cleanup 跑在 auto-gen 前面 → 白干。

## 修复

```python
# 新（正确）:
#   _load_a_rules()       → 从磁盘加载
#   _auto_gen_a_rules()   → 生成新规则
#   _cleanup_a_rules()    → 清理（包括 auto-gen 产出的垃圾）
#   _save_a_rules()       → 保存清理后的结果
```

具体改动：SSR `__init__.py` `register()` 函数，`_cleanup_a_rules()` + `_save_a_rules()` 移到 auto-gen 块之后。无论 `auto_gen_rules` 是否开启都执行 `_save_a_rules()`。

## 验证

```bash
grep '加载 A 层\|清理后 A 层\|auto-gen.*条' ~/.hermes/logs/agent.log | tail -3
```

期望：清理后规则数 ≈ auto-gen 新增前的规则数。

## 关联

- SSR pitfall 42: 同样是不分析执行顺序就行动
- 长期: `_auto_gen_a_rules()` STOP_WORDS 应与 `_cleanup_a_rules()` GARBAGE_STOP_WORDS 同步（18 vs 50）
