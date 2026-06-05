"""
智配路由 (SSR) — Smart Skill Router Plugin v0.1.0

自动匹配用户意图到最合适的 skill 并推荐加载。
A 层（关键词精确匹配，零延迟）+ B 层（Ollama 语义匹配，兜底）。
B 层连续命中 3 次自动升级到 A 层。启动时扫描 skills_list 建索引。
完全解耦——匹配的是功能语义，不是具体 skill 名。

配置（config.yaml）:

    ssr:
      hooks:
        pre_llm_call: true
      ollama_model: qwen2.5:3b
      ollama_base_url: http://localhost:11434
      ollama_timeout: 5
      a_rules_max: 100
      a_rules_ttl_days: 30
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

PHASE_LABELS = {"DISCOVER", "PLAN", "BUILD", "VERIFY"}
PHASE_ORDER = ["DISCOVER", "PLAN", "BUILD", "VERIFY"]

# 任务切换检测词
TASK_SWITCH_PATTERNS = re.compile(
    r"另外|换个|还有|也要|顺便|除此之外|另外再|再帮|下一个|接下来",
    re.IGNORECASE,
)

# 升级阈值：B 层连续 N 次同一匹配 → 升级到 A 层
PROMOTE_THRESHOLD = 3

# SSR 插件目录
SSR_DIR = Path(__file__).resolve().parent
A_RULES_PATH = SSR_DIR / "a_rules.json"

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

_CONFIG_CACHE: Optional[dict] = None


def _load_ssr_config() -> dict:
    """读取 config.yaml 中 ssr 配置节，结果缓存。"""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    try:
        from hermes_cli.config import load_config
        raw = load_config()
        cfg: dict = raw.get("ssr", {})
    except Exception:
        cfg = {}
    _CONFIG_CACHE = cfg
    return _CONFIG_CACHE


def _hook_enabled() -> bool:
    cfg = _load_ssr_config()
    hooks = cfg.get("hooks", {})
    return hooks.get("pre_llm_call", True)


def _ssr_mode() -> str:
    """推荐模式：suggest（建议）| enforce（强制）。"""
    return _load_ssr_config().get("mode", "suggest")


def _b_provider() -> str:
    """B 层后端: main | ollama | openai"""
    return _load_ssr_config().get("b_layer", {}).get("provider", "main")


def _b_model() -> str:
    """B 层模型名。main 模式时忽略此值，使用主模型。"""
    return _load_ssr_config().get("b_layer", {}).get("model", _ollama_model())


def _b_base_url() -> str:
    return _load_ssr_config().get("b_layer", {}).get("base_url", _ollama_url())


def _b_api_key() -> str:
    return _load_ssr_config().get("b_layer", {}).get("api_key", "")


def _b_timeout() -> int:
    return _load_ssr_config().get("b_layer", {}).get("timeout", _ollama_timeout())


def _ollama_url() -> str:
    return _load_ssr_config().get("ollama_base_url", "http://localhost:11434")


def _ollama_timeout() -> int:
    return _load_ssr_config().get("ollama_timeout", 30)


def _ollama_model() -> str:
    return _load_ssr_config().get("ollama_model", "qwen2.5:3b")


def _a_rules_max() -> int:
    return _load_ssr_config().get("a_rules_max", 100)


def _a_rules_ttl_days() -> int:
    return _load_ssr_config().get("a_rules_ttl_days", 30)


def _scan_mode() -> str:
    """扫描策略：startup（启动时）| every_turn（每次提问）。"""
    return _load_ssr_config().get("scan_mode", "startup")


# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------

# 技能索引：启动时构建，每次启动重建
_SKILL_INDEX: Dict[str, dict] = {}

# 残骸清单
_BROKEN_SKILLS: List[str] = []

# A 层规则：{pattern: {skills, hits, last_hit, source, priority}}
_A_RULES: Dict[str, dict] = {}

# B→A 升级计数器：{(pattern_hash, skill): count}
_PROMOTE_COUNTER: Dict[Tuple[str, str], int] = {}

# 会话缓存：已推荐的 skill 集合（去重）
_SESSION_CACHE: Dict[str, set] = {}

# 任务切换检测：上次用户消息 hash
_LAST_MESSAGE_HASH: Dict[str, str] = {}

# 上次匹配结果缓存
_LAST_MATCH_RESULT: Dict[str, Optional[List[dict]]] = {}


# ---------------------------------------------------------------------------
# Phase 2: 索引构建
# ---------------------------------------------------------------------------

def _build_skill_index() -> Tuple[Dict[str, dict], List[str]]:
    """启动时扫描 skills_list，构建技能索引 + 残骸清单。

    Returns:
        (index, broken): index 为 {name: {description, category}}，
        broken 为残骸 skill 名列表。
    """
    index: Dict[str, dict] = {}
    broken: List[str] = []

    try:
        # 通过 Hermes 内部 API 获取 skills_list
        # 如果不可用，退而读取 skills 目录
        skills = _get_skills_list()
    except Exception as e:
        logger.warning("[ssr] skills_list() 调用失败: %s", e)
        return index, broken

    for skill_name in skills:
        try:
            info = _get_skill_info(skill_name)
            if info is None:
                broken.append(skill_name)
                continue

            index[skill_name] = {
                "description": info.get("description", ""),
                "category": info.get("category", ""),
            }
        except Exception as e:
            logger.debug("[ssr] 读取 %s 失败: %s", skill_name, e)
            broken.append(skill_name)

    return index, broken


def _get_skills_list() -> List[str]:
    """获取所有已安装 skill 的名称列表。

    尝试通过 skills_list tool 获取，不可用时退而读取文件系统。
    """
    # 尝试通过 skills_list 工具获取
    try:
        from hermes_cli.skills.registry import get_registry
        reg = get_registry()
        return list(reg.list_skills().keys())
    except Exception:
        pass

    # 回退：扫描文件系统
    skills = []
    skills_dir = Path.home() / ".hermes" / "skills"
    agents_dir = Path.home() / ".agents" / "skills"
    for base in (skills_dir, agents_dir):
        if not base.exists():
            continue
        for skill_md in base.rglob("SKILL.md"):
            try:
                content = skill_md.read_text()
                # 提取 name
                for line in content.split("\n"):
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                        if name:
                            skills.append(name)
                        break
            except Exception:
                pass
    return list(set(skills))


def _get_skill_info(skill_name: str) -> Optional[dict]:
    """获取单个 skill 的详细信息。

    优先通过 skill_view tool 获取，不可用时解析 SKILL.md。
    """
    # 先获取 description 和 category
    try:
        from hermes_cli.skills.registry import get_registry
        reg = get_registry()
        skill = reg.get_skill(skill_name)
        if skill:
            return {
                "description": getattr(skill, "description", ""),
                "category": getattr(skill, "category", ""),
            }
    except Exception:
        pass

    # 回退：搜索并解析 SKILL.md
    for base in (Path.home() / ".hermes" / "skills", Path.home() / ".agents" / "skills"):
        for skill_md in base.rglob("SKILL.md"):
            try:
                content = skill_md.read_text()
                found_name = None
                for line in content.split("\n"):
                    if line.startswith("name:"):
                        found_name = line.split(":", 1)[1].strip()
                        break
                if found_name == skill_name:
                    desc = ""
                    cat = str(skill_md.parent.parent.name)
                    # 提取 description
                    for line in content.split("\n"):
                        if line.startswith("description:"):
                            desc = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
                    return {"description": desc, "category": cat}
            except Exception:
                pass
    return None


# ---------------------------------------------------------------------------
# Phase 3: A 层关键词匹配
# ---------------------------------------------------------------------------

def _load_a_rules() -> Dict[str, dict]:
    """加载 A 层固化规则。"""
    if not A_RULES_PATH.exists():
        return {}
    try:
        return json.loads(A_RULES_PATH.read_text())
    except Exception as e:
        logger.warning("[ssr] a_rules.json 读取失败: %s", e)
        return {}


def _save_a_rules(rules: Dict[str, dict]) -> None:
    """保存 A 层规则到磁盘。"""
    try:
        A_RULES_PATH.write_text(json.dumps(rules, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning("[ssr] a_rules.json 写入失败: %s", e)


def _match_a_layer(user_message: str) -> Optional[List[dict]]:
    """A 层关键词精确匹配。

    Returns:
        匹配到的 skill 列表 [{name, phase}]，或 None 表示未匹配。
    """
    global _A_HIT_COUNT
    if not _A_RULES:
        return None

    candidates: List[Tuple[str, dict]] = []  # (pattern, rule)

    for pattern, rule in _A_RULES.items():
        try:
            if re.search(pattern, user_message, re.IGNORECASE):
                candidates.append((pattern, rule))
        except re.error:
            continue

    if not candidates:
        return None

    # 排序：priority（manual > auto）→ 精确度（模式长度）→ hits
    def _sort_key(item: Tuple[str, dict]) -> Tuple[int, int, int]:
        _pattern, rule = item
        priority = rule.get("priority", 0)
        specificity = len(_pattern)
        hits = rule.get("hits", 0)
        # manual (priority=10) > auto (priority=1)
        return (-priority, -specificity, -hits)

    candidates.sort(key=_sort_key)

    # 收集 skills，去重，上限 5
    seen: set = set()
    result: List[dict] = []
    for _pattern, rule in candidates:
        # 更新命中计数
        rule["hits"] = rule.get("hits", 0) + 1
        rule["last_hit"] = time.strftime("%Y-%m-%d")
        for skill_info in rule.get("skills", []):
            name = skill_info if isinstance(skill_info, str) else skill_info.get("name", "")
            if name not in seen:
                seen.add(name)
                phase = skill_info.get("phase", "") if isinstance(skill_info, dict) else ""
                result.append({"name": name, "phase": phase})
            if len(result) >= 5:
                break
        if len(result) >= 5:
            break

    _mark_a_dirty()
    _A_HIT_COUNT += 1
    if _A_HIT_COUNT >= 5:
        _flush_a_rules()
    return result if result else None


# A 层脏标记：避免每次命中都写盘
_A_DIRTY = False
_A_HIT_COUNT = 0  # 自动落盘计数器


def _mark_a_dirty() -> None:
    global _A_DIRTY
    _A_DIRTY = True


def _flush_a_rules() -> None:
    """延迟写盘：仅在显式调用时保存。"""
    global _A_DIRTY, _A_HIT_COUNT
    if _A_DIRTY:
        _save_a_rules(_A_RULES)
        _A_DIRTY = False
        _A_HIT_COUNT = 0
        logger.debug("[ssr] A 层规则已落盘")


def _cleanup_a_rules() -> None:
    """清理 A 层过期规则：超过 TTL 天未命中 + 上限淘汰。"""
    if not _A_RULES:
        return

    ttl_days = _a_rules_ttl_days()
    ttl_seconds = ttl_days * 86400
    now = time.time()
    expired: List[str] = []

    for pattern, rule in _A_RULES.items():
        last_hit_str = rule.get("last_hit", "")
        # 空 last_hit = 从未命中过，视为新规则，不过期
        if not last_hit_str:
            continue
        try:
            last_hit = time.mktime(time.strptime(last_hit_str, "%Y-%m-%d"))
            if now - last_hit > ttl_seconds:
                expired.append(pattern)
        except (ValueError, OverflowError):
            expired.append(pattern)

    for p in expired:
        logger.info("[ssr] A 层规则过期: %s", p)
        del _A_RULES[p]

    # 上限淘汰：超 max → 淘汰命中数最低的
    max_rules = _a_rules_max()
    if len(_A_RULES) > max_rules:
        sorted_rules = sorted(_A_RULES.items(), key=lambda x: x[1].get("hits", 0))
        to_evict = len(_A_RULES) - max_rules
        for i in range(to_evict):
            pattern = sorted_rules[i][0]
            logger.info("[ssr] A 层规则淘汰（命中数低）: %s", pattern)
            del _A_RULES[pattern]

    if expired or len(_A_RULES) > max_rules:
        _save_a_rules(_A_RULES)


def _promote_to_a(pattern: str, skills: List[dict]) -> None:
    """B 层匹配升级到 A 层。"""
    # 将 skills 转为存储格式
    skill_entries = []
    for s in skills:
        skill_entries.append({"name": s["name"], "phase": s.get("phase", "")})

    _A_RULES[pattern] = {
        "skills": skill_entries,
        "hits": PROMOTE_THRESHOLD,
        "last_hit": time.strftime("%Y-%m-%d"),
        "source": "auto",
        "priority": 1,
    }
    _mark_a_dirty()
    logger.info("[ssr] B→A 升级: %s → %s", pattern, [s["name"] for s in skills])


# ---------------------------------------------------------------------------
# Phase 4: B 层 LLM 语义匹配
# ---------------------------------------------------------------------------

# B 层结果缓存：{message_hash: (expires_at, result)}
_B_CACHE: Dict[str, Tuple[float, Optional[List[dict]]]] = {}


def _match_b_layer(user_message: str, retry: bool = True) -> Optional[List[dict]]:
    """B 层语义匹配。支持 ollama / openai / main 三种后端，含预过滤+缓存+重试。"""
    if not _SKILL_INDEX:
        return None

    # ── 缓存检测 ──
    cache_key = _derive_pattern(user_message)
    if cache_key in _B_CACHE:
        expires, cached_result = _B_CACHE[cache_key]
        if time.time() < expires:
            logger.debug("[ssr] B 层缓存命中: %s", cache_key)
            return cached_result

    # ── 预过滤：223 → ~20 ──
    candidates = _prefilter_skills(user_message, max_candidates=20)
    if not candidates:
        candidates = list(_SKILL_INDEX.keys())[:20]

    prompt = _build_b_prompt(user_message, candidates=candidates)
    provider = _b_provider()

    try:
        if provider == "ollama":
            result = _match_b_ollama(prompt)
        elif provider == "openai":
            result = _match_b_openai(user_message)
        elif provider == "main":
            result = _match_b_main(user_message)
        else:
            logger.warning("[ssr] 未知 B 层后端: %s", provider)
            return None

        # 缓存结果（60s）
        _B_CACHE[cache_key] = (time.time() + 60, result)
        return result

    except Exception as e:
        # ── 冷启动重试（仅 ollama 后端）──
        err_msg = str(e).lower()
        is_timeout = any(kw in err_msg for kw in ("timed out", "timeout", "readtimeout"))
        if retry and is_timeout and provider == "ollama":
            logger.info("[ssr] B 层超时，Ollama 预热重试中...")
            try:
                import httpx
                httpx.post(
                    f"{_b_base_url()}/api/generate",
                    json={"model": _b_model(), "prompt": "warmup", "stream": False,
                          "options": {"num_predict": 1}},
                    timeout=15,
                )
                logger.info("[ssr] 预热完成，重新调用 B 层")
            except Exception as we:
                logger.debug("[ssr] 预热失败: %s", we)
            return _match_b_layer(user_message, retry=False)
        elif retry and is_timeout:
            # main/openai 后端超时 → 直接重试一次
            logger.info("[ssr] B 层超时（%s），直接重试...", type(e).__name__)
            return _match_b_layer(user_message, retry=False)

        logger.info("[ssr] B 层调用失败（%s/%s 降级跳过）: %s", provider, _b_model(), e)
        return None


def _prefilter_skills(user_message: str, max_candidates: int = 20) -> List[str]:
    """关键词粗筛：从 223 skill 中挑出最相关的 ~20 个。

    三层策略：
    1. 中文双字 + 英文单词提取
    2. 优先匹配 skill 名（高权重），其次描述
    3. A 层规则命中的 skill 直接加入
    """
    # 提取关键词
    keywords = set()
    for w in re.findall(r"[a-zA-Z]{2,}", user_message):
        keywords.add(w.lower())
    msg_clean = re.sub(r"[^\u4e00-\u9fff]", "", user_message)
    for i in range(len(msg_clean) - 1):
        keywords.add(msg_clean[i:i+2])  # 双字组合

    scores: Dict[str, int] = {}

    # ── 匹配 skill 名（权重 ×3） ──
    for name in _SKILL_INDEX:
        name_lower = name.lower()
        for kw in keywords:
            if kw in name_lower:
                scores[name] = scores.get(name, 0) + 3

    # ── 匹配描述（权重 ×1） ──
    for name, info in _SKILL_INDEX.items():
        desc = info.get("description", "").lower()
        for kw in keywords:
            if kw in desc:
                scores[name] = scores.get(name, 0) + 1

    # ── A 层规则命中的 skill 加分 ──
    a_result = _match_a_layer(user_message)
    if a_result:
        for s in a_result:
            name = s["name"]
            scores[name] = scores.get(name, 0) + 10  # 高权重锁入

    # 排序取 top N
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    result = [name for name, _ in ranked[:max_candidates]]

    # 如果结果太少，补全量索引的前 N 个
    if len(result) < 5:
        for name in _SKILL_INDEX:
            if name not in result:
                result.append(name)
            if len(result) >= max_candidates:
                break

    return result


def _build_b_prompt(user_message: str, candidates: Optional[List[str]] = None) -> str:
    """构建 B 层匹配 prompt。candidates 为空时使用全量索引。"""
    if candidates is None:
        names = list(_SKILL_INDEX.keys())
    else:
        names = candidates

    skill_lines = []
    for name in names:
        info = _SKILL_INDEX.get(name, {})
        desc = info.get("description", "")
        skill_lines.append(f"- {name}: {desc}")
    skill_list = "\n".join(skill_lines)

    return f"""你是一个技能匹配器。根据用户消息，从以下可用技能中选择最匹配的 1-3 个。

