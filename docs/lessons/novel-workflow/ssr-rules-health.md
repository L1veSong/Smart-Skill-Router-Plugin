# SSR 规则健康状况（2026-07-26）

## 需要修复的规则

以下规则在 `a_rules.json` 中指向已删除的 bridge skill：

- `inkos` 桥接 skill 已删除（CLI 不需要桥接）→ SSR 仍有 2 条规则指向 `inkos`
- 修复方向：指向 `novel-workflow`（包含 inkos 的完整调用说明）

## 需要添加的规则

- `去AI味|反AI检测` 等去AI味场景 → 应指向 `humanizer-zh`（不是 `inkos` 也不是 `@actalk/inkos`）
- `文笔提升|文字质感` → 应新增规则指向 `chinese-novelist`（当前无此规则）

## 建议执行的修复脚本

修复方式（在 Hermes terminal 中执行）：
```python
# backup first
cp ~/.hermes/plugins/ssr/a_rules.json ~/.hermes/plugins/ssr/a_rules.json.bak.0726-review

# 编辑 a_rules.json:
# 1. 查所有包含 "inkos" 的 key
# 2. 将 skills 从 ["inkos"] 改为 ["novel-workflow"]
# 3. 将 "@actalk/inkos" 改为 "novel-workflow"
# 4. 新增文笔提升规则 → chinese-novelist
```

实际修复待下一轮常规会话执行（review 模式不允许 execute_code/terminal）。
