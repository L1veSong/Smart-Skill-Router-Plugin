# SSR 匹配范围：不仅限于 Skill

## 结论

SSR A 层规则不校验目标是否为 Hermes Skill。`a_rules.json` 的 `skills` 字段中，`name` 可以是：

| 类型 | 示例 | 说明 |
|------|------|------|
| Skill 名 | `libtv-cli`, `funai-skill` | 标准用法 |
| CLI 工具 | `auto-editor`, `whisperx` | 用户指定即可 |
| 桌面 App | `shotcut`, `losslesscut` | 同上 |
| 脚本 | `life-services (油价)` | 同上 |

## 起因

用户两次纠正 AI 的错误假设：

1. **2026-07-25** — AI 拒绝将油价/节假日/快递脚本加入 SSR，理由是「不是 skill」。用户反问：「不对啊，我之前入库的也有工具吧？」

2. **同日** — AI 再次拒绝 auto-editor/whisperx/losslesscut/shotcut，用户：「那其实 SSR 匹配非 skill 也没什么不好的。」

## 正确做法

用户说「入库」→ 入。不替用户判断「这个配不配叫 skill」。SSR 的职责是匹配意图→推荐目标，目标是什么类型不重要。
