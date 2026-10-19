# B 层 LLM Gate 成功方案 (2026-06-21)

## 问题

DeepSeek v4-pro 和 qwen3.5:9b 都有 reasoning/thinking 开销，max_tokens 太小时 content 永远为空。

## 解决方案

`max_tokens=200` — 给 reasoning ~100 tokens 空间，content 正常输出。

## 验证 (6/6 全对)

| 查询 | 期望 | 结果 |
|------|:--:|:--:|
| 今天天气不错 | NO | NO ✅ |
| 帮我设计暗色仪表盘 | YES | YES ✅ |
| 分析茅台股票均线 | YES | YES ✅ |
| 谢谢你的帮助 | NO | NO ✅ |
| 好的我明白了 | NO | NO ✅ |
| 帮我写论文文献综述 | YES | YES ✅ |

## 成本

- 每次 ~75 tokens total
- ~¥0.0002/条
- ~¥0.21/千次对话
- 延迟 ~2s

## Prompt

```python
{
    "model": "deepseek-v4-pro",
    "messages": [
        {"role":"system","content":"先判断用户消息是否需要工具。不需要→只回答NO。需要→回答YES并列出最多3个最匹配的技能名。"},
        {"role":"user","content":f"「{user_message}」"}
    ],
    "temperature": 0,
    "max_tokens": 200
}
```
