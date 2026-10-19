# SSR 全量 grep 审计（2026-08-03 实战验证）

用户说「走一遍全量 grep 审计」「现在 ssr 正常的吗」时的完整审计流程。本文件来自 2026-08-03 真实审计：验证了上个会话的修复全部生效，同时发现 4 类漏网残留。

## 审计清单（按顺序执行，每步独立验证）

### 1. 测试套件
```bash
cd ~/.hermes/plugins/ssr && python3 test_ssr.py --quick
```
期望：22+ 通过 / 0 失败。跳过项要区分"正常跳过"（未安装 skill 的 embedding、--quick 模式）和"待验证"。

### 2. 运行时存活
```bash
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -5
```
有 `A 层命中: N 条 (x kw + y emb)` = 插件活着。同时看最近一次重启的注册日志：
```bash
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -3
# 期望形如: skill: 577 | 残骸: 0 | A层: 283+0 | emb: 577 | B层: main
```

### 3. 旧域残留（domain 修复验证）
对比 a_rules.json 规则 domain 集合 vs `__init__.py` L78-115 `DOMAIN_STEMS`：
- 中文域（业务/设计/视频/生图/学术/金融/部署/通讯/音乐）合法
- 英文域（business/design/dev/gamedev/video 等）在 2026-08 修复中已补入 DOMAIN_STEMS，**现在是合法域不是残留**
- 判断标准：域必须出现在 DOMAIN_STEMS keys 里，否则规则 MoE 路由下静默死亡

### 4. 死节点关键词清零验证
上个会话删掉的死节点：DeepSeek原理/种菜/腌发酵/devcontainer/Python库/简化流水线/BIM/dat network
```bash
grep -c "关键词" ~/.hermes/plugins/ssr/a_rules.json  # 应为 0
```

### 5. 双空规则（keywords + skills 双空）
```python
python3 -c "
import json
rules = json.load(open('a_rules.json'))
empty = [p for p,r in rules.items() if not r.get('keywords') and not r.get('skills')]
print('双空死节点:', len(empty))  # 期望 0
"
```

### 6. 伪双空规则（本审计新发现 · 上个会话漏网根因）
**症状：** keywords 非空但匹配不到任何 skill 的 auto 规则。典型例子：
`Reviewtheconversationaboveandu` / `Reviewtheconversationaboveandc`——auto_gen 从系统提示 "Review the conversation above and..." 提取的垃圾关键词，hits=3 还命中过，产出为空。

**为什么漏网：** 上个会话删 8 条"双空"死节点时，这两条 keywords 非空（有 `keywords: ['reviewtheconversationaboveandu']`）不属于双空。但它们匹配不到任何 skill = 命中零产出。

**检测：** 模拟清理逻辑的 keywords 检查——遍历每条 auto 规则 keywords，在 _SKILL_INDEX 里找 `kw in name or kw in description`，`any_match=False` 即伪死：
```python
emb = json.load(open('embeddings.json'))
idx = set(emb.keys())
for p, r in rules.items():
    if r.get('source') == 'manual': continue
    kw = r.get('keywords', [])
    if kw:
        any_match = any(any(k.lower() in n.lower() for n in idx) for k in kw)
        if not any_match:
            print(f'伪死: {p[:60]} -> {kw}')
```

### 7. manual 死引用（清理逻辑永不删除）
`_cleanup_a_rules()` 对 `source=manual` 的规则全部 `continue`（__init__.py L996 死引用清理 + L1015 keywords 检查），所以 **manual 规则引用不存在的 skill 会永久生效**。本会话实例：animejs、react-bits（系统无此 skill，命中后推荐死 skill）。

检测：所有规则（不限 auto）引用的 skill 名 vs 实际安装（embeddings keys + 磁盘 frontmatter name）。manual 命中 = 必须手动修。

### 8. auto 死引用（下次重启自动清）
auto 规则引用不在 _SKILL_INDEX 的 skill（本会话：travel/auto-editor/losslesscut/shotcut/whisperx）→ 启动 `_cleanup_a_rules()` 死引用清理会删除。可不管，但要在报告里说明"下次重启自动清"。

### 9. 重复规则（补 pattern 陷阱）
补规则时若新增一条而非修改原规则，会出现新旧并存：
- 本会话：to-tickets 补"拆.*ticket"分支 → 新规则 `(to.*ticket|...|拆.*ticket|拆.*需求.*ticket)` 与旧规则 `(to.*ticket|...|拆分.*任务.*issue)` 并存，旧的是新的严格子集
- 无实际危害（seen 去重只推一次），但冗余
- **教训：补 pattern 必须改原规则，不新增**

### 10. 死引用验证三步法（防误报）
说"死引用"前必须三步验证，三步都查不到才算真死：
1. `embeddings.json` keys（577 个，精确匹配）
2. 磁盘 SKILL.md frontmatter `name:` 字段（**注意目录名 ≠ frontmatter name**：目录 `fantasy-life-force-portrait` 的 name 是 `fantasy-life-force-portrait-photography`；`find -type d -name "*x*"` 会漏）
3. 系统提示 available_skills（~/.agents/skills 里的 skill Hermes 也加载，如 impeccable）

本会话实例：cinema-dna-21x9x3/impeccable/funai-skill 目录 find 不到但真实存在（creative/ 和 ~/.agents/skills/），是 embedding 缺口不是死引用。

### 11. 设计内引用（不算死，用户确认过）
- ppt-master → ~/ppt-master 独立仓库（非 Hermes skill）
- originkit → MCP 工具
- life-services (快递/汇率/油价/节假日) → ~/.hermes/scripts/life-services.py 脚本
用户明确允许 SSR 匹配非 skill 工具/脚本/App（纠正过两次），这些是设计内引用。

## 审计报告输出格式

结论先行（✅ 正常 / ⚠️ 有残留），然后：
- 验证通过的修复项（列证据：数字/日志行）
- 新发现问题按 P1-P4 分级：P1 垃圾规则（要修）、P2 重复（可修）、P3 manual 死引用（要修）、P4 auto 死引用（自动清）
- 明确区分"设计内引用"vs"真死引用"，避免误删

## 修复注意事项（如果用户让修）
- 改 a_rules.json 前必须 `cp a_rules.json a_rules.json.bak.$(date +%m%d%H%M)`
- 删规则用 Python 精确删除单条，不用 write_file 整文件覆盖
- 改完重跑 test_ssr.py 验证
