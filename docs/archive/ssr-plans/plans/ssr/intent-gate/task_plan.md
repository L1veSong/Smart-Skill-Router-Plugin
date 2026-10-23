# SSR LLM 意图门控 v1.7.0 — 实施计划

> 创建: 2026-06-21 | 前置: v1.6.4 | 备份: `__init__.py.bak.06211955`

## 背景

v1.6.4 解锁 embedding 门控后，信号 4/10→8/10，噪音 5/5→3/5。
"好的我明白了""你觉得呢"触发 embedding 推 12 个无关 skill。

LLM 二分类在 embedding 前做门控。零硬编码——后端由 config 驱动，自动适配任何模型。

## 架构变更

```
改前: user_message → _pre_llm_call → A层(embedding) → 推荐
改后: user_message → _pre_llm_call → _intent_gate() → YES → A层 → 推荐
                                               └─ NO → return None
```

## 配置设计

零硬编码、零自动检测、零自动写入。纯读 config，没配就不跑。

```yaml
ssr:
  intent_gate:
    enabled: true
    providers:                   # 按顺序尝试，第一个成功的返回
      - provider: ollama
        model: qwen2.5:3b        # 用户自己填，填什么用什么
        timeout: 5
      - provider: main           # 复用 Hermes 主模型
        timeout: 10
    on_error: pass               # 全链路失败 → 放行（不阻塞用户）
```

**provider 类型（可扩展）：**

| provider | model | base_url | api_key |
|----------|-------|----------|---------|
| `ollama` | 必填 | 固定 `http://localhost:11434` | 无需 |
| `main` | 可选（空=读取主模型 default） | 读 config.yaml model.base_url | 读 config.yaml model.api_key |
| `openai` | 必填 | 必填 | 必填 |

**providers 为空 → 门控静默关闭，相当于没装。**
Dashboard 后续提供配置 UI，用户自己填模型名、开关。

## 代码改动

### 改动 1: 新增 `_intent_gate()` + 辅助函数

插入位置: `_match_b_main` 之前（~line 1264）。共 3 个函数。

```python
# ── LLM 意图门控 v1.7.0 ──
_INTENT_GATE_CACHE: Dict[str, bool] = {}

def _call_llm_intent(provider: str, model: str, base_url: str,
                     api_key: str, msg: str, timeout: int) -> Optional[bool]:
    """调用 LLM 做意图二分类。返回 True/False/None(None=调用失败)。"""
    try:
        import httpx
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        r = httpx.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "只回答 YES 或 NO。不要解释。"},
                    {"role": "user", "content": f"用户消息:\"{msg}\"\n这条消息需要加载技能(skill)吗？只回答 YES 或 NO。"}
                ],
                "max_tokens": 3,
                "temperature": 0,
            },
            timeout=timeout,
        )
        if r.status_code == 200:
            answer = r.json()["choices"][0]["message"]["content"].strip().upper()
            return "YES" in answer
        return None
    except Exception:
        return None


def _intent_gate(user_message: str) -> bool:
    """LLM 二分类门控。
    
    按 ssr.intent_gate.providers 顺序尝试，第一个成功的返回。
    providers 为空 → 直接放行（门控不生效）。
    全失败 → on_error 策略（默认 pass=放行）。
    """
    if not user_message or len(user_message) < 3:
        return False
    
    msg = user_message.strip()
    
    # 极短噪音直截
    if len(msg) < 4:
        return False
    
    # 缓存命中
    cache_key = msg[:60]
    if cache_key in _INTENT_GATE_CACHE:
        return _INTENT_GATE_CACHE[cache_key]
    
    # 读配置
    cfg = _load_intent_gate_config()
    if not cfg.get("enabled", True):
        return True
    
    providers = cfg.get("providers", [])
    on_error = cfg.get("on_error", "pass")
    
    # 没配 provider → 门控关闭，放行
    if not providers:
        return True
    
    for p in providers:
        provider = p.get("provider", "")
        model = p.get("model", "")
        timeout = p.get("timeout", 10)
        
        if not model:
            # main 类型允许不填 model，自动读主模型配置
            if provider == "main":
                main_cfg = _load_main_model_config()
                model = main_cfg.get("default", "")
            if not model:
                continue
        
        # 获取端点 + 凭据
        if provider == "ollama":
            base_url = "http://localhost:11434"
            api_key = ""
        elif provider == "main":
            main_cfg = _load_main_model_config()
            base_url = main_cfg.get("base_url", "")
            api_key = main_cfg.get("api_key", "")
        elif provider == "openai":
            base_url = p.get("base_url", "")
            api_key = p.get("api_key", "")
        else:
            continue
        
        if not base_url or not model:
            continue
        
        result = _call_llm_intent(provider, model, base_url, api_key, msg, timeout)
        if result is not None:
            _INTENT_GATE_CACHE[cache_key] = result
            return result
    
    # 全链路失败
    if on_error == "block":
        _INTENT_GATE_CACHE[cache_key] = False
        return False
    else:
        # pass: 放行
        _INTENT_GATE_CACHE[cache_key] = True
        return True


def _load_intent_gate_config() -> dict:
    """读取 ssr.intent_gate 配置。providers 为空 → 门控不生效。"""
    try:
        from pathlib import Path
        import yaml
        with open(Path.home() / ".hermes" / "config.yaml") as f:
            cfg = yaml.safe_load(f)
        return cfg.get("ssr", {}).get("intent_gate", {
            "enabled": False,
            "providers": [],
            "on_error": "pass",
        })
    except Exception:
        return {"enabled": False, "providers": [], "on_error": "pass"}


def _load_main_model_config() -> dict:
    """读取 Hermes 主模型配置。"""
    try:
        from pathlib import Path
        import yaml, os
        with open(Path.home() / ".hermes" / "config.yaml") as f:
            cfg = yaml.safe_load(f)
        mc = cfg.get("model", {})
        api_key = mc.get("api_key", "")
        if not api_key:
            for sub_key in ("curator", "triage_specifier"):
                sub = mc.get(sub_key, {})
                if isinstance(sub, dict) and sub.get("api_key"):
                    api_key = sub["api_key"]
                    break
        return {
            "default": mc.get("default", ""),
            "base_url": mc.get("base_url", ""),
            "api_key": api_key,
        }
    except Exception:
        return {}
```

