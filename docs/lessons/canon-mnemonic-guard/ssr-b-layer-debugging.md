# SSR B 层调试全记录

> 创建于 2026-07-05 · 1 次会话 7 轮修复 · 来源：`帮我定位数据库连接池泄漏` 验证场景

## 核心教训

**修 bug 前必须先确认 bug 在执行路径上。** 修了 7 轮 B 层解析器（JSON/key/timeout/signature），最后发现 B 层从未被真正验证过是否可达——问题在 A 层 embedding 质量、配置路径不匹配、模型能力天花板。

## 发现的阻塞点（按诊断顺序）

### 1. `_is_ollama` 检测逻辑陷阱

```python
_is_ollama = (provider == "ollama") or (not api_key and "localhost" in base_url)
```

**问题**：`base_url` 为空 → 回退 `http://localhost:11434` → 即使 `provider: main` 也走 Ollama 分支。

**触发条件**：`b_layer.provider: main` + `b_layer.base_url: ""` + `b_layer.api_key: ""`

**修复**：必须显式设置 `base_url` 为非 localhost 值：
```bash
hermes config set ssr.b_layer.base_url https://api.xiaomimimo.com/v1
```

### 2. `_similarity_floor()` 无视用户配置

**症状**：`similarity_floor: 0.35` 写入 config.yaml，但日志显示 `自动 floor (无极): Qwen3-Embedding-8B → 0.580`

**根因**：`_similarity_floor()` 先检查 `cfg.get("similarity_floor")`，但如果 `_load_ssr_config()` 返回的缓存对象不包含这个 key（hermes config set 写的路径和 `hermes_cli.config.load_config()` 读的不是同一个），则落入自动校准路径。模型匹配到 `Qwen3-Embedding-8B` → 命中 `model_scores.json` 的 `calibrated_floor: 0.58` → 返回 0.58。

**诊断**：`_load_ssr_config()` 走 `hermes_cli.config.load_config()`，与 `hermes config set` 写的关键路径可能不同步。日志中 `_CONFIG_CACHE` 可能持有旧值。

**修复**：清理 `_CONFIG_CACHE` 后重启，或直接在配置文件中写入 floor 而非通过 CLI。

### 3. `_post_llm_call` 签名不匹配框架调用

**症状**：`Hook 'post_llm_call' callback raised: _post_llm_call() missing 1 required positional argument: 'text'`

**根因**：函数签名 `def _post_llm_call(text: str, session_id: str = "", **kwargs) -> str` —— Hermes 框架调用 post_llm_call hook 时可能不传 `text` 参数（或传 `None`），导致 `text: str` 必填参数缺失。

**修复**：`def _post_llm_call(text: str = "", session_id: str = "", **kwargs) -> str`

### 4. qwen3.5:4b 模型能力天花板

**症状**：B 层每次都判「语境无关 → 静默」，即使 A 层有 30 个候选。

**根因**：4B 参数太小，无法可靠执行 JSON 格式的二分类意图判断。prompt 灌 200 个 skill name + description → 超过 4B 模型有效上下文窗口 → 随机输出「空数组」或「need_skill: false」。

**验证**：沙箱实测 `_call_llm_screen_direct` → 返回 `[]`（判断无匹配 skill）。

**修复**：关 B 层（`ssr.llm_screen: false`），或升级到 7B+ 模型（`qwen2.5:7b` / 云 API `deepseek-v4-pro`）。

### 5. qwen3.5:4b 输出格式问题

- **`format: "json"` 参数 Bug**：Ollama 原生 `/api/chat` + `"format": "json"` → 模型输出 JSON 后追加上百个空行 → `Expecting value: line 1 column 34`
- **单引号 JSON**：`{need_skill: false, 'relevant': []}` → `json.loads()` 报 `'expected after dictionary key`
- **unquoted key**：`{need_skill: false}` → 需要 sanitize 加引号

