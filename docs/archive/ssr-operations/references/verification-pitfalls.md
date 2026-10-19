# SSR 验证坑点实录

> 日期: 2026-06-05
> 来源: 用户测试 SSR 时 AI 误判 B 层后端

## 坑点 1: 日志消息不可信——"Ollama 调用失败"≠ B 层是 Ollama

**现场：** agent.log 显示 `B 层 Ollama 调用失败（降级跳过）: timed out`。AI 据此断定"B 层是 Ollama，Ollama 挂了"。用户纠正："b层不是ollama"。

**根因：** SSR `__init__.py` 第 449-461 行的冷启动预热代码硬编码了 Ollama API 格式：

```python
httpx.post(
    f"{_b_base_url()}/api/generate",  # ← Ollama 专用端点
    json={"model": _b_model(), "prompt": "warmup", ...},
    ...
)
```

无论 `b_layer.provider` 是 main/ollama/openai，预热都往 `/api/generate` 发。provider=main 时 `_b_base_url()` 返回 `https://api.deepseek.com/v1`，DeepSeek 没有 `/api/generate` → 超时 → 日志写"Ollama 调用失败"。

**教训：** 
1. 判断 B 层后端 → 读 `config.yaml` 的 `ssr.b_layer.provider`，不信日志里的 provider 名
2. 预热代码的日志消息有误导性——这是 SSR 自身的 bug，不是配置问题

## 坑点 2: 会话级日志隔离

SSR 日志按 session_id 分组。本会话的 B 层超时（`20260605_014040_ec6344`）不代表前一会话（`20260604_222352_085ec3`）的状态。前一会话是 DeepSeek 401，本会话是超时——两个不同会话、不同错误。

判断 SSR 状态时只看当前 session_id 的日志行。

## 坑点 3: A 层关键词误匹配

用户说"测试ssr" → A 层命中 `technical-analysis`, `tushare-finance`, `diagnose`。原因：关键词"测试"撞到了技术分析/诊断类 skill 的关键词表。

A 层是关键词匹配，不是语义理解。对口语化请求（"测试ssr"）可能完全误匹配。B 层（LLM 语义）才是兜底——B 层挂了就只剩盲猜。

## 坑点 4: A 层日志搜索关键词错误（2026-07-22 实战）

**症状：** 用 `grep '关键词匹配命中\|Embedding 命中' agent.log` 搜 A 层活动 → 零结果。误判为"A 层完全没在工作"。

**根因：** SSR 的实际日志格式是：

```
[ssr] A 层命中: N 条 (X kw + Y emb) → ['skill1', 'skill2', ...]
```

不是 `关键词匹配命中`、不是 `Embedding 命中`。这两个词只出现在代码注释里，从未写入日志。

**正确搜索：**
```bash
# ✅ A 层日志
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -5

# ✅ A 层无命中（DEBUG 级别）
grep 'A 层无命中' ~/.hermes/logs/agent.log | tail -5

# ❌ 错误搜索词——永远不会匹配
grep '关键词匹配命中' ~/.hermes/logs/agent.log    # 零结果
grep 'Embedding 命中' ~/.hermes/logs/agent.log     # 零结果
```

**教训：** 诊断前先确认日志格式。`grep` 搜代码注释里的词 = 假阴性。

## 坑点 5: v2.4.0-MoE 升级后域名规则丢失（2026-07-23 实战）

**症状：** SSR v2.4.0-MoE 重启后，A 层规则 33 条（预期 36）。"电影那种感觉""新疆玩几天拍照片"无匹配。a_rules.json 只有 4 个域（travel/writing/storage/map），生图域 10 条规则完全丢失。

**根因：** MoE 重构新增 `domain` 字段 + `_route_domains()` 路由。升级只迁移了 4 个域，旧版生图/金融/debug 域规则未迁移——它们没有 `domain` 字段，路由层无法激活。

**教训：**
1. 升级后必须验证域覆盖：`python3 -c "import json; rules=json.load(open('...a_rules.json')); print(set(r.get('domain','') for r in rules.values()))"`
2. 缺失规则从备份恢复 + 补 `domain` 字段
3. 完整恢复流程 → `references/moe-upgrade-domain-loss.md`

## 坑点 6: P0 gate 日志是 DEBUG 级别——`grep 'SSR P0'` 永远抓不到（2026-07-24 实战）

