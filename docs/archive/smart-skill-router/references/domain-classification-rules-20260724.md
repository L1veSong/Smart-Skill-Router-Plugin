# SSR 域分类铁则（2026-07-24 实战纠正）

## 核心原则

**域标注反映 skill 的真实平台范围，不是用户的 OS。** 只有真正仅在某平台可用的 skill 才能标为平台专属域。

## 三条铁则

### 铁则 1：跨平台功能禁入 OS 专属域

❌ `find-nearby`（找附近餐厅）标为 `macos` → 错。Windows/Linux 用户也需要找附近。
✅ 移入 `leisure` 通用域。

### 铁则 2：平台专属 skill 的 regex 必须窄到不误伤

❌ `(?i)(提醒|reminder|提醒我)` 匹配 apple-reminders → "提醒我明天开会" 在 Windows 上也触发，瞎匹配。
✅ `(?i)(apple.*提醒|siri.*提醒|icloud.*提醒)` → 只在 Apple 上下文中触发。

### 铁则 3：域标注前先问"这功能在其他 OS 上能用吗？"

能 → 不入 OS 专属域。
不能 → 可以入，但 regex 必须带平台关键词（`mac.*磁盘` 而非 `磁盘清理`）。

## 本次纠正记录

| 规则 | 旧域 | 问题 | 修复 |
|------|------|------|------|
| find-nearby | macos | 跨平台通用 | → leisure |
| "提醒我" → apple-reminders | macos | 通用词误匹配 | regex 收窄 |
| "备忘录" → apple-notes | macos | 通用词误匹配 | regex 收窄 |

## 自查清单（每次新增域或修改规则后）

1. 这个域里的 skill 是否**全部**仅在该平台可用？
2. regex 中的通用词（提醒/找/清理）是否带了平台限定？
3. 是否存在"用户 OS 是 macOS 所以标 macos"的偷懒逻辑？
