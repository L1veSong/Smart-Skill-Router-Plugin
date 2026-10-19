# a_rules.json 空覆盖诊断与恢复

> 记录于 2026-06-14 SSR v0.6.2 根因追踪

## 症状

重启 Hermes 后 a_rules.json 为 2 字节 `{}`，所有 A 层关键词规则永久丢失。Agent 日志显示：

```
[ssr] 加载 A 层规则: 0 条
[ssr] 清理后 A 层规则: 0 条
```

## 诊断三步

```bash
# 1. 检查当前状态
python3 -c "import json; d=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(f'规则数: {len(d)}')"

# 2. 查找可用的备份
ls -la ~/.hermes/plugins/ssr/a_rules.json.bak*

# 3. 查看 SSR 注册日志（确认何时归零）
grep '加载 A 层规则\|清理后 A 层' ~/.hermes/logs/agent.log | tail -10
```

## 恢复步骤

### 从自动备份恢复（v0.6.2+）

```bash
# v0.6.2 保存空覆盖前自动创建 a_rules.json.bak
cp ~/.hermes/plugins/ssr/a_rules.json.bak ~/.hermes/plugins/ssr/a_rules.json
# 重启 Hermes 生效
```

### 从手动备份恢复

```bash
# 列出所有备份
ls -lt ~/.hermes/plugins/ssr/a_rules.json.bak.* | head -5

# 选最近的非空备份（文件大小>10 字节）
# 例：a_rules.json.bak.20260614_1615 含 100 条规则
cp ~/.hermes/plugins/ssr/a_rules.json.bak.20260614_1615 \
   ~/.hermes/plugins/ssr/a_rules.json
```

### 恢复后验证

```bash
# 确认规则数
python3 -c "import json; d=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(len(d))"

# 重启后检查
grep '加载 A 层规则\|清理后 A 层' ~/.hermes/logs/agent.log | tail -3
```

## 根因机制

v0.6.1 `_save_a_rules()` 无空覆盖保护。任何 `_save_a_rules({})` 调用 → 静默覆写 15KB 文件为 2 字节 `{}`。

**已确认时间线（2026-06-14）：**

| 时间 | 事件 |
|------|------|
| 16:15 | 手动备份创建（100 条规则，15KB） |
| 16:24 | Session 162423 启动，SSR 正常加载 100 条 |
| 16:50:26 | a_rules.json 被覆写为 `{}`（mtime 与 review agent 注册时间重合） |
| 16:54 | 主 session 仍在命中 A 层（内存副本完好） |
| 17:10 | v0.6.2 T1-T3 部署（保护机制上线） |
| 17:26 | 新 session → A 层 0 条 |

**触发路径（推断）：** 主 session 运行期间，`_flush_a_rules()` 在 `_A_RULES` 全局被异常重置为空时写盘。

## v0.6.2 保护

- `_save_a_rules()`: 空覆盖前自动备份到 `a_rules.json.bak`
- `_load_a_rules()`: JSON 损坏时备份到 `a_rules.json.corrupted`
- `register()`: 三步诊断日志（加载/清理后/净化后）
- `_pre_llm_call`: miss 路径不再沉默
