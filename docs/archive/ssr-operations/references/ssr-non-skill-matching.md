# SSR 非 Skill 匹配

**决策日期：2026-07-25**

SSR 不限于匹配 skill。它可以匹配任何目标——CLI 工具、Python 脚本、桌面 App、外部平台。

## 设计理由

用户指出："之前入库的也有工具。"验证确认 `animejs` 已在 SSR 中。SSR 本身不做目标校验——只是字符串模式匹配。限制\"只能匹配 skill\"是人为约束，没有技术依据。

## 当前匹配范围

```
Skill:    libtv-cli, funai-skill, remotion, claude-code 等
CLI:      auto-editor, whisperx, reasonix, inkos
App:      losslesscut, shotcut
脚本:     (不推荐——脚本直接跑就行，不需要SSR指路)
平台:     LibTV画布, 橙星梦工厂
```

## 添加规则时的命名约定

非 skill 目标用描述性后缀，方便区分：
```
"auto-editor"       ← CLI 工具，裸名
"life-services (油价)" ← 脚本，加功能后缀
```

## 与 Skill 匹配共存

SSR 内部不区分目标类型。`libtv-cli`（skill）和 `auto-editor`（CLI）对匹配引擎来说完全相同——只是 rule → target 对。未来如果要区分，应在插件层加 `target_type` 字段，不在规则数据层。