**已修复**：
1. 去掉 `"format": "json"` 参数
2. 栈匹配 JSON 提取（`start = content.find('{')` + depth tracking）
3. unquoted key sanitize（`re.sub(r'([{,]\s*)([a-zA-Z_]\w*)(\s*:)', r'\1"\2"\3', raw)`）
4. 三层解析链：`json.loads` → `ast.literal_eval` → 降级放行

### 6. Embedding 质量瓶颈（非代码问题）

**数据**：`帮我定位数据库连接池泄漏` 对 Qwen3-Embedding-8B 的 top-5 是 `investigate`、`canary`、`canon-mnemonic-guard-dashboard`、`benchmark`、`vercel-optimize`。

**结论**：embedding 对中文技术查询的语义理解不足——这不是 floor 高低能修的。

### 7. `_display_enabled()` 初始为 False

**症状**：`_post_llm_call` 在 `_display_enabled()` 返回 False 时跳过注入，推荐结果存 `_POST_LLM_CACHE` 但从不展示。

**修复**：`hermes config set ssr.display true`

## 调试方法论

### 正确的诊断顺序（本会话反例）

1. **先验证数据流** → `execute_code` 导入 SSR 模块，直接测试 `_intent_gate` → `_match_a_layer` → `_llm_screen` → `_post_llm_call` 每个环节
2. **先查配置读值** → `_load_ssr_config()` 实际返回什么 vs config.yaml 写的是什么
3. **先隔离测试模型** → curl Ollama 端点验证模型可用、输出格式、延迟
4. **最后才动代码**

### 错误的反模式（本会话 7 轮）

1. 看到 `HTTP 401` → 改 b_layer 配置读取路径 ✓（实际需要，但不够）
2. 看到 `timed out` → 改 timeout 值 ✓
3. 看到 `Expecting value` → 改 JSON 解析 ✓
4. 看到 `'expected after dictionary key` → 加 ast.literal_eval ✓
5. 看到 `LLM 筛查: 语境无关 → 静默` → 认为 B 层正常工作了（❌ 实际是 4B 模型太弱判全否）
6. 修 `_post_llm_call` 签名 ✓
7. 开 `ssr.display` ✓

**每一步修的代码都是对的——但前 5 步都在修同一个端点的同一个函数，却从未停下来验证调用链是否真的走到了这个函数。**

## 最小可工作配置

### 本地 Ollama（需要 7B+ 模型）

```yaml
ssr:
  b_layer:
    provider: ollama
    model: qwen2.5:7b  # 最小 7B，4B 不可用
    base_url: http://localhost:11434
    api_key: ''
    timeout: 60
  llm_screen: true
  display: true
  confidence_threshold: 0.50
```

### 云 API（DeepSeek / MoA）

```yaml
ssr:
  b_layer:
    provider: main
    model: deepseek-v4-pro
    base_url: https://api.xiaomimimo.com/v1
    api_key: sk-xxx  # 必须显式填写，SSR 不继承全局 key
    timeout: 30
  llm_screen: true
  display: true
  confidence_threshold: 0.50
```

### 仅 A 层（零 API 费，零延迟，有噪音）

```yaml
ssr:
  llm_screen: false
  display: true
  confidence_threshold: 0.35
  similarity_floor: 0.35
```

## 代码关键位置（修复后）

| 函数 | 行号 | 作用 | 状态 |
|------|------|------|------|
| `_intent_gate` | 1776 | LLM 二分类门控 | ✅ |
| `_match_a_layer` | 717 | A层关键词+embedding | ⚠️ embedding 中文质量差 |
| `_llm_screen` | 1310 | 候选筛查（有候选时） | ✅ 代码已修，受限于模型 |
| `_call_llm_screen_direct` | 1433 | 独立匹配（无候选时） | ✅ 代码已修，受限于模型 |
| `_post_llm_call` | 1035 | 推荐注入到回复 | ✅ 签名已修 |
| `_similarity_floor` | 738 | 相似度地板 | ⚠️ 配置可能被校准覆盖 |
| `_display_enabled` | 1038 | 是否展示推荐 | ✅ |
