# Force 模式 GREEN 基准测试

> v0.5.1+ | 替代用户逐条发送消息的繁琐流程

## 何时使用

用户说"跑 GREEN"、"测试 SSR 匹配准确率"时，用 execute_code 直接对 `a_rules.json` 做正则匹配——不需要用户逐条输入消息。

## 边界

- 只测 A 层关键词正则匹配
- Embedding 语义匹配需要独立测试（直调 Ollama API）
- B 层需要真实 Hermes 会话（独立 Python 无法导入 hermes_cli）

## 执行模板

```python
import json, os, re

a_rules_path = os.path.expanduser("~/.hermes/plugins/ssr/a_rules.json")
with open(a_rules_path) as f:
    a_rules = json.load(f)

tests = [
    ("帮我设计一个响应式导航栏", ["ui-ux-pro-max", "popular-web-designs"]),
    ("这段 Python 代码报 KeyError 帮我看看", ["diagnose"]),
    ("生成一个 ASCII 猫咪图", ["ascii-art"]),
    ("帮我写论文的 Related Work 部分", ["research-paper-writing", "paper-spine-research"]),
    ("分析贵州茅台的均线走势", ["technical-analysis"]),
]

def extract_skill_names(entry):
    skills = entry.get("skills", []) if isinstance(entry, dict) else entry
    return [s["name"] if isinstance(s, dict) else s for s in skills]

def match(msg, rules):
    results = []
    seen = set()
    for pattern, entry in rules.items():
        try:
            if re.search(pattern, msg):
                for n in extract_skill_names(entry):
                    if n not in seen:
                        results.append(n); seen.add(n)
        except re.error:
            pass
    return results

passed = 0
for i, (msg, expected) in enumerate(tests, 1):
    hits = match(msg, a_rules)
    ok = any(e in hits for e in expected)
    passed += ok
    print(f"{'✅' if ok else '❌'} {i}: '{msg[:30]}' → {hits}")

print(f"{passed}/{len(tests)}")
```

## 结果记录

| 日期 | 结果 | 备注 |
|------|:--:|------|
| 2026-06-09 首次 | 4.5/5 | 测试4 paper-spine≈research-paper 功能等效 |
| 2026-06-09 force | 5/5 | research-paper-writing 已加入 A 层规则 |
