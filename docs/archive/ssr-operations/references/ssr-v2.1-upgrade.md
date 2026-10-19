# SSR v2.1 升级参考 (2026-06-23)

## 升级内容

| 功能 | 代码位置 |
|------|---------|
| Gate prompt 配置化 | `_call_llm_intent(..., gate_prompt)` 从 `intent_gate.prompt` 读 |
| 元对话检测 | `_intent_gate` 内 `meta_detection` 层，7 条正则 + 任务动词安全阀 |
| 自循环 stub | `boost_skill()` API + `preferences.json` + `_SESSION_RECOMMENDED` |

## 版本号同步清单

11 文件：
- `plugin.yaml` (version 字段)
- `__init__.py` (5 处)
- `test_ssr.py` (2 处)
- `dashboard.py` (1 处)
- `README.md` (版本历史)
- `CHANGELOG.md` (新条目)
- `ssr-operations/SKILL.md` (version + description)
- `master-status.md` (当前版本)
- `v2.1-self-loop/task_plan.md` (实施记录)
- CMG SKILL.md (SSR 引用)
- memory (版本)

## config.yaml 写入方式

`hermes config set` 可以写入 config.yaml（不会被沙箱拦截）：

```bash
hermes config set ssr.intent_gate.prompt ''
hermes config set ssr.meta_detection.enabled false
hermes config set 'ssr.meta_detection.patterns' '["pat1", "pat2"]'
```

> 注意：JSON 数组可能被存为字符串而非 YAML 列表。写入后验证格式——如果 patterns 是字符串，用 Python 重写：`yaml.dump(config, f, allow_unicode=True)`。

## 语法验证

改完代码后必须运行：
```bash
python3 -c "compile(open('$HOME/.hermes/plugins/ssr/__init__.py').read(), '__init__.py', 'exec')"
```

## 重启

所有代码/config 改完后，重启 Hermes（完整重启，非 /new）。`register()` 只在进程启动时执行一次。