**现场：** 用户写好了 P0 gate 代码（`_route_domains()` 中 `logger.debug('SSR P0: gate closed — no domain activated')`），重启后用 `grep 'SSR P0' ~/.hermes/logs/agent.log | tail -5` 验证——零结果。用户质疑"P0 代码没生效"。

**根因：**
1. `SSR P0: gate closed` 是 `logger.debug()` 级别，默认日志不输出 DEBUG
2. gate 只在**零 domain 激活**时才输出（即用户消息没有任何词干命中），有命中时不输出
3. 两重过滤叠加 → 这个日志行几乎永远不会出现在 `grep` 结果中

**正确的存活验证命令：**
```bash
# 注册确认（一条命令，INFO 级别，必定输出）
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# 期望输出：skill: N | 残骸: 0 | A层: N+0 | emb: N | B层: main

# A 层命中确认
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -3

# B 层命中确认
grep 'B 层命中' ~/.hermes/logs/agent.log | tail -3
```

**噪声量化方法（判断 SSR 是否"高命中低噪声"）：**
```bash
# 统计最近 N 轮中 A 层推荐被 LLM 筛查静默的比例
grep 'A 层命中\|LLM 筛查' ~/.hermes/logs/agent.log | tail -40
# 健康：LLM筛查静默率 < 70%
# 可接受：70-95%（当前实测 ~95%，embedding 噪声高但 LLM 筛查有效抑制）
# 警告：>95% 且 B 层也无命中 → SSR 形同虚设
```

**教训：** 不要在 DEBUG 级别埋验证用的关键日志。重启验证命令必须以 INFO 级别日志为锚点。

## 坑点 9: LLM 筛查误杀有效推荐——写作域短指令被判"语境无关"（2026-07-25 实战）

**现场：** 用户说"帮我写一篇小说"，A 层正确匹配了 `claude-code`, `khazix-writer`, `writing-fragments`, `writing-shape`。但 LLM 筛查判定"语境无关 → 静默"，推荐被吞。

日志证据：
```
[ssr] A 层命中: 31 条 (2 kw + 30 emb) → ['khazix-writer', 'claude-code', 'writing-fragments', 'dbs-content', 'writing-shape']
[ssr] LLM 筛查: 语境无关 → 静默
```

**根因：** LLM 筛查对短指令（<10字）过度保守。"帮我写一篇小说"是明确的写作意图，但筛查模型可能因缺少"类型/题材/字数"等细节判定为"不明确"→静默。

**与坑点 8 的关系：** 坑点 8 说 LLM 筛查有效抑制 embedding 噪声（95% 静默率是正常的）。但本坑点揭示另一面：它也会误杀有效推荐。写作域是重灾区——"写小说""写篇文章"这类简洁指令最容易被判"语境无关"。

**缓解方向：**
1. 短指令 + keyword>0 时信任 A 层命中的 keyword 规则，跳过 LLM 筛查
2. 或对 writing 域单独降低筛查保守度
3. 当前实际效果：模型自身知识仍然引导了正确行为（回复推荐了 Claude Code），所以误杀影响可控——但 SSR 推荐的价值被浪费了

**代码修复（2026-07-25 已实施）：**

在 `_pre_llm_call()` 中加了两层安全网：

1. **LLM 筛查否决时信任 A 层**（line ~2480）：当 `_llm_screen()` 返回 `[]` 但 A 层候选 ≥5 条时，不信任 LLM，改用 A 层结果。
```python
if screened is not None:
    if screened or len(candidates) < 5:
        result = screened      # LLM 有结果，或 A 层太弱 → 听 LLM
    else:
        logger.info("LLM 筛查否决但 A 层命中 %d ≥ 5，信任 A 层", len(candidates))
        result = candidates    # LLM 说空但 A 层很强 → 不信 LLM
```

2. **静默时给反馈**（line ~2502）：当 `result=[]` 且 `display=true` 时，不再静默返回 None，而是注入可见反馈消息。
```
[SSR] 本轮静默 (A层 31 条候选，LLM 筛查判定语境无关)
```

