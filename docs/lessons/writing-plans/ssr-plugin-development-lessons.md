# SSR Plugin Development — Lessons Learned

> 来源：SSR v0.1.0 完整开发过程（2026-06-04 → 2026-06-05）
> 覆盖：Hermes 插件开发中遇到的 5 个坑点及解决方案

## 坑点 1：多会话并行导致持久化文件覆盖

**症状：** a_rules.json 反复回退到旧版。每次修改后不久就被覆盖。

**根因：** 插件在 `_match_a_layer` 中每次命中都调 `_save_a_rules` 全量写盘。多个 Hermes 会话并行运行时，旧会话的内存副本会覆盖刚修好的文件。

**修复：延迟写盘（lazy-write）模式。**
- 用 `_mark_a_dirty()` 标记脏数据，不立即写盘
- 累计 N 次命中后调 `_flush_a_rules()` 统一落盘
- 启动时 `_load_a_rules()` 加载一次，之后只读不写

```python
_A_DIRTY = False
_A_HIT_COUNT = 0

def _mark_a_dirty():
    global _A_DIRTY
    _A_DIRTY = True

def _flush_a_rules():
    global _A_DIRTY, _A_HIT_COUNT
    if _A_DIRTY:
        _save_a_rules(_A_RULES)
        _A_DIRTY = False
        _A_HIT_COUNT = 0
```

**适用场景：** 任何有持久化状态的 Hermes 插件（规则文件、缓存、配置快照），如果多会话可能并行写入。

## 坑点 2：`hermes config set` 截断长值

**症状：** `hermes config set ssr.b_layer.api_key sk-7c66...5711` 存储的是截断的 13 字符版本，而非完整 35 字符 key。DeepSeek 返回 401。

**根因：** `hermes config set` 对包含省略号格式的值可能做内部处理，导致实际 key 被截断。

**修复：** 长值用 `sed` 或 Python 直接写 config.yaml，不用 `hermes config set`。

```bash
# ❌ 可能截断
hermes config set ssr.b_layer.api_key sk-7c6...5711

# ✅ 直接写文件
sed -i '' 's|api_key: .*|api_key: sk-7c6...5711|' ~/.hermes/config.yaml
```

**验证：** 写完后检查长度：
```python
import yaml
cfg = yaml.safe_load(open('~/.hermes/config.yaml'))
assert len(cfg['ssr']['b_layer']['api_key']) >= 30
```

## 坑点 3：插件中 `hermes_cli` 导入不可靠

**症状：** `from hermes_cli.config import load_config` 在独立 Python 环境报 `ModuleNotFoundError`，在插件上下文可能静默失败。

**修复：** 用 `yaml.safe_load` 直接读 config.yaml 文件作为主路径，`hermes_cli` 作为降级路径。

```python
# 路径 1：直接读文件（可靠）
config_path = Path.home() / ".hermes" / "config.yaml"
with open(config_path) as f:
    cfg = yaml.safe_load(f)

# 路径 2：hermes_cli（降级）
try:
    from hermes_cli.config import load_config
    cfg = load_config()
except Exception:
    pass
```

## 坑点 4：warmup/预热代码不能硬编码端点

**症状：** 冷启动预热代码硬编码 Ollama 的 `/api/generate` 端点，无论 B 层实际后端是什么都往这打。对 `main`（DeepSeek）→ 404/silent fail；日志写"Ollama 调用失败"误导排查。

**修复：** 预热代码检测后端类型，仅对 `ollama` 后端预热。

```python
# ✅ 只在 ollama 后端预热
if _b_provider() == "ollama":
    try:
        httpx.post(f"{base_url}/api/generate", ...)
    except:
        pass
# main/openai 后端超时 → 直接重试一次
```

## 坑点 5：`_cleanup_a_rules` 空 `last_hit` 被误判过期

**症状：** 种子规则的 `last_hit: ""` 被 cleanup 函数当成过期删除，导致新装的插件 A 层规则 0 条。

**根因：** `time.strptime("", "%Y-%m-%d")` 抛 ValueError → 被 `except` 捕获 → 标记为过期。

**修复：** 空 `last_hit` 视为新规则，永不过期。

```python
for pattern, rule in _A_RULES.items():
    last_hit_str = rule.get("last_hit", "")
    if not last_hit_str:  # 从未命中过 → 不过期
        continue
```

## 架构模式：A+B 双路径匹配

SSR 采用的 A 层（关键词正则，0ms）+ B 层（LLM 语义，~2s）双路径架构：

- **A 层**：种子规则 → 命中直接返回，零延迟
- **B 层**：A 层未命中时 LLM 兜底
- **B→A 升级**：B 层连续 3 次匹配成功 → 自动固化为 A 层规则
- **默认后端**：`main`（复用 Hermes 主模型），用户可选 `openai`（自定义 API）或 `ollama`（本地模型）
