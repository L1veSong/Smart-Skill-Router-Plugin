# SSR 双路径架构：auto_gen vs promote — 2026-07-22 实战

## 问题

同一天内 SSR auto-gen 两次复现垃圾规则泛滥：
- 小规模：62 条规则，59 条单英文词，skills 全空
- 大规模：重启后 12 → 7267 条暴增，a_rules.json 从 3.4KB 膨胀到 642KB

PROMOTE_THRESHOLD 已设为 999999，但**无效**——它只阻断了一条路径，另一条照跑。

## 双路径架构

```
启动时 auto_gen  ← _auto_gen_a_rules()  __init__.py line 881-925
    触发: 每次 Hermes 重启
    控制: ssr.auto_gen_rules: false | true (config.yaml)
    门禁: PROMOTE_THRESHOLD ← 不检查！不检查！不检查！

运行时 promote  ← _promote_to_a()      __init__.py line 2313
    触发: 用户消息命中 B 层后被调用
    控制: PROMOTE_THRESHOLD 代码常量 (line 67)
    门禁: PROMOTE_THRESHOLD ← 有效
```

**关键：PROMOTE_THRESHOLD = 999999 只阻断运行时 promote。重启时的 auto_gen 走独立代码路径，完全不检查 PROMOTE_THRESHOLD。**

## 代码 Bug（v2.3.2 及之前）：line 907 缺 skills 字段

### 旧代码（已修复）

```python
# 旧 __init__.py line 905-910
for kw in keywords:
    pattern = _re.escape(kw)
    rules[pattern] = {
        "keywords": [kw],       # ✅ 有关键词
        "source": "auto-gen",   # ✅ 有来源
        # ❌ 没有 "skills" 字段！匹配上了不知道推荐哪个 skill
    }
```

**第二个 Bug：** `name` 变量（skill 名）在 `for name, info` 循环的作用域内，但从没被用过。多 skill 共享同一关键词时后面的覆盖前面的，且无频率过滤。

## 已实施修复（2026-07-22, v2.3.3）

### 修复代码：`__init__.py` 第 881-925 行

```python
def _auto_gen_a_rules() -> Dict[str, dict]:
    """从 _SKILL_INDEX 的 description 自动生成 A 层规则（v2 修复版）。

    两遍扫描：
      1. 建 {keyword: [skill_name, ...]} 频率表
      2. 只为 1~5 个 skill 共享的关键词建规则（过滤泛词）
    已有规则（用户手动添加的）不会被覆盖。
    """
    import re as _re

    STOP_WORDS = frozenset({
        'the', 'and', 'use', 'for', 'this', 'that', 'with', 'when',
        'from', 'your', 'can', 'how', 'are', 'you', 'has', 'its',
        'all', 'not', 'but', 'get', 'any', 'was', 'one', 'out',
    })
    MAX_SKILLS_PER_KW = 5   # 出现超过此数的关键词视为泛词，跳过

    # 第一遍：keyword → [skill_names]
    kw_to_skills: Dict[str, list] = {}
    for name, info in _SKILL_INDEX.items():
        desc = info.get("description", "")
        if not desc or len(desc) < 5:
            continue
        seen: set = set()
        for word in desc.lower().replace(",", " ").replace("/", " ").split():
            word = word.strip('()[]{}."\'')
            if _re.match(r'^[a-z]{3,}$', word) and word not in STOP_WORDS:
                seen.add(word)
        for cw in _re.findall(r'[\u4e00-\u9fff]{2,4}', desc):
            seen.add(cw)
        for kw in seen:
            kw_to_skills.setdefault(kw, []).append(name)

    # 第二遍：建规则（过滤泛词）
    rules: Dict[str, dict] = {}
    for kw, skill_names in kw_to_skills.items():
        if len(skill_names) > MAX_SKILLS_PER_KW:
            continue  # "design""build" 50+ skill 共用，跳过
        pattern = _re.escape(kw)
        rules[pattern] = {
            "keywords": [kw],
            "skills": skill_names,    # ← 补上了
            "source": "auto-gen",
        }
    return rules
```

**关键参数：**
- `MAX_SKILLS_PER_KW = 5` — 出现超过 5 次的关键词视为泛词（如 "design" 出现在 50+ skill description 中），跳过
- `STOP_WORDS` — 常见英文停用词，跳过

### 预期效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 自动规则数 | 7200+ (垃圾) | ~200-400 (全有 skills) |
| skills 字段 | 全空 | 全部填充 |
| 单英文词 | work, dice, fork... | 过滤掉（>5 skill 共用） |

### 调用点保护

```python
# __init__.py line 2370-2383
# 已有手工规则不会被覆盖：
if k not in _A_RULES:      # ← 保护
    _A_RULES[k] = v
```

## 紧急关闭

```bash
hermes config set ssr.auto_gen_rules false
```

## 回滚

```bash
# 备份位置（本会话）：
#   __init__.py → __init__.py.bak.07222328
#   a_rules.json → a_rules.json.bak.07222328
#   a_rules.json.bak.07222130  (修复前的 12 条手工规则)

cp ~/.hermes/plugins/ssr/a_rules.json ~/.hermes/plugins/ssr/a_rules.json.bak.$(date +%m%d%H%M)
cp ~/.hermes/plugins/ssr/a_rules.json.bak.07222130 ~/.hermes/plugins/ssr/a_rules.json
```

## 验证修复

```bash
# 重启 Hermes 后检查
grep 'auto-gen' ~/.hermes/logs/agent.log | tail -3

# 确认无垃圾规则
python3 -c "
import json
with open('$HOME/.hermes/plugins/ssr/a_rules.json') as f:
    rules = json.load(f)
empty = [k for k,v in rules.items() if not v.get('skills')]
print(f'空 skills: {len(empty)}/{len(rules)}')
# 预期: 空 skills = 0
"
```

## 手工规则补漏工作流（GREEN 基准驱动）

```bash
# 1. 跑基准
python3 ~/.hermes/plugins/ssr/test_ssr.py 2>&1 | grep "GREEN.*关键词"

# 2. 看哪个场景没覆盖
# ❌ GREEN·UI设计  → 补规则到 a_rules.json
# ❌ GREEN·ASCII艺术 → 同上

# 3. 补规则模板
# { "pattern": "regex", "keywords": [...], "skills": [...], "source": "manual" }

# 4. 再跑基准验证
python3 ~/.hermes/plugins/ssr/test_ssr.py 2>&1 | grep "GREEN.*覆盖率"
# 预期: 5/5
```
