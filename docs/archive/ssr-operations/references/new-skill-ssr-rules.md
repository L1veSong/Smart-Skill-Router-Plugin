# 新装 Skill 套装 → SSR 规则同步

## 问题

装完新 skill 套装后，SSR 不会自动感知这些 skill。不加 A 层规则 = 用户下次问相关问题时 SSR 匹配不到 = 白装。

## 触发条件

用 `npx skills add` 装了一批新 skill 后，必须检查并补充 SSR a_rules.json。

## a_rules.json 规则格式

```json
"(?i)(用户可能说的.*正则.*匹配)": {
  "source": "manual",
  "phases": ["CREATE"],
  "skills": [{"name": "skill-name", "phase": "CREATE"}],
  "domain": "domain-name"
}
```

## 添加流程

1. 备份：`cp a_rules.json a_rules.json.bak.xxx`
2. Python 加载 → 添加规则 → 写回（`json.dump(indent=2, ensure_ascii=False)`）
3. 用测试消息验证正则全部命中
4. 重启 Hermes 或等下次会话重载生效

## 验证脚本

```python
import json, re
with open('~/.hermes/plugins/ssr/a_rules.json') as f:
    rules = json.load(f)
for msg in ["测试消息1", "测试消息2"]:
    matched = []
    for k, v in rules.items():
        if re.search(k, msg):
            for s in v.get('skills', []):
                matched.append(s['name'] if isinstance(s, dict) else s)
    print(f'{msg} → {matched}')
```

## 实战数据 (2026-07-24)

| 套装 | skill 数 | 新增规则 | 域 |
|------|:--:|:--:|------|
| dbskill | 29 | 25 | business |
| hyperframes | 19 | 11 | video |
| remotion | 10 | 已含在 video | video |
| **合计** | | **36** | SSR 139→175 |

验证：29/29 测试消息全部命中。