**验证方法：**
```bash
grep 'A 层命中.*claude-code\|A 层命中.*khazix-writer' ~/.hermes/logs/agent.log | tail -5
# 如果命中行下一行跟着"LLM 筛查.*静默" → 就是本案
# 修复后应看到 "LLM 筛查否决但 A 层命中" → 安全网生效

## 总结

```
验证 SSR 四步（v2.4.0+）：
1. grep '插件注册完成' agent.log | tail -1  ← 注册确认（INFO级别，必定输出）
2. grep 'A 层命中' agent.log | tail -3      ← A 层活动确认
3. grep -A 8 'b_layer:' config.yaml          ← 确认 B 层真身后端
4. python3 -c "检查 domain 覆盖"             ← v2.4.0+ 必检：生图/旅行/写作/存储/地图
```

## 坑点 12: 测 SSR 匹配必须走真实加载路径——直接 import 模块时 _A_RULES 是空的（2026-08-03 实战）

**现场：** 修完 81 条非法 domain 规则后验证。第一轮用**自己重写的模拟匹配**（复刻 DOMAIN_STEMS + 正则）测出"全过"，但用户追问"测试了吗？"后改用真实模块：`import __init__ as ssr` 后 `len(ssr._A_RULES)` 返回 0，所有消息零命中，差点误判修复无效。

**根因：** `_A_RULES` 不在模块顶层加载——它只在 `register()`（2624 行 `_A_RULES = _load_a_rules()`）里赋值。直接 import 模块时 register() 不执行，`_A_RULES` 保持初始空 dict。测试必须模拟 register() 的加载路径。

**正确测试方法：**
```python
import sys
sys.path.insert(0, '/Users/holiday_home/.hermes/plugins/ssr')
import __init__ as ssr

# 模拟 register() 的加载路径（2623-2645 行逻辑）
ssr._A_RULES = ssr._load_a_rules()
print('加载 A 层规则:', len(ssr._A_RULES))  # 应 > 0

# 然后才能调用真实匹配函数
result = ssr._match_a_layer_keyword('现在做ppt哪个skill好')
names = [s['name'] for s in result] if result else []
print(names)
```

**教训：**
1. 测插件逻辑前先确认状态变量在哪里初始化——查 `register()` 或模块级代码，别假设 import 即就绪
2. 自己重写匹配逻辑做"模拟测试"只能算逻辑推演，必须走真实函数才算验证（用户问"测试了吗"就是这个意思）
3. 验证证据必须来自真实代码路径的终端输出，不是复刻逻辑的推断结果

## 坑点 13: 空 skills 规则≠必删——有意图的补 skills，双空才是死节点（2026-08-03 实战）

**现场：** test_ssr.py 报 14 条"缺 keywords"。第一反应全删。删除后立刻意识到错了——这些规则有完整 pattern（如"系统排查"→hermes-system-maintenance、"去AI味"→humanizer-zh、"inkos"→webnovel-writer），只是缺 skills 绑定，删了丢失意图识别能力。从备份恢复，改为**补 6 条 + 删 8 条**。

**判据：**
- **补 skills**：pattern 有明确意图且有对应 skill 存在 → 补 `skills: [{"name": "...", "phase": "BUILD"}]`（坑点 7 的正解）
- **删**：keywords 和 skills **双空** → 命中零产出，纯死节点（本案例：DeepSeek原理/种菜/腌发酵/devcontainer/Python库推荐/简化流水线/BIM/dat network 8 条——无对应 skill）

**验证：** 删除前 `cp a_rules.json a_rules.json.bak.$(date +%m%d%H%M)`，删错可恢复。本案例删错后从 `.bak.08032056` 恢复成功。

**教训：** 批量清理死规则前先逐条看 pattern 有没有意图、有没有对应 skill。能补则补，双空才删。用户偏好"能装全装"，删有意图的规则 = 丢能力。

## 坑点 14: test_ssr.py 断言过时——keywords 检查不兼容 skills 新格式（2026-08-03 实战）

**现场：** `test_ssr.py --quick` 报 2 失败：①"所有规则含 keywords" 295 缺 keywords；②"GREEN·代码调试" 命中空。第一反应以为修复引入回归——查 golden 备份（改动前）同样失败，确认是历史遗留。

**根因：**
1. **keywords 断言过时**：v2.4.0 MoE 新格式规则用 `skills` 字段直推（`rule.get("skills")`），旧断言只认 `keywords` 字段 → 295 条新格式规则全误报。修断言：keywords 缺失时检查 skills 存在即可（兼容新旧格式）。
2. **GREEN·代码调试用例与规则不匹配**：测试消息"这段 Python 代码报 KeyError 帮我看看"只有"代码+报错"，规则 pattern 要求"代码类词+调试类词"（如"代码...调试"）→ 永远不命中。修规则 pattern：补 `|(?:代码|程序|脚本|函数).*(?:报错|报|异常|错误|KeyError|TypeError|ValueError|Traceback).*(?:看看|解决|修复|为什么|原因)` 分支。

**正确顺序：** 测试失败先查 golden/历史备份确认是否本次改动引入——不是则修根因（断言过时/规则 pattern 缺口），而不是改测试掩盖。

**验证：** 修复后 `python3 test_ssr.py --quick` → 🟢 全部通过（24 通过/2 跳过），GREEN 覆盖率 5/5。

## 坑点 11: domain 值必须是 DOMAIN_STEMS 里的合法键——写错域=规则静默死亡（2026-08-03 实战）

**现场：** a_rules.json 里 ppt-master 规则一直在（`source: manual`，skills 直推），但"做ppt"永远不推荐它。guizang-ppt-skill 规则同样中招（靠 B 层 embedding 兜底才偶尔出现）。规则在库、命中条件满足、日志零异常——就是不出现在推荐里。

**根因：** 两条规则的 `domain: "presentation"`，但 DOMAIN_STEMS（`__init__.py` 78-113 行）里**根本没有 presentation 这个域**（PPT 相关词在 `docs` 域下）。`_route_domains()` 永远激活不了 presentation → 766 行 `if rule_domain and rule_domain not in domains: continue` 把规则静默跳过。**无任何日志，无任何错误。**

**与坑点 5 的区别：** 坑点 5 是规则没写 domain 字段（无法激活）；本坑点是 domain 写错值（激活永远失败）。两种都表现为"规则在但永不命中"。

**排查命令：**
```bash
# 找出所有 domain 值不在 DOMAIN_STEMS 里的规则
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