### 改动 2: `_pre_llm_call` 插入门控调用

位置: line 1488 之后（`len < 3` 检查之后，`try:` 之前）。

```python
    if not user_message or len(user_message) < 3:
        return None

    # ── v1.7.0 LLM 意图门控 ──
    if not _intent_gate(user_message):
        logger.debug("[ssr] 意图门控: NO → 静默")
        return None

    try:
        # ... 现有逻辑不变
```

### 改动 3: 版本号更新

| 位置 | 旧 | 新 |
|------|----|----|
| `__init__.py` docstring | `v0.6.3` | `v0.7.0` |
| `plugin.yaml` version | `0.6.3` | `0.7.0` |
| SKILL.md version | `1.6.4` | `1.7.0` |

### 改动 4: 旧 B 层保留不删

`_match_b_main` / `_match_b_openai` / `_match_b_ollama` 不动。

## 不影响的部分

- A 层关键词 + embedding 匹配：不变
- B→A 自学习：不变
- 冷却制、会话统计、热更新：不变
- 现有 `ssr.display`、`ssr.embedding.*`：不变
- `similarity_floor`、`confidence_threshold`：不变

## 测试计划

### 1. 编译验证
```bash
python3 -c "compile(open('$HOME/.hermes/plugins/ssr/__init__.py').read(), '__init__.py', 'exec')"
```

### 2. 15 条回归测试（10 信号 + 5 噪音）
同本次会话流程。逐条发，逐条 grep。

预期：
- 信号 10/10：门控 YES → 走现有流程
- 噪音 5/5：门控 NO → 静默
- 零硬编码确认：`grep 'qwen2.5\|gpt-4\|claude' __init__.py` → 无结果
- 零自动检测确认：`grep 'api/tags\|auto_detect' __init__.py` → 无结果

### 3. 门控日志验证
```bash
grep '意图门控' ~/.hermes/logs/agent.log | tail -15
```

### 4. 降级路径验证
```bash
# 停掉 Ollama，门控应降级到 main 或放行，不崩溃
```

### 5. 未配置验证
```bash
# 确保 config.yaml 无 intent_gate 配置时，门控不生效（放行）
grep 'intent_gate' ~/.hermes/config.yaml
# 应无结果（或 enabled: false）
```

## 回滚

```bash
cp ~/.hermes/plugins/ssr/__init__.py.bak.06211955 ~/.hermes/plugins/ssr/__init__.py
# 重启 Hermes
```

## 风险

| 风险 | 概率 | 缓解 |
|------|:--:|------|
| 用户未配置 provider | 确定 | 门控不生效，放行=现状 |
| API key 失效 | 低 | 降级放行（on_error: pass） |
| 门控误判 YES → 噪音漏过 | 中 | embedding floor 二次过滤 |
| 门控误判 NO → 信号丢失 | 极低 | on_error=pass 兜底 |
| 延迟增加 | 确定 | 缓存 60s + 可关闭门控 |
