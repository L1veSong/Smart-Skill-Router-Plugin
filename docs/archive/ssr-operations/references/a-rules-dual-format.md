# a_rules.json 双格式共存 — 2026-07-25

## 问题

`a_rules.json` 的 value 字段同时存在两种格式，读取代码必须兼容。

## 两种格式

```python
# 格式 A: list — 新规则、auto-gen、本次手动添加
"(?i)(写.*小说|写.*网文)": [
    {"name": "claude-code", "phase": "CREATE"}
]

# 格式 B: dict — 旧规则、早期手动规则
"(?i)(设计|ui.*设计|设计.*系统)": {
    "skills": [...],
    "source": "manual",
    "domain": "设计",
    "phases": ["CREATE"]
}
```

## 区别

| 字段 | 格式 A (list) | 格式 B (dict) |
|------|:---:|:---:|
| skills 位置 | 直接数组元素 | `["skills"]` 子字段 |
| source 标记 | 无 | `"source": "manual"` |
| domain | 无 | 可选 |
| phases | 在元素内 `phase` | 顶层 `phases` |

## 正确读取代码

```python
v = rules[key]
if isinstance(v, list):
    # 格式 A
    skills = [s["name"] if isinstance(s, dict) else s for s in v]
elif isinstance(v, dict):
    # 格式 B
    skills = [s["name"] if isinstance(s, dict) else s 
              for s in v.get("skills", [])]
```

## 错误示例

```python
# ❌ 假设所有值都是 dict → 遇到 list 格式 crash
skills = v.get('skills', [])  # AttributeError: 'list' object has no attribute 'get'
```

## 实战记录

2026-07-25: 审计脚本 `python3 -c` 遍历 a_rules.json 统计覆盖 skill 时 crash，根因即此。
