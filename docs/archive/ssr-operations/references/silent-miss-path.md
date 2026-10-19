# SSR 假性沉默：A 层 0 规则 + B 层 miss → 零日志（2026-06-14 实战）

## 症状

- SSR 注册成功：`emb: >0, B层: main, pre_llm_call: true`
- 当前会话 agent.log 无任何 `[ssr]` 输出 —— 连 session stats 都没有
- 用户怀疑 "SSR 挂了" 或 "hook 没触发"
- **实际 SSR hook 执行了，但 A 层空 + B 层无匹配 → 静默返回 None**

## 根因

`_pre_llm_call()` 在 `__init__.py` 第 1588-1589 行：

```python
result = _match_b_layer(user_message)
if not result:
    stats["misses"] += 1
    return None        # ← 无 logger.info() 调用
```

对比其他路径：
- A 层命中 → `logger.info("[ssr] A 层命中: %s", ...)`  ✓
- B 层命中 → `logger.info("[ssr] B 层命中: %s", ...)`  ✓
- A/B 层置信不足 → `logger.info("[ssr] A/B 层置信度不足...")`  ✓
- **A 层 0 匹配 + B 层 0 匹配 → 零输出**  ✗

## 触发条件

1. `a_rules.json` 为空（`{}`，2 字节）→ A 层规则 0 条，100% 回退 B 层
2. B 层 `_match_b_main()` 超时或返回不匹配 → `return None`
3. 用户消息是元对话（"SSR 加载了吗" / "测试 SSR"）→ B 层可能也匹配不到

## 诊断

```bash
# ① 检查 a_rules.json 是否为空（2 字节 {} = 被清空）
ls -la ~/.hermes/plugins/ssr/a_rules.json
python3 -c "import json; print(len(json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json'))))"

# ② 检查 B 层连通性（发一条明确触发消息后查日志）
grep 'B 层' ~/.hermes/logs/agent.log | tail -3

# ③ 确认是否假性沉默
# a_rules.json 空 + B 层无命中 → 假性沉默（SSR 在工作但没产出）
# a_rules.json 非空 + 当前 session 零日志 → 真故障（hook 未被调用）
```

## 与 "hook 未触发" 的区别

| 现象 | 假性沉默（本次） | hook 未触发 |
|------|:--:|:--:|
| session stats 计数器递增 | **无法判断**（无日志，计数器在内存中） | 否 |
| a_rules.json | 空（2 bytes） | 可能正常 |
| 发触发消息（如 "设计登录页面"）后 | 可能开始命中 | 仍然零日志 |
| 根因 | 代码设计缺陷（miss 路径无日志） | Hermes hook 调度问题 |

## 修复（v0.6.2 已实施）

1. **T2 (✅):** 补 `logger.info("[ssr] 无匹配（A层 %d 条 + B层 %s, 本轮第 %d 次）", len(_A_RULES), _b_provider(), stats["calls"])` 到 miss 路径
2. **T3 (✅):** `_save_a_rules` 空覆盖前自动备份到 `.json.bak` + `_load_a_rules` 损坏时备份到 `.json.corrupted`
3. **T1 (✅):** `register()` 加 3 行诊断日志（加载→清理→净化后规则数）定位清空步骤
4. **T4 (⏳):** 重启验证 + GREEN baseline 待执行

## 修复方向（已实现）

## 本会话时间线

```
16:49:25 - embedding 增量同步完成（370 skill, bge-large-chinese）
16:50:26 - SSR 注册完成（A层: 0+0, emb: 370）
16:50:38 - 当前会话开始，用户消息 "测试SSR"
16:50:38 - skill_autoload pre_llm_call 触发（可见日志）
16:50:57 - 首次 API 调用（19 秒延迟 — B 层可能在超时）
         - SSR miss 路径，无日志输出 ← 假性沉默
```
