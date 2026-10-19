# SSR Hook 注册成功但未触发（2026-06-14 实战）

## 现象

- Hermes 完整重启（gateway 重连）
- SSR register() 成功：`370 skill | emb: 370 | B层: main`
- `hooks.pre_llm_call: true`
- `plugins.enabled` 含 `ssr`
- **但当前会话 agent.log 无任何 `[ssr]` 输出**
- skill_autoload 和 cmg-guard 的 pre_llm_call 也同时哑火

## 结论（验证后）

**本会话确认为「假性沉默」而非 hook 未触发。**

三层证据：
1. **a_rules.json = 2 bytes** — 重启后被清空，A 层 0 规则，100% 回退 B 层
2. **B 层主模型** — 370 skill 全量喂 DeepSeek，可能超时/不匹配 → 静默返回 None
3. **miss 路径无日志** — `__init__.py` 第 1588-1589 行 `stats["misses"] += 1; return None` 无任何 logger 调用

cmg-guard 的 `transform_llm_output` 正常触发 → Hermes hook 机制无故障。SSR 在工作，只是没产出。

## 与真实故障的区分

| 判据 | 假性沉默 | 真故障 |
|------|:--:|:--:|
| a_rules.json | 空（2 bytes, `{}`） | 可能正常 |
| 发触发消息（"设计登录页"）后 | A/B 层开始命中 | 仍零日志 |
| cmg-guard/skill_autoload | 正常 | 可能正常 |
| embeddings.json | 正常（7-8MB） | 可能空 |

## 诊断步骤（已验证）

```bash
# 1. 确认是完整重启还是 /new
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1

# 2. 检查 a_rules.json 大小（2 bytes = 被清空）
ls -la ~/.hermes/plugins/ssr/a_rules.json
python3 -c "import json; print(len(json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json'))))"

# 3. 检查 embeddings.json（>0 = embedding 层工作）
ls -la ~/.hermes/plugins/ssr/embeddings.json

# 4. 发触发消息验证（"帮我设计一个暗色仪表盘"）→ 查 A 层命中
grep 'A 层命中' ~/.hermes/logs/agent.log | tail -3

# 5. 若仍无 → 真故障；若有 → 假性沉默（本条消息没命中而已）
```

## 相关

- [`silent-miss-path.md`](silent-miss-path.md) — 假性沉默的代码根因和修复方向
- SSR `__init__.py` 第 1588-1589 行 — miss 路径无日志 → **v0.6.2 已修复**（补 `logger.info`）
- `~/.hermes/plans/ssr/smart-skill-router/task_plan.md` — T1-T3 修复计划（3/4 完成）
