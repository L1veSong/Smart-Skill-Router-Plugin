# SSR A 层缺口：Skill 创作/编辑意图检测

> 发现：2026-07-25 | 状态：待修复

## 缺口

SSR A 层缺少以下检测规则：

**检测用户意图：创建/修改/编辑 skill**
**应推荐：** `skill-creator` + `hermes-agent-skill-authoring`（创作时）+ `writing-skills`（重写时）

## 缺失场景

当用户说以下内容时，SSR 未推荐任何 skill 创作工具：

- "把它变成调用 claude code 的 ccgs"（修改 game-design-reference）
- "配到 ssr"（编辑 SSR A 层规则）
- "这次为啥又没用 skill creator？"（用户明确指出缺失）

## 建议规则

以下正则模式应添加到 `a_rules.json`：

```json
{
  "(?i)(改.*skill|修改.*skill|更新.*skill|skill.*改成|把这个.*变成.*skill|配到.*ssr|加.*规则|写.*skill|创建.*skill)": {
    "source": "manual",
    "phases": ["CREATE"],
    "skills": [
      {"name": "skill-creator", "phase": "CREATE"},
      {"name": "hermes-agent-skill-authoring", "phase": "CREATE"}
    ],
    "domain": "skill-authoring"
  },
  "(?i)(写.*SKILL|编辑.*SKILL|重写.*skill|skill.*重写)": {
    "source": "manual",
    "phases": ["CREATE"],
    "skills": [
      {"name": "skill-creator", "phase": "CREATE"}
    ],
    "domain": "skill-authoring"
  }
}
```

## 添加方式

```bash
python3 << 'EOF'
import json, shutil
from datetime import datetime

path = "/Users/holiday_home/.hermes/plugins/ssr/a_rules.json"
shutil.copy(path, path + f".bak.{datetime.now().strftime('%m%d%H%M')}")

with open(path) as f:
    rules = json.load(f)

new_rules = {
    "(?i)(改.*skill|修改.*skill|更新.*skill|skill.*改成|把这个.*变成.*skill|配到.*ssr|加.*规则|写.*skill|创建.*skill)": {
        "source": "manual",
        "phases": ["CREATE"],
        "skills": [
            {"name": "skill-creator", "phase": "CREATE"},
            {"name": "hermes-agent-skill-authoring", "phase": "CREATE"}
        ],
        "domain": "skill-authoring"
    },
}

for pattern, value in new_rules.items():
    if pattern not in rules:
        rules[pattern] = value

with open(path, 'w') as f:
    json.dump(rules, f, ensure_ascii=False, indent=2)

print(f"Total rules: {len(rules)}")
EOF
```

## 验证

```bash
grep -c "skill-creator" ~/.hermes/plugins/ssr/a_rules.json
# 应该 >= 1（之前为 0）
```
