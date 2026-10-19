# SSR 插件开发教训（2026-06-05）

## 坑点 44: `hermes config set` 截断含省略号的值

`hermes config set ssr.b_layer.api_key sk-cwv...tews` 写入的 key 被截断。

**修复:** 敏感长字符串（API key/token）禁用 `hermes config set`。用 Python `yaml.safe_load → 改 dict → dump` 或 `sed` 直接编辑 config.yaml。写入后 `yaml.safe_load` 验证。

## 坑点 45: Python 模块级计数变量须声明 `global`

`count += 1` 在函数内没有 `global count` → `UnboundLocalError`。

**修复:** 函数第一行加 `global varname`。字典的 `[]=` 不需要，数字/字符串重新绑定需要。

## 坑点 46: 空 `last_hit` 误判过期

`_cleanup_a_rules()` 中 `time.strptime("", "%Y-%m-%d")` → `ValueError` → 标记为过期删除。种子规则 `last_hit: ""` 全灭。

**修复:** `if not last_hit_str: continue` — 空值视为新规则，不过期。

## 坑点 47: 每次匹配都写盘导致多会话覆盖

`_match_a_layer` 命中一次就 `_save_a_rules()` 全量落盘。多个 Hermes 会话同时跑时，旧会话内存覆盖新规则文件。

**修复:** 延迟写盘（`_mark_dirty()` + 每 5 次命中 `_flush_a_rules()`）。

## 坑点 48: Warmup 路径硬编码 Ollama 端点

`register()` 和 `_match_b_layer` 重试中硬编码 `/api/generate`。main 后端发到 DeepSeek `/api/generate` → 404/timeout。

**修复:** Warmup 加 `if _b_provider() == "ollama"` 守卫。main/openai 超时 → 直接重试，不走 warmup。

## 坑点 49: 多后端 `hermes_cli` 导入失败

`_match_b_main` 用 `from hermes_cli.config import load_config` ——插件上下文中可能不可用。

**修复:** 三路径降级：① `yaml.safe_load(config.yaml)` ② `hermes_cli`（如果可用）③ `b_layer` 配置。

## 坑点 50: model.api_key 截断导致 401

`hermes config set` 写入时 key 被截断为 13 字符合 `...`。DeepSeek 返回 401。

**修复:** 用 `yaml.safe_load` 直接读文件获取完整 key，不靠 `hermes config set`。

## 坑点 51: 公开发布版勿硬编码推荐 skill

a_rules.json 中的 seed 规则写入了我自己的 skill 名（ui-ux-pro-max 等）→ 别人装了没有 → 废了。

**修复:** 发布版 a_rules.json = `{}`。B 层自学习生成规则。README 说明只推荐用户已安装 skill。
