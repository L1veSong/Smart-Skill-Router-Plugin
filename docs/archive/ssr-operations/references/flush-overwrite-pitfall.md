# SSR a_rules.json 直接编辑被覆盖（2026-07-25）

## 症状

用 `execute_code` / `write_file` 直接修改 `a_rules.json` 添加规则。过一会儿规则消失，文件回退到旧状态。本次会话 Anthropic 15 条规则从 242→219 回退两次。

## 根因

SSR 在内存中维护 `_A_RULES` dict。`_flush_a_rules()` 写盘时写入的是**内存中的旧状态**。

关键代码路径（`__init__.py`）：

```
第 806 行: _mark_a_dirty()
第 808 行: if _A_HIT_COUNT >= 5:
第 809 行:     _flush_a_rules()
第 890 行: def _flush_a_rules():
第 894 行:     _save_a_rules(_A_RULES)  # 写的是内存旧数据
```

触发链：
1. SSR 启动 → `_A_RULES = _load_a_rules()` → 内存加载 219 条
2. 你编辑 `a_rules.json` → 磁盘变成 242 条
3. 对话中 SSR 每匹配 5 次 → `_flush_a_rules()` → 内存 219 条覆盖磁盘

## 修复

### 临时（每次改规则后）

```bash
# 改完验证规则数
python3 -c "import json; print(len(json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json'))))"
# 重启 Hermes 让 SSR 重新加载
```

### 根治方向

- 在 `_save_a_rules()` 保存前合并磁盘上新增的手动规则
- 或提供 `!ssr reload` 命令从磁盘重新加载 `_A_RULES`

## 验证命令

```bash
# 检查是否有未落盘的手动规则
# 对比磁盘文件规则数 vs SSR 日志中加载的规则数
grep "加载.*规则" ~/.hermes/logs/agent.log | tail -3
python3 -c "import json; print(len(json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json'))))"
```

## 本次会话追踪

| 时间 | 操作 | 规则数 | 结果 |
|------|------|:--:|------|
| 初始 | — | 219 | — |
| +8 游戏规则 | execute_code | 227 | ✅ |
| +15 Anthropic | execute_code | 242 | ❌ 被回退到 219 |
| +4 superpowers | execute_code | 223 | ✅ |
| 补回 Anthropic | execute_code | 238 | ⚠️ 需验证未再回退 |
