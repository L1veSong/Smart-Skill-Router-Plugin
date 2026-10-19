# A 层规则缺口审计 (2026-07-25)

## 什么时候做

新装一批 skill 后、用户问"全加SSR了吗"时、定期维护。

## 三步审计

### 1. 统计覆盖

```python
import json, os, re

# 加载 A 层规则
with open(os.path.expanduser('~/.hermes/plugins/ssr/a_rules.json')) as f:
    rules = json.load(f)

# 提取所有被引用的 skill 名
rule_skills = set()
for k, v in rules.items():
    items = v if isinstance(v, list) else v.get('skills', [])
    for s in items:
        name = s['name'] if isinstance(s, dict) else s
        if name: rule_skills.add(name)
```

### 2. 挑出关键缺失

不是每个 skill 都需要 A 层规则——CC 子技能走 claude-code 路由，B 层 embedding 兜底。**重点关注这类：**

- 用户频繁手动调用的 skill
- 有明确触发词（关键词匹配比 embedding 快 100 倍）
- 顶层调度类（orchestrator/plan/build 阶段）

**不需要 A 层的：**
- Claude Code 子技能（走 claude-code 路由即可）
- 工具类（image_generate/video_generate）
- SSR 自身组件（ssr-operations/smart-search）
- 极小众 skill

### 3. 批量补规则

```python
# 格式：regex → [{name, phase}]
new = {
    "(?i)(关键词1|关键词2|...)": [{"name": "skill-name", "phase": "BUILD"}],
}
```

**phase 选择：**
- PLAN: 计划/调研/分析类
- DESIGN: 设计/规范/审美类
- CREATE: 产出/构建/生成类
- VERIFY: 审查/测试/发布类

**关键词设计原则：**
- 包含中文和英文别名
- 包含动词组合（"做.*计划" 而非仅 "计划"）
- 参考用户实际用语（从 agent.log 看用户怎么说的）

## 本会话实战

| 缺口 skill | 关键词示例 | phase |
|-----------|----------|-------|
| oh-story | oh-story, 拆文分析 | SEARCH |
| chinese-novelist | chinese-novelist, 中文网文 | CREATE |
| webnovel-writer | webnovel-writer, 网文写作 | CREATE |
| originkit | originkit, 列出组件 | BUILD |
| plan | 做计划, plan, 规划方案 | PLAN |
| ralph-loop | ralph, 闭环, 自动循环 | VERIFY |
| travel | 旅行, 机票, 酒店, 攻略 | PLAN |
| github-pr-workflow | PR, pull request, 代码审查 | VERIFY |
| remotion | remotion, 视频编辑 | CREATE |
| imessage | iMessage, 发短信 | BUILD |
| finesse-ui | finesse, 品牌站, landing page | DESIGN |
| frame-smith | frame-smith, 动效视频, 宣传片 | CREATE |

## 验证命令

```bash
# 确认规则写入
python3 -c "import json; r=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(len(r))"

# 确认 A 层命中新规则
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -3
```

## 注意

- 写 a_rules.json 前必 `cp backup`
- 用 `patch` 增量修改，不整文件覆写
- 新增规则后重启 Hermes 生效