**修复：** `domain: presentation` → `domain: docs`（PPT/文档词都在 docs 域）。修复后模拟验证：
```bash
python3 -c "
import json, re, sys
sys.path.insert(0, '/Users/holiday_home/.hermes/plugins/ssr')
from __init__ import DOMAIN_STEMS
rules = json.load(open('/Users/holiday_home/.hermes/plugins/ssr/a_rules.json'))
msg = '现在做ppt哪个skill好'
domains = {d for d, stems in DOMAIN_STEMS.items() for s in stems if s.lower() in msg.lower()}
hits = [s['name'] for k, r in rules.items() if isinstance(r, dict)
        and (not r.get('domain') or r['domain'] in domains)
        and re.search(k, msg, re.IGNORECASE)
        for s in r.get('skills', [])]
print('HIT:', hits)
"
```

**教训：** 手动加/改 SSR 规则时，domain 字段必须抄 DOMAIN_STEMS 里的现成键。写新域 = 规则进冷宫，且没有日志提示。加规则后必须模拟消息验证命中，不能只看规则文件存在。

**同类全查（2026-08-03 二次发现）：** 修完 ppt-master 一条规则后，顺手全量审计发现 81 条规则、11 个非法域（business/dev/video/design/gamedev/document/leisure/learning/meta/research/knowledge）——全部静默死亡，从最早备份就带着。**发现一条非法 domain 必须全量审计，不能只修被点名的**。审计命令见本坑点排查命令。修复策略：能映射的映射到合法域（video→视频, design→设计, document→docs, gamedev→gaming, research→search, knowledge→obsidian, leisure→macos, meta→system），大块业务域（business/dev/learning）在 DOMAIN_STEMS 补域+词干，词干从规则 pattern 高频词提取（business 补"开头/黄金/爆款/目标/好问题"，gaming 补"GDD/unity/godot/肉鸽/玩法"），个别规则 pattern 补中文口语变体（如 to-tickets 补 拆.*ticket）。

**重启生效（2026-08-03）：** SSR 在模块加载时读规则（`_A_RULES = _load_a_rules()`，__init__.py 2621 行）——**改 a_rules.json 或 DOMAIN_STEMS 后当前会话仍是旧规则，必须重启 Hermes 才生效**。改完不能直接说"修好了"，要告知用户重启后生效，或用模拟验证（python import DOMAIN_STEMS + re.search）证明修复逻辑正确。

## 坑点 10: display=true 但静默无反馈——用户不知道 SSR 跑了（2026-07-25 实战）

**现场：** 用户开启 `ssr.display: true`，但"帮我写一篇小说"无推荐输出。检查日志发现 A 层命中 31 条但 LLM 筛查静默了。用户质疑："我不是开的显示吗？为什么静默？"