可用技能（名称: 描述）：
{skill_list}

用户消息：「{user_message}」

返回 JSON 格式（只返回 JSON，不要其他内容）：
{{"skills": ["技能名1", "技能名2"], "phases": ["DISCOVER|PLAN|BUILD|VERIFY", ...]}}

规则：
- skills: 匹配的技能名列表（1-3个，必须从上面的可用技能中选择）
- phases: 对应每个技能的执行阶段标签
  - DISCOVER: 调研/发散/学习/搜索类
  - PLAN: 规划/设计/架构类
  - BUILD: 开发/实现/创建/构建类
  - VERIFY: 测试/验证/审查/检查类
- 无匹配返回 {{"skills": [], "phases": []}}"""


def _match_b_ollama(prompt: str) -> Optional[List[dict]]:
    """B 层 Ollama 后端."""
    import httpx
    from urllib.parse import urljoin

    url = urljoin(_b_base_url(), "/api/generate")
    resp = httpx.post(
        url,
        json={"model": _b_model(), "prompt": prompt, "stream": False,
              "options": {"temperature": 0.1}},
        timeout=_b_timeout(),
    )
    resp.raise_for_status()
    data = resp.json()
    return _parse_b_response(data.get("response", ""))


def _match_b_openai(user_message: str) -> Optional[List[dict]]:
    """B 层 OpenAI 兼容后端（SiliconFlow / DeepSeek 等）."""
    import httpx

    api_key = _b_api_key()
    if not api_key:
        logger.warning("[ssr] B 层 openai 模式缺少 api_key")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    skill_lines = [f"- {n}: {i.get('description','')}" for n, i in _SKILL_INDEX.items()]
    skill_list = "\n".join(skill_lines)

    resp = httpx.post(
        f"{_b_base_url()}/v1/chat/completions",
        json={
            "model": _b_model(),
            "messages": [
                {"role": "system", "content": f"你是技能匹配器。可用技能：\n{skill_list}"},
                {"role": "user", "content": f"根据\u300c{user_message}\u300d匹配 1-3 个技能，返回 JSON: {{\"skills\":[\"...\"],\"phases\":[\"...\"]}}"},
            ],
            "temperature": 0.1,
        },
        headers=headers,
        timeout=_b_timeout(),
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return _parse_b_response(content)


def _match_b_main(user_message: str) -> Optional[List[dict]]:
    """B 层复用 Hermes 主模型。优先直接读 config.yaml。"""
    import httpx
    import os
    import yaml

    model = ""
    base_url = ""
    api_key = ""

    # 路径 1：直接读 config.yaml（无需 hermes_cli 导入）
    config_path = Path.home() / ".hermes" / "config.yaml"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        model_cfg = cfg.get("model", {})
        model = model_cfg.get("default", "")
        base_url = model_cfg.get("base_url", "")
        api_key = model_cfg.get("api_key", "")
    except Exception:
        pass

    # 路径 2：尝试 hermes_cli（可能不可用）
    if not base_url or not model:
        try:
            from hermes_cli.config import load_config
            cfg = load_config()
            model_cfg = cfg.get("model", {})
            model = model_cfg.get("default", "")
            base_url = model_cfg.get("base_url", "")
            api_key = model_cfg.get("api_key", "")
        except Exception:
            pass

    # 路径 3：降级到 b_layer 配置（openai 模式凭据）
    if not base_url or not model:
        model = _b_model()
        base_url = _b_base_url()
        api_key = _b_api_key()
        if not base_url or not api_key:
            logger.warning("[ssr] B 层 main 模式无法获取凭据（三路径全失败）")
            return None
        logger.info("[ssr] B 层 main 降级到 b_layer 凭据")

    # 环境变量展开
    if api_key and api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, api_key)

    if not base_url or not model:
        logger.warning("[ssr] B 层 main 模式无法读取主模型配置")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    skill_lines = [f"- {n}: {i.get('description','')}" for n, i in _SKILL_INDEX.items()]
    skill_list = "\n".join(skill_lines)

    resp = httpx.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": f"你是技能匹配器。可用技能：\n{skill_list}"},
                {"role": "user", "content": f"根据\u300c{user_message}\u300d匹配 1-3 个技能，返回 JSON: {{\"skills\":[\"...\"],\"phases\":[\"...\"]}}"},
            ],
            "temperature": 0.1,
            "max_tokens": 100,
        },
        headers=headers,
        timeout=_b_timeout(),
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return _parse_b_response(content)


def _parse_b_response(raw: str) -> Optional[List[dict]]:
    """解析 B 层返回的 JSON，提取技能列表。"""
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        logger.debug("[ssr] B 层返回非 JSON: %s", raw[:200])
        return None

    parsed = json.loads(json_match.group())
    skill_names = parsed.get("skills", [])
    phases = parsed.get("phases", [])

    if not skill_names:
        return None

    result = []
    for i, name in enumerate(skill_names):
        if name not in _SKILL_INDEX:
            continue
        phase = phases[i] if i < len(phases) and phases[i] in PHASE_LABELS else ""
        result.append({"name": name, "phase": phase})

    return result if result else None

# Phase 5: 核心调度
# ---------------------------------------------------------------------------

def _detect_task_switch(session_id: str, user_message: str) -> bool:
    """检测是否发生任务切换。显式关键词 + 短消息（可能是新话题）。"""
    if TASK_SWITCH_PATTERNS.search(user_message):
        return True
    # 短消息（≤15 字）且不含明确延续上下文 → 可能新话题
    if len(user_message) <= 15:
        return True
    return False


# A 层最后命中模式缓存，用于检测任务切换
_LAST_A_PATTERN: Dict[str, str] = {}

# 会话推荐计数：{session_id: {skill_name: (last_recommended_at, count)}}
_SESSION_REC_COUNT: Dict[str, Dict[str, Tuple[float, int]]] = {}


def _format_recommendation(skills: List[dict]) -> str:
    """格式化推荐消息。"""
    phase_emoji = {
        "DISCOVER": "🔍",
        "PLAN": "📋",
        "BUILD": "🔨",
        "VERIFY": "✅",
    }
    parts = []
    for i, s in enumerate(skills, 1):
        phase = s.get("phase", "")
        emoji = phase_emoji.get(phase, "")
        phase_str = f" ({phase})" if phase else ""
        parts.append(f"{emoji}{s['name']}{phase_str}")

    mode = _ssr_mode()
    if mode == "enforce":
        return f"[MUST-LOAD] SSR 强制加载: {' | '.join(parts)}\n以上技能必须在此回复中使用 skill_view() 加载，不可跳过。"
    return f"[SSR] 建议加载: {' | '.join(parts)}"


def _pre_llm_call(
    session_id: str = "",
    user_message: str = "",
    is_first_turn: bool = False,
    platform: str = "",
    **kwargs,
) -> Optional[dict]:
    """pre_llm_call hook 入口。"""
    if not _hook_enabled():
        return None

    if not user_message or len(user_message) < 3:
        return None

    try:
        # ── 每次提问扫描（如启用）──
        global _SKILL_INDEX
        if _scan_mode() == "every_turn":
            idx, broken = _build_skill_index()
            if idx:
                _SKILL_INDEX = idx

        # ── 任务切换检测 ──
        if _detect_task_switch(session_id, user_message):
            _SESSION_CACHE.pop(session_id, None)
            _SESSION_REC_COUNT.pop(session_id, None)
            _LAST_A_PATTERN.pop(session_id, None)
            logger.debug("[ssr] 检测到任务切换，清除会话缓存")

        # ── A 层匹配 ──
        result = _match_a_layer(user_message)
        if result:
            # 冷却制去重：同 skill 60 秒内不重复推荐（非永久跳过）
            rec_count = _SESSION_REC_COUNT.setdefault(session_id, {})
            now = time.time()
            COOLDOWN = 60
            fresh = []
            for s in result:
                name = s["name"]
                if name in rec_count:
                    last_t, _ = rec_count[name]
                    if now - last_t < COOLDOWN:
                        continue
                fresh.append(s)
                rec_count[name] = (now, rec_count.get(name, (0, 0))[1] + 1)
            if not fresh:
                return None
            # 按阶段排序
            fresh.sort(key=lambda x: PHASE_ORDER.index(x["phase"]) if x["phase"] in PHASE_ORDER else 99)
            rec = _format_recommendation(fresh)
            logger.info("[ssr] A 层命中: %s", [s["name"] for s in fresh])
            return {"context": rec}

        # ── B 层匹配 ──
        result = _match_b_layer(user_message)
        if not result:
            return None

        # 冷却制去重
        rec_count = _SESSION_REC_COUNT.setdefault(session_id, {})
        now = time.time()
        COOLDOWN = 60
        fresh = []
        for s in result:
            name = s["name"]
            if name in rec_count:
                last_t, _ = rec_count[name]
                if now - last_t < COOLDOWN:
                    continue
            fresh.append(s)
            rec_count[name] = (now, rec_count.get(name, (0, 0))[1] + 1)
        if not fresh:
            return None

        # 按阶段排序
        fresh.sort(key=lambda x: PHASE_ORDER.index(x["phase"]) if x["phase"] in PHASE_ORDER else 99)

        # ── B→A 升级检测 ──
        # 用用户消息的前 30 字符做简易 pattern
        pattern_key = _derive_pattern(user_message)
        for s in fresh:
            counter_key = (pattern_key, s["name"])
            count = _PROMOTE_COUNTER.get(counter_key, 0) + 1
            _PROMOTE_COUNTER[counter_key] = count
            if count >= PROMOTE_THRESHOLD:
                _promote_to_a(pattern_key, fresh)
                _PROMOTE_COUNTER.pop(counter_key, None)
                logger.info("[ssr] B→A 升级触发: %s → %d skills", pattern_key, len(fresh))

        rec = _format_recommendation(fresh)
        logger.info("[ssr] B 层命中: %s", [s["name"] for s in fresh])
        return {"context": rec}

    except Exception as e:
        logger.warning("[ssr] pre_llm_call 异常（降级跳过）: %s", e)
        return None


def _derive_pattern(user_message: str) -> str:
    """从用户消息提取简易匹配模式，用于 B→A 升级的 key。

    策略：取前 30 字符，去掉标点 → 作为模式。
    """
    clean = re.sub(r"[^\w\u4e00-\u9fff]", "", user_message)
    return clean[:30] if clean else "fallback"


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """注册 pre_llm_call hook + 启动时构建索引。"""
    global _SKILL_INDEX, _BROKEN_SKILLS, _A_RULES

    ctx.register_hook("pre_llm_call", _pre_llm_call)

    # 启动时构建索引
    try:
        _SKILL_INDEX, _BROKEN_SKILLS = _build_skill_index()
    except Exception as e:
        logger.warning("[ssr] 索引构建失败: %s", e)

    # 加载 A 层规则 + 清理过期
    _A_RULES = _load_a_rules()
    _cleanup_a_rules()

    # 预热（仅 ollama 后端需要）
    if _b_provider() == "ollama":
        try:
            import httpx
            httpx.post(
                f"{_ollama_url()}/api/generate",
                json={"model": _ollama_model(), "prompt": "ping", "stream": False,
                      "options": {"num_predict": 1}},
                timeout=10,
            )
            logger.info("[ssr] Ollama 预热完成")
        except Exception as e:
            logger.info("[ssr] Ollama 预热跳过（%s）", e)

    logger.info(
        "[ssr] 插件注册完成 | 可用 skill: %d | 残骸: %d | A 层规则: %d | B 层: %s/%s timeout=%ds",
        len(_SKILL_INDEX),
        len(_BROKEN_SKILLS),
        len(_A_RULES),
        _b_provider(),
        _b_model(),
        _b_timeout(),
    )

    # 残骸报告
    if _BROKEN_SKILLS:
        logger.warning(
            "[ssr] 检测到 %d 个残骸 skill: %s",
            len(_BROKEN_SKILLS),
            ", ".join(_BROKEN_SKILLS[:10]),
        )
