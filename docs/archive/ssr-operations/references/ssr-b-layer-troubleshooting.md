# SSR 错误链路诊断（2026-07-05 实战）

> 这轮会话的诊断成本极高：修了 7 轮 B 层 JSON 解析器，最后发现管道根本没跑到 B 层。
> 本文件记录完整错误链路，下次修 SSR 前先对照此表。

## 错误链路（按发现顺序）

| 轮次 | 日志/症状 | 定位 | 根因 | 代价 |
|------|----------|------|------|------|
| 1 | `HTTP 401` | `_llm_screen` API 调用 | `b_layer.api_key` 有值 → 代码走 OpenAI 分支 → `/v1/chat/completions` 不认 qwen 推理模型 | 低，配置修复即可 |
| 2 | `timed out` | 同上 | `timeout: 15` 太短 + 模型冷加载 | 低：改为 60 |
| 3 | `Expecting property name` | JSON 解析 | qwen 输出 `{need_skill: false}`（无引号 key） | 中：需要栈匹配+sanitize |
| 4 | `Expecting value` | JSON 解析 | `"format": "json"` 在 qwen3.5:4b 上有 Bug（JSON 后追加空行） | 中：删 format |
| 5 | `语境无关 → 静默`（全部查询） | B 层结果 | **qwen3.5:4b 太弱**，30 个 A 层候选全判「无关」 | 🔴 **白修 6 轮** |
| 6 | Hook 崩溃 | `_post_llm_call` 签名 | `text: str` 无默认值 + 框架传空 | 低：加 `= ""` |
| 7 | B 层从不被调用 | 控制流 | `ssr.display: false` + floor 0.580 | 低：配置修复 |

## 关键教训

**先修管道，再修组件。** 管道 = 意图门控 → A 层 → B 层 → display。组件 = JSON 解析器。

发现错误时：
```bash
# 不要 grep 最后一行就去改代码。先查：
grep '\[ssr\]' ~/.hermes/logs/agent.log | tail -20
```
确认管道实际跑到了哪一节，只修那一节。

## qwen3.5:4b 实测结论

**不支持 SSR B 层。** 对大中文技术短语的 token 直接吃进思维链。实际测试：
- "数据库连接池泄漏" → 44 tokens → content 经常为空  
- 候选列表 > 20 个 → 被推理链压垮

## Ollama 原生 API vs OpenAI 兼容端点

| 端点 | `think:false` 支持 | qwen3.5 适用 |
|------|-------------------|-------------|
| `/api/chat` | ✅ | ✅ |
| `/v1/chat/completions` | ❌（参数被吞） | ❌ |

用 `/api/chat` 且不加 `"format": "json"`（Bug，见轮次 4）。

## 代码修复清单（已完成）

以下修改都在 `~/.hermes/plugins/ssr/__init__.py` 中落地：

1. `_llm_screen()`：读 `ssr.b_layer` 配 → Ollama `/api/chat` + think:false（L1310）
2. `_call_llm_screen_direct()`：同上（L1399）
3. 两处 JSON 解析：栈匹配提取 → sanitize → json.loads → ast.literal_eval 兜底
4. `_post_llm_call()` 签名：`text: str = ""`（L1035）
5. 无 `"format": "json"` 参数

备份：`~/.hermes/plugins/ssr/__init__.py.bak.0705_final`
