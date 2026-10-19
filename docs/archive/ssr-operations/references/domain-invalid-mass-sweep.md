# SSR 非法 domain 规则批量死亡实录（2026-08-03）

## 症状

a_rules.json 中 81 条 manual 规则带 `domain` 字段，但值不在 `DOMAIN_STEMS`（__init__.py 78-113 行）里。
这些规则从 MoE 域路由（v2.4.0）上线起就静默死亡：规则在库、命中条件满足、日志零异常，但推荐永不输出。
排查起点是 ppt-master 规则 `domain: "presentation"` 永不命中——扩查发现是系统性问题，不是单条规则的事。

## 根因

`_route_domains()` 只能激活 DOMAIN_STEMS 里存在的域；766 行 `if rule_domain and rule_domain not in domains: continue` 把非法域规则静默跳过。无任何日志、无任何错误。规则作者写域时用了自造的语义域（business/dev/video/design…），但路由表里没有。

## 诊断命令（找出所有非法域规则）

```bash
python3 -c "
import json, sys
sys.path.insert(0, '/Users/holiday_home/.hermes/plugins/ssr')
from __init__ import DOMAIN_STEMS
rules = json.load(open('/Users/holiday_home/.hermes/plugins/ssr/a_rules.json'))
valid = set(DOMAIN_STEMS.keys())
bad = [(k[:60], r.get('domain','')) for k, r in rules.items()
       if isinstance(r, dict) and r.get('domain') and r['domain'] not in valid]
print('非法 domain 规则:', len(bad))
for k, d in bad: print(f'  [{d}] {k}')
"
```

## 本次修复规模

11 个非法域 / 81 条规则：

| 非法域 | 条数 | 修复方式 |
|--------|------|----------|
| business | 25 | DOMAIN_STEMS 新增 business 域 + 词干 |
| dev | 20 | DOMAIN_STEMS 新增 dev 域 + 词干 |
| video | 11 | 映射 → 视频 |
| design | 8 | 映射 → 设计 |
| gamedev | 8 | 映射 → gaming |
| document | 4 | 映射 → docs |
| leisure | 1 | 映射 → macos |
| learning | 1 | DOMAIN_STEMS 新增 learning 域 |
| meta | 1 | 映射 → system |
| research | 1 | 映射 → search |
| knowledge | 1 | 映射 → obsidian |

## 修复流程

1. 备份：`cp a_rules.json a_rules.json.bak.$(date +%m%d%H%M)`，改 __init__.py 前同样备份
2. 能映射的改 domain 值（映射表见上）；无对应域的（business/dev/learning）在 DOMAIN_STEMS 补域 + 词干
3. 词干必须覆盖该域规则的触发词，否则补了域还是死：
   - business 补：开头/黄金/爆款/目标/好问题/复盘/同行/课程（dbs-hook、dbs-goal 等规则的触发词）
   - gaming 补：GDD/unity/godot/unreal/ue5/引擎/肉鸽/rogue/roguelike/玩法/独立游戏/小游戏
4. 顺手修规则 pattern 缺口：to-tickets 补中文口语 `拆.*ticket|拆.*需求.*ticket`

## 验证（必须走真实代码路径）

⚠️ 关键坑：`_A_RULES` 在 `register()`（2624 行）里才加载，直接 `import __init__` 时它是**空的**！
模拟验证必须手动调 `_load_a_rules()` 复现 register() 的加载：

```python
import sys, json
sys.path.insert(0, '/Users/holiday_home/.hermes/plugins/ssr')
import __init__ as ssr
ssr._A_RULES = ssr._load_a_rules()   # 模拟 register() 加载，否则 _A_RULES 为 {}
# 然后调 ssr._match_a_layer_keyword('现在做ppt哪个skill好') 验证命中
```

验收标准：
- 非法域规则数必须为 0
- 域路由关键场景逐条回归：PPT / business(dbs-*) / dev(code review、ticket、spec、merge) / gaming(GDD、godot、肉鸽) / learning(teach) / knowledge(唐诗、知识库) / leisure(附近)
- 检查 register() 启动清理不会误删：manual 规则 cleanup 跳过（993/1012 行 continue），无 last_hit 跳过 TTL 检查

## 生效条件

SSR 在模块加载 / register() 时读规则（`_A_RULES = _load_a_rules()` 2624 行）。**改 a_rules.json 或 DOMAIN_STEMS 后必须重启 Hermes 才生效**——当前会话仍是旧规则，模拟验证通过 ≠ 当前会话生效。

## 预防

- 手动加 SSR 规则时，domain 值必须抄 DOMAIN_STEMS 里的现成键，或同步在 DOMAIN_STEMS 补域+词干
- 加规则后必须用真实代码路径（_load_a_rules → _match_a_layer_keyword）模拟验证命中，不能只看规则文件存在
- 版本升级（如 MoE 域路由）后全量审计 domain 覆盖（关联坑点 5、坑点 11）
