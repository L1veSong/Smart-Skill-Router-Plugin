# Ollama 本地模型 B 层集成坑位（2026-07-05 实战修复）

## 触发场景

SSR B 层 `llm_screen` / `_call_llm_screen_direct` 使用本地 Ollama 推理模型（qwen3.5:4b 等），通过 `/api/chat` 原生端点做候选 skill 筛查。

---

## 坑位 1：推理模型 content 为空（表象：401 / timed out）

**根因**：Ollama 推理模型走 `/v1/chat/completions`（OpenAI 兼容 shim）时，`think: false` 不被透传，所有 `max_tokens` 进入 `reasoning` 字段，`content` 返回空字符串 → JSON 解析永远失败 → 降级放行。

**修复**：检测本地 Ollama 后改用原生 `/api/chat` + `"think": false`。

检测条件：
```python
_is_ollama = (provider == "ollama") or (not api_key and "localhost" in base_url)
```

请求体：
```python
{
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "think": False,
    "stream": False,
    "options": {"num_predict": 300},
}
```

响应解析：`resp.json().get("message", {}).get("content", "")`（非 OpenAI 路径的 `choices[0]`）

---

## 坑位 2：配置不一致导致修复不生效

**表象**：代码已改用原生 `/api/chat`，日志仍 `HTTP 401` 或 `timed out`。

**根因**：`config.yaml` 中 `b_layer.provider` 仍为 `main`，且 `api_key` 非空 → `_is_ollama` 判定失败（两个条件全不满足）→ 走 OpenAI 分支 → 代码修复白改。

**修复命令**：
```bash
hermes config set ssr.b_layer.provider ollama
hermes config set ssr.b_layer.api_key ""
hermes config set ssr.b_layer.base_url http://localhost:11434
```

**验证**：
```bash
grep -A 10 'b_layer:' ~/.hermes/config.yaml
# 预期：provider: ollama, api_key: '', base_url: http://localhost:11434
```

---

## 坑位 3：推理模型冷启动超时

**表象**：重启后第一次调用 `timed out`，后续正常。

**根因**：qwen3.5:4b 冷加载耗时约 23s（简单 prompt），原有硬编码 `timeout=15` / `timeout=20` 根本不够。`_b_timeout()` 读的是 `config.yaml` 的 `timeout: 30`，但对冷启动仍然偏紧。

**修复**：
```bash
hermes config set ssr.b_layer.timeout 60
```

代码已通过 `_b_timeout()` 动态读取配置，无需改源码。

---

## 坑位 4：`format: "json"` 导致空白行追加

**表象**：加 `"format": "json"` 后报 `Expecting value: line 1 column 34`。

**根因**：qwen3.5:4b 在 `format: "json"` 模式下，输出合法 JSON 后追加上百个空行。`re.search(r'\{[^}]+\}', content)` 只匹配到第一个 `}`，`content.strip()` 后的空白尾缀不影响 `json.loads`？不——实际是 Ollama 的 `format: json` 实现有 Bug，后续空白行导致 content 截断/偏移。

**修复**：**去掉两处 `"format": "json"`**，不做 format 强制。靠 prompt 指令 + `ast.literal_eval` 兜底。

---

## 坑位 5：小模型输出单引号 JSON（Python dict 风格）

**表象**：`Expecting property name enclosed in double quotes: line 3 column 2`。

**根因**：qwen3.5:4b 倾向输出 `{'need_skill': False, 'relevant': []}` 而非标准 JSON。`json.loads()` 对单引号报错。

**修复**：`json.loads` 失败时 fallback 到 `ast.literal_eval`。

```python
raw = m.group().strip()
try:
    parsed = json.loads(raw)
except (json.JSONDecodeError, ValueError):
    import ast
    parsed = ast.literal_eval(raw)
```

需在两处解析点同时修改：`_llm_screen`（筛查分支）和 `_call_llm_screen_direct`（独立匹配分支）。

---

## 坑位 6：pyc 字节码缓存导致代码不生效

**表象**：代码修改正确、语法通过、重启 Hermes，行为却不变。

**根因**：Python 编译的 `.pyc` 缓存文件可能时间戳比新源码更新，插件加载时优先读缓存。

**修复**：
```bash
find ~/.hermes/plugins/ssr -name '*.pyc' -delete
```

---

## 诊断命令速查

```bash
# 查当前日志（看是否有 401、timed out、Expecting 系列错误）
grep '\[ssr\]' ~/.hermes/logs/agent.log | tail -10

# 查 B 层配置（确认 provider/ api_key/ base_url/ timeout）
grep -A 10 'b_layer:' ~/.hermes/config.yaml

# 查代码中涉及 Ollama B 层的函数位置
grep -n 'def _b_timeout\|def _llm_screen\|def _call_llm_screen_direct' ~/.hermes/plugins/ssr/__init__.py

# 清字节码缓存（改代码后必须执行）
find ~/.hermes/plugins/ssr -name '*.pyc' -delete

# 语法检查（改代码后必须执行）
python3 -c "compile(open('$HOME/.hermes/plugins/ssr/__init__.py').read(), 'x', 'exec'); print('语法 OK')"
```

---

## 修复后验证三场景

1. **日志检查**：`grep '[ssr]' ~/.hermes/logs/agent.log | tail -5` — 无 401 / timed out / Expecting 系列
2. **精准推荐**：说"帮我定位数据库连接池泄漏" → 推荐精准、≤6 条、无 PDF/nature/social-media 噪音
3. **零命中过滤**：说"帮我想想" → A 层低分 + B 层再砍
