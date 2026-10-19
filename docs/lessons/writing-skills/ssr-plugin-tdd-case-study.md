# SSR Plugin TDD 案例研究

SSR（Smart Skill Router Plugin）是第一个完整走 RED→GREEN→REFACTOR 流程的 Hermes Plugin。

## RED 基线

```python
# 无 SSR 时：5 个测试场景全部失败
# 用户消息 → AI 不主动加载任何 skill
# 基线：0/5
```

## GREEN 验证

```python
# A 层 11 条种子规则 + B 层 main 后端
# 5/5 场景全命中
```

## REFACTOR 修复记录（10 轮）

| # | 问题 | 修复 |
|---|------|------|
| 1 | `last_hit: ""` 被误判过期 | `if not last_hit_str: continue` |
| 2 | session 去重永久跳过 | 冷却制（60s） |
| 3 | B 层 Ollama 超时 | timeout 5→30s + 冷启动预热 |
| 4 | model.api_key 截断 13 字符 | 替换为完整 key |
| 5 | 每次 A 层命中全量写盘 → 多会话覆盖 | 延迟写盘（每 5 次命中） |
| 6 | `global _A_HIT_COUNT` 缺声明 | 已声明 |
| 7 | debug 规则不匹配"报 KeyError" | 扩展 `Error|报.*Error` |
| 8 | warmup 路径硬编码 Ollama 端点 | `if _b_provider() == "ollama"` 守卫 |
| 9 | `_match_b_openai` URL 双 `/v1` | 改为 `/chat/completions` |
| 10 | plugin.yaml/dashboard.py/README badge 版本号滞后 | 全文件 grep 同步 |

## 关键教训

### Plugin TDD 不同于 Skill TDD

| Skill | Plugin |
|-------|--------|
| 测试载体：subagent 压力场景 | 测试载体：真实 Hermes 会话 |
| 修改对象：SKILL.md | 修改对象：__init__.py + plugin.yaml |
| 发布工具：skill_manage patch | 发布工具：git + ZIP |
| 版本同步：SKILL.md/README/CHANGELOG | plugin.yaml + __init__.py + dashboard.py + README |

### 延迟写盘模式

多会话并行时，任一会话的 `_save_a_rules` 全量写盘会覆盖其他会话的变更。解决方案：

```python
_A_DIRTY = False
_A_HIT_COUNT = 0

def _mark_a_dirty():
    global _A_DIRTY; _A_DIRTY = True

def _flush_a_rules():
    global _A_DIRTY, _A_HIT_COUNT
    if _A_DIRTY:
        _save_a_rules(_A_RULES)
        _A_DIRTY = False
        _A_HIT_COUNT = 0

# 在 _match_a_layer 中：
_mark_a_dirty()
_A_HIT_COUNT += 1
if _A_HIT_COUNT >= 5:
    _flush_a_rules()
```
