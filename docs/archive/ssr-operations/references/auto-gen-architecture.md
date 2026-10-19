# SSR Auto-Gen 架构（v0.4.0）

## 问题

v0.3.0 的 A 层规则来自两个源头：
1. 手动编写的 `a_rules.json`（10 条）
2. B 层连续命中 3 次后自动升级（`_promote_to_a`）

问题：10 条规则覆盖不了 200+ skill。B 层升级慢（需连续 3 次命中同一匹配）。结果——SSR 每次只推荐 3-5 个 skill。

## 用户核心洞察

> 「我不想绑定成固定的，不能自动吗？不设限或者怎么样」
> 「所有人都能用还是专属于我的？绑定 244 条 skill 不能缺斤少两」
> 「为什么还要设限？太多也不好吗？」

三个需求：
1. **不设限** — 推荐数量不应受规则数限制
2. **不绑定** — 规则集必须适配任何人的 skill 集，不能写死
3. **不替用户决定** — 不用假设"太多推荐会烦人"

## 解决方案：`_auto_gen_a_rules()`

```python
def _auto_gen_a_rules() -> Dict[str, dict]:
    """从 _SKILL_INDEX 的 description 自动生成 A 层规则。"""
    rules: Dict[str, dict] = {}
    for name, info in _SKILL_INDEX.items():
        desc = info.get("description", "")
        if not desc or len(desc) < 5:
            continue
        keywords = set()
        # 英文 3+ 字母词，过滤停用词
        for word in desc.lower().replace(",", " ").replace("/", " ").split():
            word = word.strip('()[]{}."')
            if re.match(r'^[a-z]{3,}$', word) and word not in STOP_WORDS:
                keywords.add(word)
        # 中文 2-4 字词
        for cw in re.findall(r'[\u4e00-\u9fff]{2,4}', desc):
            keywords.add(cw)
        for kw in keywords:
            rules[re.escape(kw)] = {"skills": [name], "source": "auto-gen"}
    return rules
```

## 调用时机与合并策略

在 `register()` 中，`_load_a_rules()` 之后：

```python
_A_RULES = _load_a_rules()
_cleanup_a_rules()
auto_gen = _auto_gen_a_rules()
# 逐条检查，已有规则不覆盖（B 层升级规则优先级更高）
added = 0
for k, v in auto_gen.items():
    if k not in _A_RULES:
        _A_RULES[k] = v
        added += 1
_save_a_rules(_A_RULES)
```

**关键设计：B 层升级保护。** `_A_RULES.update(auto_gen)` 会覆盖已有规则——改为逐条检查。B 层升级的规则（命中 3 次验证）远优于 auto-gen 粗糙关键词。

## 限制解除（v0.4.0）

| 限制 | 旧值 | 新值 | 位置 |
|-----|------|------|------|
| B 层 prompt | "1-3 个" | "3-8 个" | 3 处 |
| B 层 max_tokens | 100 | 200 | 2 处 |
| A 层上限 | 5 | 10 | `_match_a_layer` |

修改方式：直接 patch 字符串和常量，不需改 config。

## 效果

| | v0.3.0 | v0.4.0 |
|---|--------|--------|
| 规则来源 | 手动 JSON + B 层升级 | 自动扫描 + B 层升级 + 手动 |
| 合并策略 | update 覆盖 | 逐条检查，不覆盖已有 |
| 规则数 | 10 | ~2000（随 skill 数变化） |
| 覆盖 skill | <10 | ~250 |
| 换机器 | 规则作废 | 自动适配新 skill 集 |
| B 层推荐 | 1-3 个 | 3-8 个 |
| A 层上限 | 5 | 10 |

## 日志验证

```
[ssr] 插件注册完成 | 可用 skill: 293 | 残骸: 0 | A 层规则: 2083 (B 层升级: 10, auto-gen: +2073) | B 层: main/ timeout=30s
```

`B 层升级: 10` = 之前累积的高质量规则（持久化保留）。`auto-gen: +2073` = 本次启动新增的自动生成规则。

## 已知局限

**A 层 auto-gen 独立准确率：10%。** 纯关键词匹配无法处理 description 语言与用户自然语言的差距。正确模式是 A 层做冷启动 + B 层语义兜底 → B→A 升级循环提升质量。

**保护策略：** 永远不要 `rm a_rules.json` 不备份。B 层升级规则是学习成果——丢了只能重新积累。CMG 规则 `rule_ban_no_del_a_rules`。

## 代码回归（2026-07-22 发现）

**设计文档（本文）描述的规则格式：**
```python
rules[re.escape(kw)] = {"skills": [name], "source": "auto-gen"}
```

**实际代码 `__init__.py` L907-910：**
```python
rules[pattern] = {
    "keywords": [kw],
    "source": "auto-gen",
}
```

差异：实际代码缺少 `"skills": [name]` 字段。导致 2026-07-22 自动生成的 7264 条规则 skills 全空——每条规则匹配后返回零个推荐。a_rules.json 从 3.4KB 膨胀到 642KB，有效命中率 = 0。需回滚到备份。

**临时修复：** `hermes config set ssr.auto_gen_rules false` 关闭启动时 auto-gen。
**根治：** 在 L907 补上 `"skills": [name]`，并加关键词区分度过滤（同一关键词出现在 >5 个 skill 则跳过）。
