# 独立导入 SSR plugin 用于 benchmark 测试

> 2026-06-22 实战。benchmark 调用真实 SSR `_match_a_layer` 而非复制逻辑。

## 问题

SSR plugin 的 `register()` 依赖 Hermes 运行时 (`ctx.register_hook`)，无法独立 import。
`_load_ssr_config()` 依赖 `hermes_cli.config.load_config`，独立 Python 返回空配置 → 默认模型 `nomic-embed-text` (未安装) → 404。

## 解决方案：`_init_ssr()` 函数

```python
def _init_ssr():
    plugin_path = HOME / ".hermes" / "plugins" / "ssr" / "__init__.py"
    spec = importlib.util.spec_from_file_location("ssr_plugin", str(plugin_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    # 注入配置 — 绕过 hermes_cli 依赖
    mod._CONFIG_CACHE = ssr_cfg       # 预填充配置缓存
    mod._CONFIG_PATH = str(CONFIG_PATH)
    
    # 手动初始化（跳过 hook 注册）
    mod._SKILL_INDEX, mod._BROKEN_SKILLS = mod._build_skill_index()
    mod._A_RULES = mod._load_a_rules()
    mod._cleanup_a_rules()
    existing = mod._load_embedding_index()
    mod._EMBEDDING_INDEX = existing if existing else {}
    
    return mod
```

## 关键点

1. **`_CONFIG_CACHE` 必须预填充** — `_load_ssr_config()` 先检查缓存，非空直接返回，不再调用 `hermes_cli`。这是绕过运行时依赖的关键。
2. **`_build_skill_index()` 有文件系统回退** — 扫描 `~/.hermes/skills/**/SKILL.md`，不依赖 Hermes API。
3. **`_EMBEDDING_INDEX` 从磁盘加载** — `_load_embedding_index()` 读 `embeddings.json`。
4. **不调用 `register()`** — 跳过 `ctx.register_hook`，手动设置所需全局变量。

## 使用方式

```python
mod = _init_ssr()
if mod:
    result = mod._match_a_layer("部署网站到Vercel")
    # result: [{"name": "deploy-to-vercel", "phase": "BUILD", "_sim": 0.61}, ...]
```