**根因：** `display: true` 控制的是**匹配成功后**是否展示推荐。当 SSR 决定静默（意图门控拒绝 或 LLM 筛查判定语境无关）时，`_pre_llm_call` 直接 `return None`——display 开关根本没被检查。用户看到的效果是：SSR 像没装一样安静。

**涉及的静默路径：**
1. `_intent_gate()` → False → 静默（"意图门控: NO → 静默"，DEBUG 级别）
2. `result=[]` → 静默（"LLM 筛查: 语境无关 → 静默"，INFO 级别）

两条路径都不检查 `_display_enabled()`。

**代码修复（2026-07-25 已实施）：**

两处静默路径加 display 感知：
```python
# 路径 1: 意图门控拒绝
if not _intent_gate(user_message):
    if _display_enabled():
        return {"context": "[SSR] 本轮静默 (意图门控判定非任务请求)"}
    return None

# 路径 2: LLM 筛查说空
if not result:
    if _display_enabled():
        return {"context": f"[SSR] 本轮静默 (A层 {a_hit_count} 条候选，LLM 筛查判定语境无关)"}
    return None
```

**效果：** display=true 时，SSR 永远有输出——要么推荐 skill，要么反馈静默原因。用户不再猜测"SSR 是不是没装/坏了"。

## 坑点 7: 空 skills 规则是死节点——关键词命中但零推荐产出（2026-07-24 实战）

**现场：** 审计 a_rules.json 发现 33 条手动规则 skills=[]。用户问"为什么不修"，AI 第一轮错误判定为"MoE 域路由规则，走 embedding"——未验证代码路径就下结论。用户追回后才读代码确认：domain 激活走的是 DOMAIN_STEMS（代码层 272 词干），不是 a_rules.json → 空 skills 规则在 A 层管线中确实是死节点。

**根因：** 这些规则是 `src=manual`，用户在早期手动定义了关键词模式，但未绑定具体 skill。当关键词命中时，`rule.get("skills", [])` 返回空列表 → 无推荐产出。

**诊断命令：**
```bash
python3 -c "
import json
with open('~/.hermes/plugins/ssr/a_rules.json') as f:
    rules = json.load(f)
empty = [(kw, r.get('domain','?')) for kw, r in rules.items()
         if isinstance(r, dict) and not r.get('skills', [])]
print(f'空skills规则: {len(empty)} 条')
for kw, domain in empty:
    print(f'  [{domain}] {kw[:100]}')
"
```

**修复：** 逐条补 skills 字段——关键词已经定义好了，只需绑定对应的 skill 名称。补完后的规则在 A 层 keyword 命中时能直接产出推荐。

**教训：** 不能凭分类名称推断代码行为。说"这是域路由规则"前必须先验证：domain 激活走的是哪条代码路径？skills 字段在哪个环节被消费？

## 坑点 8: A 层 embedding 噪声高——95% 被 LLM 筛查静默，B 层才是实际推荐主力（2026-07-24 实战）

**现场：** 用户质疑"SSR 不是靠 A 层吗，为什么实际靠 B 层？"审计最近 20 轮日志：
- A 层 embedding: 30 条/轮，LLM 筛查静默 19/20 轮（95%）
- A 层 keyword: 仅 1/20 轮有 kw>0（用户明确说"ssr""grep"时才触发）
- B 层: 每轮命中 1-6 条，准确度明显更高（旅行→travel-plan-request，论文→nature-citation，系统→storage-analyzer）

**根因：** embedding 对短消息/歧义消息判别力天然弱。confidence_threshold=0.62 不够高，30 条相似度都过阈值但几乎都不相关。LLM 筛查有效抑制噪声（用户看不到垃圾推荐），但每轮多烧 30 次 embedding API 调用。

**不是 bug，是架构现实。** 改进方向：
1. 补全空 skills 规则 → A 层 keyword 路径产生实际推荐
2. 校准 embedding 阈值（可能提到 0.70-0.75 减少噪声）
3. 接受短消息场景下 B 层为主力

**诊断命令（噪声率）：**
```bash
# 最近 40 条 A 层/LLM筛查 日志
grep 'A 层命中\|LLM 筛查' ~/.hermes/logs/agent.log | tail -40
# 数一下：LLM筛查静默次数 / A层命中次数 = 噪声率
```
