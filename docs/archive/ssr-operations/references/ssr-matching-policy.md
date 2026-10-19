# SSR 匹配策略：不限于 formal skill

SSR 的 `a_rules.json` 只做正则匹配 → 目标名称映射，不校验目标是否是 Hermes skill。用户明确允许匹配 CLI 工具、Python 脚本、桌面 App 等非 skill 目标。

## 目标类型

| 目标类型 | 示例 | SSR 推荐时行为 |
|---------|------|---------------|
| Hermes skill | `libtv-cli`, `funai-skill` | Agent 可 `skill_view()` 加载 |
| CLI 工具 | `auto-editor`, `reasonix` | Agent 直接调 terminal |
| Python 脚本 | `life-services.py` | Agent 调 `python3 ~/.hermes/scripts/...` |
| 桌面 App | `shotcut`, `losslesscut` | Agent 提示用户打开 |

## 立场

不主动过滤。只要用户觉得某个工具值得被 SSR 发现，就加规则。SSR 是路由器，不是裁判。

## 来源

2026-07-25 会话：用户纠正「脚本不是 skill，不该入 SSR」→「那其实 ssr 匹配非 skill 也没什么不好的，之前没入的入一下吧」→ 油价/节假日/快递/汇率重新入库，auto-editor/whisperx/losslesscut/shotcut 一并入库。
