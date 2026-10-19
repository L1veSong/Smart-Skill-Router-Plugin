# SSR Display 开关双重门 bug (2026-07-04 实战)

## 症状

`config.yaml` 设 `ssr.display: false` 后，终端仍出现 `[SSR] [D] skill1, skill2 | [B] skill3` 推荐的输出前缀。

## 根因：三重门顺序错误

SSR 有两个 hook 入口都产生输出：

### 门一：`_pre_llm_call` (line 2211-2226, 修复前)

```
候选匹配 → 冷却过滤 → 格式化推荐 → 写入 _POST_LLM_CACHE → 格式化推荐字符串
→ 低置信跳过? → 命中统计 → display 检查 → return {"context": rec}
```

`_format_recommendation(fresh)` 和 `_POST_LLM_CACHE[session_id] = rec` 在 display 检查**之前**执行。`display: false` 时 `return None` 跳过了 `context` 注入，但：

1. **缓存已被写入** → `_post_llm_call` 读缓存 → 注入到回答前
2. **格式化已执行** → 纯 CPU 浪费
3. **embedding API 已调用**（SiliconFlow）→ 消耗 API 额度

### 门二：`_post_llm_call` (line 1035-1047)

```
读 _POST_LLM_CACHE → display 检查 → 注入前缀 或 跳过
```

只有这一个门做了 display 检查——门一已经把所有活都干完了。

## 修复（2026-07-04）

display 检查前移到 `_pre_llm_call` 内 `fresh` 截断之后、B→A 升级检测之前：

```python
# ── display 开关：提前拦截，避免无用格式化和缓存写入 ──
if not _display_enabled():
    stats["hits_b"] += 1
    return None
```

**效果：** `display: false` 时跳过所有后续操作——不格式化、不写缓存、不调 embedding、不调 LLM。

## 验证

```bash
# 确认 config
grep 'display:' ~/.hermes/config.yaml | grep ssr -A 1 | tail -1

# 重启后发一条消息，检查日志
grep '\[ssr\]' ~/.hermes/logs/agent.log | tail -5
# display=false 时应零命中日志（意图门控 + 噪音过滤的日志除外）
```

## 相关文件

- `~/.hermes/plugins/ssr/__init__.py`: `_pre_llm_call()` 函数 display 检查已前移 (line ~2198)
- `~/.hermes/plugins/ssr/__init__.py`: `_post_llm_call()` 函数 display 检查保留（兜底）
- `~/.hermes/config.yaml`: `ssr.display: false`
