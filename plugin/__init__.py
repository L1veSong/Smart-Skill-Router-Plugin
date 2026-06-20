"""
智配路由 (SSR) — Smart Skill Router Plugin v0.6.3


自动匹配用户意图到最合适的 skill 并推荐加载。
A 层（Embedding 语义匹配，bge-m3 1024维）+ B 层（LLM 语义匹配，五后端可选）。
支持 main / openai / ollama / lmstudio / llamacpp 五种后端。
自学习升级 + Dashboard 可视化管理 + 推荐/强制模式 + 暂停开关。

v0.6.2 (2026-06-14):
  - _load_a_rules 损坏备份 + _save_a_rules 空覆盖保护
  - register() A层规则加载/清理诊断日志
  - miss 路径补日志（A/B两层无匹配时可见）
  - 修复：重启后 a_rules.json 可能被空覆盖

v0.6.1 (2026-06-10):
  - 智能冷却：自适应冷却（已加载×3、反复推荐未加载×0.5、紧急×0.5、5次未加载跳过）
  - 增量索引自动运行：每10分钟自动全量 sync + description 变更检测

配置（config.yaml）:

    ssr:
      enabled: true
      mode: suggest
      scan_mode: startup
      b_layer:
        provider: main
        timeout: 30
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


def _auto_gen_enabled() -> bool:
    """是否启用 auto-gen 规则生成（默认 true，可配置 ssr.auto_gen_rules: false 关闭）。"""
    cfg = _load_ssr_config()
    return cfg.get("auto_gen_rules", True)


def _hook_enabled() -> bool:
    cfg = _load_ssr_config()
    if not cfg.get("enabled", True):
        return False
    hooks = cfg.get("hooks", {})
    return hooks.get("pre_llm_call", True)


def _ssr_mode() -> str:
    """推荐模式：suggest（建议）| enforce（强制）。"""
    return _load_ssr_config().get("mode", "suggest")


def _b_provider() -> str:
    """B 层后端: main | openai | ollama | lmstudio | llamacpp"""
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


def _prefilter_candidates() -> int:
    """B 层预过滤候选数（默认20，0=不过滤）。"""
    return _load_ssr_config().get("prefilter_candidates", 20)


def _display_max() -> int:
    """推荐展示折叠阈值（默认12，0=不折叠）。"""
    return _load_ssr_config().get("display_max", 12)


def _max_total_recommendations() -> int:
    """推荐总数硬上限（默认12，0=不限制）。超过此数按质量截断。"""
    return _load_ssr_config().get("max_total_recommendations", 12)


def _similarity_floor() -> float:
    """embedding 相似度地板。score < 此值直接丢弃。"""
    return _load_ssr_config().get("similarity_floor", 0.35)


def _confidence_threshold() -> float:
    """整体匹配置信度阈值。top-3 embedding 平均 < 此值 → 跳过推荐。"""
    return _load_ssr_config().get("confidence_threshold", 0.40)


def _keyword_weight_boost() -> float:
    """关键词命中 skill 的 embedding 加权。默认 0.3。"""
    return _load_ssr_config().get("keyword_weight_boost", 0.30)


def _phase_cooldown(phase: str) -> int:
    """分阶段冷却时长（秒）。DISCOVER 30s / PLAN 60s / BUILD 120s / VERIFY 30s。"""
    defaults = {"DISCOVER": 30, "PLAN": 60, "BUILD": 120, "VERIFY": 30}
    cfg = _load_ssr_config().get("phase_cooldowns", {})
    return int(cfg.get(phase, defaults.get(phase, 60)))


def _smart_cooldown(session_id: str, skill_name: str, phase: str, user_message: str = "") -> int:
    """智能自适应冷却（秒）。

    规则：
    - 检测到 skill 已被用户加载 → cooldown × 3（已满足需求，勿重复打扰）
    - 同一 skill 推荐 3+ 次仍未加载 → cooldown × 0.5（用户可能在犹豫，加密度）
    - 同一 skill 推荐 5+ 次仍未加载 → 标记为 ignore（用户明确不需要）
    - 用户消息含紧急/催促词 → cooldown × 0.5（快节奏场景）
    - 其他 → 使用默认分阶段冷却
    """
    base = _phase_cooldown(phase)

    # 跟踪计数
    tracker = _COOLDOWN_TRACKER.setdefault(session_id, {})
    entry = tracker.setdefault(skill_name, {"recs": 0, "last_rec": 0, "loaded": False})
    entry["recs"] += 1
    entry["last_rec"] = time.time()

    # 检测是否已被加载：用户消息中包含 skill 名或 "用 xxx" 模式
    if not entry["loaded"]:
        msg_lower = user_message.lower()
        name_lower = skill_name.lower()
        # 检测 "用 xxx"、"加载 xxx"、"skill_view xxx" 模式
        load_patterns = [
            rf"(用|加载|load|skill.view|调用)\s*{re.escape(name_lower)}",
            rf"{re.escape(name_lower)}\s*(skill|加载|用一下)",
        ]
        for pat in load_patterns:
            if re.search(pat, msg_lower):
                entry["loaded"] = True
                logger.debug("[ssr] 冷却检测: %s 已被加载 → cooldown ×3", skill_name)
                break

    # 规则 1: 已加载 → 3 倍冷却
    if entry["loaded"]:
        return base * 3

    # 规则 2: 推荐 5+ 次未加载 → 用户明确不需要，跳过此次（返回 -1 表示忽略）
    if entry["recs"] >= 5:
        logger.debug("[ssr] 冷却检测: %s 推荐 %d 次未加载 → 跳过", skill_name, entry["recs"])
        return -1

    # 规则 3: 推荐 3+ 次未加载 → 缩短冷却（加密度）
    if entry["recs"] >= 3:
        return max(base // 2, 10)

    # 规则 4: 紧急/催促消息 → 减半冷却
    urgency_patterns = re.compile(r"快|急|马上|立刻|赶紧|速度|赶时间|urgent|ASAP|hurry", re.IGNORECASE)
    if urgency_patterns.search(user_message):
        return max(base // 2, 10)

    return base


# 智能冷却追踪：{session_id: {skill_name: {recs, last_rec, loaded}}}
_COOLDOWN_TRACKER: Dict[str, Dict[str, dict]] = {}


# ---------------------------------------------------------------------------
# Embedding 后端配置
# ---------------------------------------------------------------------------

def _embed_provider() -> str:
    """embedding 后端: ollama | siliconflow | openai"""
    return _load_ssr_config().get("embedding", {}).get("provider", "ollama")


def _embed_model() -> str:
    """embedding 模型名"""
    return _load_ssr_config().get("embedding", {}).get("model", "nomic-embed-text")


def _embed_timeout() -> int:
    """embedding API 超时（秒）"""
    return _load_ssr_config().get("embedding", {}).get("timeout", 10)


def _embed_api_key() -> str:
    """embedding API key。优先 ssr.embedding.api_key，回退 auxiliary.vision.api_key"""
    cfg = _load_ssr_config()
    key = cfg.get("embedding", {}).get("api_key", "")
    if key:
        return key
    # 回退到 siliconflow 全局 key
    try:
        import yaml, os
        with open(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")) + "/config.yaml") as f:
            full = yaml.safe_load(f)
        vis = full.get("auxiliary", {}).get("vision", {})
        if vis.get("provider", "").startswith("custom:Api.siliconflow"):
            return vis.get("api_key", "")
    except Exception:
        pass
    return ""


def _embed_base_url() -> str:
    """embedding API base_url。默认 siliconflow"""
    cfg = _load_ssr_config()
    url = cfg.get("embedding", {}).get("base_url", "")
    if url:
        return url
    return "https://api.siliconflow.cn/v1"


# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------

# 技能索引：启动时构建，每次启动重建
_SKILL_INDEX: Dict[str, dict] = {}

# 残骸清单
_BROKEN_SKILLS: List[str] = []

# A 层规则：{pattern: {skills, hits, last_hit, source, priority}}
_A_RULES: Dict[str, dict] = {}

# Embedding 索引：{skill_name: {embedding: [768维], desc: str}}
_EMBEDDING_INDEX: Dict[str, dict] = {}

# B→A 升级计数器：{(pattern_hash, skill): count}
_PROMOTE_COUNTER: Dict[Tuple[str, str], int] = {}

# 会话缓存：已推荐的 skill 集合（去重）
_SESSION_CACHE: Dict[str, set] = {}

# 任务切换检测：上次用户消息 hash
_LAST_MESSAGE_HASH: Dict[str, str] = {}

# 上次匹配结果缓存
_LAST_MATCH_RESULT: Dict[str, Optional[List[dict]]] = {}

# 技能目录 mtime：用于检测文件系统变更（6.1）
_SKILLS_MTIME: float = 0.0

# 热更新失败标记：下次全量重建（6.2）
_INDEX_DIRTY: bool = False

# 增量自动同步：距上次全量 embedding sync 的时间（秒），默认每 10 分钟
_LAST_AUTO_SYNC: float = 0.0
_AUTO_SYNC_INTERVAL: int = 600  # 10 分钟


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
                    # 提取 description（兼容单行和 YAML literal block scalar）
                    lines = content.split("\n")
                    in_frontmatter = False
                    for i, line in enumerate(lines):
                        if line.strip() == "---":
                            if not in_frontmatter:
                                in_frontmatter = True
                                continue
                            else:
                                break  # end of frontmatter
                        if in_frontmatter and line.startswith("description:"):
                            val = line.split(":", 1)[1].strip()
                            if val in ("", "|", ">", "|-", ">-"):
                                # YAML block scalar — 读后续行
                                body_lines = []
                                for j in range(i + 1, min(i + 10, len(lines))):
                                    next_line = lines[j]
                                    if next_line.startswith(("name:", "version:", "author:", "---")):
                                        break
                                    stripped = next_line.strip()
                                    if stripped:
                                        body_lines.append(stripped)
                                desc = " ".join(body_lines)
                            else:
                                desc = val.strip().strip('"').strip("'")
                            break
                    # 提取正文前 3 段散文 — 用于富化 description 或兜底
                    # 跳过表格行（|...）、代码块、标题行
                    body_desc = ""
                    body_start = 0
                    dashes = 0
                    for i, line in enumerate(lines):
                        if line.strip() == "---":
                            dashes += 1
                            if dashes == 2:
                                body_start = i + 1
                                break
                    paragraphs = []
                    current_para = []
                    in_code_block = False
                    for line in lines[body_start:]:
                        stripped = line.strip()
                        if stripped.startswith("```"):
                            in_code_block = not in_code_block
                            if current_para:
                                para_text = " ".join(current_para)
                                if len(para_text) > 15:
                                    paragraphs.append(para_text)
                                current_para = []
                            continue
                        if in_code_block:
                            continue
                        # 跳过：空行、标题、表格行、纯符号行
                        if (not stripped or stripped.startswith("#")
                                or stripped.startswith("|")
                                or stripped.startswith("-")
                                or stripped.startswith(">")
                                or len(stripped) < 15):
                            if current_para:
                                para_text = " ".join(current_para)
                                if len(para_text) > 15:
                                    paragraphs.append(para_text)
                                current_para = []
                            if len(paragraphs) >= 3:
                                break
                            continue
                        current_para.append(stripped)
                    if current_para and len(paragraphs) < 3:
                        para_text = " ".join(current_para)
                        if len(para_text) > 15:
                            paragraphs.append(para_text)
                    body_desc = " ".join(paragraphs)[:300] if paragraphs else ""

                    if desc and len(desc) >= 5:
                        # 已有 YAML description → 用正文富化
                        if body_desc and body_desc not in desc:
                            desc = f"{desc}. {body_desc}"
                    elif body_desc:
                        # 无 description → 正文兜底
                        desc = body_desc
                    return {"description": desc, "category": cat}
            except Exception:
                pass
    return None


# ---------------------------------------------------------------------------
# Phase 3: A 层关键词匹配
# ---------------------------------------------------------------------------

def _load_a_rules() -> Dict[str, dict]:
    """加载 A 层固化规则。损坏时自动备份。"""
    if not A_RULES_PATH.exists():
        return {}
    try:
        data = json.loads(A_RULES_PATH.read_text())
        if not isinstance(data, dict):
            raise ValueError(f"expected dict, got {type(data).__name__}")
        return data
    except Exception as e:
        logger.warning("[ssr] a_rules.json 读取失败（%s），备份损坏文件", e)
        try:
            backup = A_RULES_PATH.with_suffix(".json.corrupted")
            backup.write_text(A_RULES_PATH.read_text())
        except Exception:
            pass
        return {}


def _save_a_rules(rules: Dict[str, dict]) -> None:
    """保存 A 层规则到磁盘。空覆盖前自动备份。"""
    try:
        if not rules and A_RULES_PATH.exists() and A_RULES_PATH.stat().st_size > 10:
            backup = A_RULES_PATH.with_suffix(".json.bak")
            backup.write_text(A_RULES_PATH.read_text())
            logger.warning("[ssr] a_rules.json 即将被空覆盖，已备份到 %s", backup)
        A_RULES_PATH.write_text(json.dumps(rules, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning("[ssr] a_rules.json 写入失败: %s", e)


def _match_a_layer_keyword(user_message: str) -> Optional[List[dict]]:
    """[保留] A 层关键词精确匹配（原版，embedding 不可用时的 fallback）。"""
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

    # 收集 skills，去重（不设上限——合并阶段由 _match_a_layer 统一去重 + _pre_llm_call 冷却制控量）
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

    _mark_a_dirty()
    _A_HIT_COUNT += 1
    if _A_HIT_COUNT >= 5:
        _flush_a_rules()
    return result if result else None


# ---------------------------------------------------------------------------
# A 层：Embedding 语义匹配（Phase 2）
# ---------------------------------------------------------------------------

def _match_a_layer(user_message):
    """A 层：关键词精确匹配 + Embedding 语义匹配 → 合并去重。

    两条路径并行，不互相封堵：
    - 关键词：精确命中（手动规则、B→A 升级），零延迟，排前面
    - Embedding：语义覆盖（bge-m3 top-30），补充关键词未覆盖的
    """
    # 第一步：关键词精确匹配
    keyword_result = _match_a_layer_keyword(user_message) or []

    # 第二步：Embedding 语义匹配
    emb_result = []
    if _EMBEDDING_INDEX:
        query = _expand_chinese_query(user_message)
        msg_vec = _embed(query)
        if msg_vec:
            scores = []
            for name, entry in _EMBEDDING_INDEX.items():
                sim = _cosine_sim(msg_vec, entry["embedding"])
                scores.append((sim, name))
            scores.sort(reverse=True)
            floor = _similarity_floor()
            for sim, name in scores[:30]:
                if sim < floor:
                    continue
                phase = _infer_phase(name)
                emb_result.append({"name": name, "phase": phase, "_sim": sim})

    # 第三步：合并去重，按 _sim 降序排列（关键词命中 + 权重加分）
    keyword_names = {item["name"] for item in keyword_result}
    boost = _keyword_weight_boost()
    for item in emb_result:
        if item["name"] in keyword_names and "_sim" in item:
            item["_sim"] = min(item["_sim"] + boost, 1.0)
            item["_keyword_boosted"] = True

    seen: set = set()
    result: list = []

    for item in keyword_result:
        if item["name"] not in seen:
            seen.add(item["name"])
            result.append(item)

    for item in emb_result:
        if item["name"] not in seen:
            seen.add(item["name"])
            result.append(item)

    # 按 _sim 降序排序（有关键词加分的排在前面，纯关键词无 _sim 的自然靠后）
    result.sort(key=lambda x: x.get("_sim", 0.0), reverse=True)

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


def _auto_gen_a_rules() -> Dict[str, dict]:
    """从 _SKILL_INDEX 的 description 自动生成 A 层规则。

    不绑定特定 skill 集——每次启动根据当前 skill 重新生成。
    已有规则（用户手动添加的）不会被覆盖。
    """
    rules: Dict[str, dict] = {}
    for name, info in _SKILL_INDEX.items():
        desc = info.get("description", "")
        if not desc or len(desc) < 5:
            continue
        # 提取关键词：英文2+字母，中文2-4字
        import re as _re
        keywords: set = set()
        for word in desc.lower().replace(",", " ").replace("/", " ").split():
            word = word.strip('()[]{}."')
            if _re.match(r'^[a-z]{3,}$', word) and word not in (
                'the', 'and', 'use', 'for', 'this', 'that', 'with', 'when',
                'from', 'your', 'can', 'how', 'are', 'you', 'has', 'its',
                'all', 'not', 'but', 'get', 'any', 'was', 'one', 'out',
            ):
                keywords.add(word)
        for cw in _re.findall(r'[\u4e00-\u9fff]{2,4}', desc):
            keywords.add(cw)
        for kw in keywords:
            pattern = _re.escape(kw)
            rules[pattern] = {
                "skills": [name],
                "source": "auto-gen",
            }
    return rules


# ---------------------------------------------------------------------------
# Embedding 语义匹配
# ---------------------------------------------------------------------------

def _expand_chinese_query(text: str) -> str:
    """中文查询 → 追加英文领域关键词，提升 bge-m3 跨语言匹配精度。

    映射覆盖 bge-m3 已知盲区：金融、UI、调试、音乐、旅行等。
    """
    _CN_EN_MAP = [
        # (中文关键词列表, 英文扩展词)
        (["设计", "界面", "UI", "样式", "布局", "前端", "网页", "登录页", "仪表盘"],
         "design, UI, interface, frontend, layout, CSS"),
        (["调试", "报错", "错误", "修复", "bug", "异常", "不工作", "闪退", "卡顿", "KeyError", "Traceback", "TypeError", "AttributeError", "Exception", "崩溃"],
         "debug, error, diagnose, fix, troubleshoot"),
        (["金融", "股票", "交易", "均线", "MACD", "RSI", "KDJ", "茅台", "A股", "打板"],
         "finance, stock, trading, market, technical analysis"),
        (["论文", "学术", "写作", "研究", "文献", "期刊", "引用", "发表"],
         "academic, paper, research, writing, journal, citation"),
        (["旅行", "旅游", "出行", "攻略", "景点", "酒店", "自驾", "行程"],
         "travel, trip, itinerary, tour, hotel, road trip"),
        (["部署", "上线", "发布", "生产", "服务器", "运维", "CI", "CD"],
         "deploy, release, production, server, CI/CD, DevOps"),
        (["数据", "分析", "统计", "图表", "可视化", "报表", "Excel", "CSV"],
         "data analysis, statistics, visualization, chart, dashboard"),
        (["音乐", "音频", "歌曲", "播放", "乐器", "和弦", "旋律", "作曲"],
         "music, audio, song, composition, sound"),
        (["视频", "剪辑", "动画", "渲染", "字幕", "转码", "特效"],
         "video, animation, render, edit, media, encoding"),
        (["AI", "模型", "训练", "推理", "LLM", "GPT", "神经网络", "深度学习"],
         "AI, model, training, inference, LLM, machine learning, neural network"),
        (["API", "接口", "后端", "服务", "REST", "HTTP", "数据库", "SQL"],
         "API, backend, server, REST, HTTP, database, SQL"),
        (["安全", "加密", "认证", "权限", "防火墙", "漏洞", "攻击"],
         "security, encryption, authentication, firewall, vulnerability"),
        (["漫画", "插画", "绘画", "色彩", "像素", "ASCII", "艺术"],
         "art, illustration, drawing, pixel, ASCII, creative"),
        (["游戏", "玩法", "关卡", "角色", "RPG", "策略", "模拟"],
         "game, gameplay, design, level, character, RPG, simulation"),
    ]
    result = text
    for cn_keywords, en_expansion in _CN_EN_MAP:
        if any(kw in text for kw in cn_keywords):
            result += " " + en_expansion
    return result


def _cosine_sim(a, b):
    """余弦相似度"""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _embed(text):
    """多后端 embedding: ollama | siliconflow。失败降级返回 None。"""
    provider = _embed_provider()
    try:
        import httpx
        if provider == "ollama":
            from urllib.parse import urljoin
            url = urljoin(_ollama_url(), "/api/embeddings")
            resp = httpx.post(
                url,
                json={"model": _embed_model(), "prompt": text},
                timeout=_embed_timeout(),
            )
            resp.raise_for_status()
            return resp.json().get("embedding")
        elif provider == "siliconflow":
            key = _embed_api_key()
            if not key:
                logger.warning("[ssr] embedding siliconflow 无 api_key")
                return None
            base = _embed_base_url()
            url = base.rstrip("/") + "/embeddings"
            resp = httpx.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": _embed_model(), "input": text, "encoding_format": "float"},
                timeout=_embed_timeout(),
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [{}])[0].get("embedding")
        else:
            logger.warning("[ssr] embedding 后端 %s 未实现", provider)
            return None
    except Exception as e:
        logger.debug("[ssr] embedding 失败（%s）: %s", provider, e)
        return None


def _load_embedding_index():
    """从 embeddings.json 加载索引"""
    path = SSR_DIR / "embeddings.json"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("[ssr] embedding 索引加载失败: %s", e)
        return {}


def _save_embedding_index(index):
    """持久化 embedding 索引"""
    try:
        with open(SSR_DIR / "embeddings.json", "w") as f:
            json.dump(index, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("[ssr] embedding 索引保存失败: %s", e)



# 推荐结果缓存（session_id → formatted recommendation）
_POST_LLM_CACHE: Dict[str, str] = {}


def _post_llm_call(text: str, session_id: str = "", **kwargs) -> str:
    """post_llm_call hook: 将 SSR 推荐前置到回答开头。仅此一种模式——末尾模式会因长回复截断而丢失。"""
    if not session_id:
        return text
    rec = _POST_LLM_CACHE.pop(session_id, "")
    if not rec:
        return text
    return rec + "\n---\n" + text



def _build_embedding_index():
    """为所有 skill description 构建 embedding 索引。全量构建。"""
    index = {}
    total = len(_SKILL_INDEX)
    built = 0
    for name, info in _SKILL_INDEX.items():
        desc = info.get("description", "")
        if not desc or len(desc) < 5:
            continue
        vec = _embed(desc)
        if vec:
            index[name] = {"embedding": vec, "desc": desc}
            built += 1
            if built % 50 == 0:
                logger.info("[ssr] embedding 索引构建: %d/%d", built, total)
    _save_embedding_index(index)
    logger.info("[ssr] embedding 索引构建完成: %d skill", built)
    return index


def _sync_embeddings():
    """增量更新 embedding 索引。"""
    global _EMBEDDING_INDEX
    existing = _load_embedding_index()
    current = set(_SKILL_INDEX.keys())
    indexed = set(existing.keys())

    new_skills = current - indexed
    removed = indexed - current

    for name in removed:
        del existing[name]
    for name in new_skills:
        desc = _SKILL_INDEX[name].get("description", "")
        if not desc or len(desc) < 5:
            continue
        vec = _embed(desc)
        if vec:
            existing[name] = {"embedding": vec, "desc": desc}

    if new_skills or removed:
        _save_embedding_index(existing)
        logger.info("[ssr] embedding 增量: +%d -%d -> %d skill",
                     len(new_skills), len(removed), len(existing))

    _EMBEDDING_INDEX = existing


def _infer_phase(name):
    """从 skill description 推断执行阶段"""
    info = _SKILL_INDEX.get(name, {})
    desc = info.get("description", "").lower()
    if any(kw in desc for kw in ("review", "verify", "test", "check", "检查", "验证", "校验", "debug")):
        return "VERIFY"
    if any(kw in desc for kw in ("plan", "规划", "design", "架构", "blueprint", "spec")):
        return "PLAN"
    if any(kw in desc for kw in ("search", "调研", "research", "分析", "analyze", "explore", "browse")):
        return "DISCOVER"
    return "BUILD"


def _check_skills_changed() -> Optional[Tuple[set, set, set]]:
    """检测 skills 目录是否有新增/删除/description变更。返回 (new, removed, changed) 或 None。"""
    global _SKILLS_MTIME
    max_mtime = 0.0
    for base in (Path.home() / ".hermes" / "skills", Path.home() / ".agents" / "skills"):
        if not base.exists():
            continue
        try:
            mtime = max((p.stat().st_mtime for p in base.rglob("*") if p.is_file()), default=0)
            max_mtime = max(max_mtime, mtime)
        except Exception:
            continue

    if _SKILLS_MTIME == 0:
        _SKILLS_MTIME = max_mtime
        return None

    if max_mtime <= _SKILLS_MTIME:
        return None

    _SKILLS_MTIME = max_mtime
    current = set(_get_skills_list())
    indexed = set(_SKILL_INDEX.keys())
    new_skills = current - indexed
    removed = indexed - current

    # 检测 description 变更：existing skills whose description changed
    changed = set()
    for name in current & indexed:
        old_info = _SKILL_INDEX.get(name, {})
        old_desc = old_info.get("description", "")
        new_info = _get_skill_info(name)
        if new_info:
            new_desc = new_info.get("description", "")
            # 只要 description 变了（不是空→空），就算变更
            if new_desc and new_desc != old_desc:
                changed.add(name)
                # 同步更新内存中的索引
                _SKILL_INDEX[name] = {"description": new_desc, "category": new_info.get("category", "")}

    return (new_skills, removed, changed) if (new_skills or removed or changed) else None


def _hot_add_skill(name: str) -> bool:
    """热新增：单个 skill → embedding 追加索引。失败标记 _INDEX_DIRTY。"""
    global _INDEX_DIRTY
    info = _get_skill_info(name)
    if not info:
        return False
    desc = info.get("description", "")
    if not desc or len(desc) < 5:
        return False
    vec = _embed(desc)
    if not vec:
        return False
    _EMBEDDING_INDEX[name] = {"embedding": vec, "desc": desc}
    # 持久化
    try:
        idx = _load_embedding_index()
        idx[name] = {"embedding": vec, "desc": desc}
        _save_embedding_index(idx)
    except Exception:
        _INDEX_DIRTY = True
    return True


def _hot_remove_skill(name: str) -> bool:
    """热删除：从 embedding 索引移除单个 skill。"""
    global _INDEX_DIRTY
    if name not in _EMBEDDING_INDEX:
        return False
    del _EMBEDDING_INDEX[name]
    try:
        idx = _load_embedding_index()
        if name in idx:
            del idx[name]
            _save_embedding_index(idx)
    except Exception:
        _INDEX_DIRTY = True
    return True


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
    candidates = _prefilter_skills(user_message, max_candidates=_prefilter_candidates())
    if not candidates:
        candidates = list(_SKILL_INDEX.keys())[:_prefilter_candidates()]

    prompt = _build_b_prompt(user_message, candidates=candidates)
    provider = _b_provider()

    try:
        if provider == "ollama":
            result = _match_b_ollama(prompt)
        elif provider in ("openai", "lmstudio", "llamacpp"):
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

    return f"""你是一个技能匹配器。理解用户的任务意图，匹配所有明确相关的技能。不限数量。

可用技能（名称: 描述）：
{skill_list}

用户消息：「{user_message}」

返回 JSON:
{{"skills": ["技能名1", "技能名2"], "phases": ["DISCOVER|PLAN|BUILD|VERIFY", ...]}}

规则:
- skills: 不限数量，必须从上面的可用技能中选择，只选明确相关的
- phases: DISCOVER(调研/搜索) | PLAN(规划/设计) | BUILD(开发/实现) | VERIFY(测试/验证)
- 按 DISCOVER -> PLAN -> BUILD -> VERIFY 顺序排列
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
        f"{_b_base_url()}/chat/completions",
        json={
            "model": _b_model(),
            "messages": [
                {"role": "system", "content": f"你是技能匹配器。可用技能：\n{skill_list}"},
                {"role": "user", "content": f"根据\u300c{user_message}\u300d匹配技能，返回 JSON: {{\"skills\":[\"...\"],\"phases\":[\"...\"]}}"},
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
                {"role": "user", "content": f"根据\u300c{user_message}\u300d匹配技能，返回 JSON: {{\"skills\":[\"...\"],\"phases\":[\"...\"]}}"},
            ],
            "temperature": 0.1,
            "max_tokens": 500,
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
    """检测是否发生任务切换。显式关键词 + 模式变化检测。"""
    if TASK_SWITCH_PATTERNS.search(user_message):
        return True
    # 模式比较：当前模式 vs 上次，显著变化 → 任务切换
    current = _derive_pattern(user_message)
    last = _LAST_A_PATTERN.get(session_id, "")
    if last and current != last and len(user_message) < 20:
        return True
    return False


# A 层最后命中模式缓存，用于检测任务切换
_LAST_A_PATTERN: Dict[str, str] = {}

# 会话推荐计数：{session_id: {skill_name: (last_recommended_at, count)}}
_SESSION_REC_COUNT: Dict[str, Dict[str, Tuple[float, int]]] = {}

# 会话命中率统计：{session_id: {calls, hits_a, hits_b, misses, skipped_low_conf}}
_SESSION_STATS: Dict[str, Dict[str, int]] = {}
_STATS_LOG_INTERVAL = 10  # 每 N 次调用输出一次统计


def _log_session_stats(session_id: str) -> None:
    """输出会话命中率统计。"""
    stats = _SESSION_STATS.get(session_id)
    if not stats:
        return
    calls = stats.get("calls", 0)
    if calls < 1:
        return
    hits = stats.get("hits_a", 0) + stats.get("hits_b", 0)
    misses = stats.get("misses", 0)
    skipped = stats.get("skipped_low_conf", 0)
    hit_rate = (hits / calls * 100) if calls > 0 else 0
    logger.info(
        "[ssr] 会话统计 | session=%s | 调用=%d | A层命中=%d | B层命中=%d | "
        "无匹配=%d | 低置信跳过=%d | 命中率=%.0f%%",
        session_id[:16], calls, stats.get("hits_a", 0), stats.get("hits_b", 0),
        misses, skipped, hit_rate,
    )


def _format_recommendation(skills: List[dict]) -> str:
    """格式化推荐消息，按阶段分组。"""
    phase_emoji = {"DISCOVER": "[D]", "PLAN": "[P]", "BUILD": "[B]", "VERIFY": "[V]"}
    groups = {}
    for s in skills:
        phase = s.get("phase", "BUILD")
        if phase not in groups:
            groups[phase] = []
        name = s["name"]
        if s.get("shown_recently"):
            name = f"{name}(刚才)"
        groups[phase].append(name)
    lines = []
    max_display = _display_max()
    for phase in PHASE_ORDER:
        if phase not in groups:
            continue
        emoji = phase_emoji.get(phase, "")
        names = groups[phase]
        if max_display > 0 and len(names) > max_display:
            shown = names[:max_display]
            rest = len(names) - max_display
            lines.append(f"      {emoji} {phase}: {' | '.join(shown)} ...及 {rest} 个")
        else:
            lines.append(f"      {emoji} {phase}: {' | '.join(names)}")
    mode = _ssr_mode()
    prefix = "[MUST-LOAD]" if mode == "enforce" else "[SSR] 建议加载:"
    body = "\n".join(lines)
    if mode == "enforce":
        return f"{prefix} SSR 强制加载:\n{body}\n以上技能必须在此回复中使用 skill_view() 加载，不可跳过。"
    return f"{prefix}\n{body}"


def _compute_confidence(result: list) -> float:
    """计算整体匹配置信度：top-3 embedding 候选的平均相似度。

    如果全部是关键词命中（无 _sim 字段），置信度 = 1.0。
    """
    emb_sims = sorted(
        [s["_sim"] for s in result if "_sim" in s],
        reverse=True,
    )
    if not emb_sims:
        return 1.0  # 全部关键词命中 → 高置信
    top3 = emb_sims[:3]
    return sum(top3) / len(top3)


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
        # ── 会话统计 ──
        stats = _SESSION_STATS.setdefault(session_id, {
            "calls": 0, "hits_a": 0, "hits_b": 0, "misses": 0, "skipped_low_conf": 0,
        })
        stats["calls"] += 1

        # ── 每次提问扫描（如启用）──
        global _SKILL_INDEX, _INDEX_DIRTY
        if _scan_mode() == "every_turn":
            idx, broken = _build_skill_index()
            if idx:
                _SKILL_INDEX = idx

        # ── 文件监听 + 热更新（6.1 + 6.2）──
        if _INDEX_DIRTY:
            # 上次热更新失败 → 全量重建
            logger.info("[ssr] 检测到脏标记，全量重建 embedding 索引")
            _build_embedding_index()
            _INDEX_DIRTY = False
            _SKILLS_MTIME = 0  # 重置 mtime 以触发下次检测
        else:
            changes = _check_skills_changed()
            if changes:
                new_skills, removed_skills, changed_skills = changes
                for name in removed_skills:
                    _SKILL_INDEX.pop(name, None)
                    _hot_remove_skill(name)
                for name in new_skills:
                    info = _get_skill_info(name)
                    if info:
                        _SKILL_INDEX[name] = info
                    _hot_add_skill(name)
                for name in changed_skills:
                    # description 变更 → 重建此 skill 的 embedding
                    _hot_add_skill(name)
                if new_skills or removed_skills or changed_skills:
                    logger.info("[ssr] 热更新: +%d -%d Δ%d skill → 索引 %d",
                                len(new_skills), len(removed_skills),
                                len(changed_skills), len(_EMBEDDING_INDEX))

        # ── 增量自动同步（每隔 _AUTO_SYNC_INTERVAL 秒全量 sync） ──
        global _LAST_AUTO_SYNC
        now_sync = time.time()
        if _LAST_AUTO_SYNC == 0:
            _LAST_AUTO_SYNC = now_sync
        elif now_sync - _LAST_AUTO_SYNC >= _AUTO_SYNC_INTERVAL:
            # 每 10 分钟全量增量 sync：检测新增/删除/description 变更
            logger.info("[ssr] 增量自动同步触发（距上次 %.0f 秒）", now_sync - _LAST_AUTO_SYNC)
            try:
                _sync_embeddings()
                _LAST_AUTO_SYNC = now_sync
            except Exception as se:
                logger.warning("[ssr] 增量自动同步失败: %s", se)
                _INDEX_DIRTY = True

        # ── 任务切换检测 ──
        if _detect_task_switch(session_id, user_message):
            _SESSION_CACHE.pop(session_id, None)
            _SESSION_REC_COUNT.pop(session_id, None)
            _COOLDOWN_TRACKER.pop(session_id, None)
            _LAST_A_PATTERN.pop(session_id, None)
            logger.debug("[ssr] 检测到任务切换，清除会话缓存+冷却追踪")
        _LAST_A_PATTERN[session_id] = _derive_pattern(user_message)

        # ── A 层匹配 ──
        result = _match_a_layer(user_message)
        if result:
            # 智能冷却制：自适应冷却（已加载×3、反复推荐未加载×0.5、紧急×0.5）
            rec_count = _SESSION_REC_COUNT.setdefault(session_id, {})
            now = time.time()
            fresh = []
            for s in result:
                name = s["name"]
                cooldown = _smart_cooldown(session_id, name, s.get("phase", "BUILD"), user_message)
                if cooldown < 0:
                    # 返回 -1 → 用户明确不需要，跳过此 skill
                    continue
                if name in rec_count:
                    last_t, _ = rec_count[name]
                    if now - last_t < cooldown:
                        continue  # 仍在冷却期内，跳过此 skill
                rec_count[name] = (now, rec_count.get(name, (0, 0))[1] + 1)
                fresh.append(s)
            # 按阶段排序
            fresh.sort(key=lambda x: PHASE_ORDER.index(x["phase"]) if x["phase"] in PHASE_ORDER else 99)
            # 截断：按阶段排序后取 top N（冷却期内已跳过，无需 shown_recently 排序）
            max_total = _max_total_recommendations()
            if max_total > 0 and len(fresh) > max_total:
                fresh = fresh[:max_total]
                # 恢复阶段排序
                fresh.sort(key=lambda x: PHASE_ORDER.index(x["phase"]) if x["phase"] in PHASE_ORDER else 99)
            conf = _compute_confidence(fresh)
            threshold = _confidence_threshold()
            if conf < threshold:
                stats["skipped_low_conf"] += 1
                logger.info("[ssr] A 层置信度不足 (%.3f < %.2f)，跳过推荐", conf, threshold)
                return None
            rec = _format_recommendation(fresh)
            if rec and session_id:
                _POST_LLM_CACHE[session_id] = rec
            stats["hits_a"] += 1
            if stats["calls"] % _STATS_LOG_INTERVAL == 0:
                _log_session_stats(session_id)
            logger.info("[ssr] A 层命中: %s", [s["name"] for s in fresh])
            return {"context": rec}

        # ── B 层匹配 ──
        result = _match_b_layer(user_message)
        if not result:
            stats["misses"] += 1
            logger.info("[ssr] 无匹配（A层 %d 条 + B层 %s, 本轮第 %d 次）",
                        len(_A_RULES), _b_provider(), stats["calls"])
            return None

        # 智能冷却制：自适应冷却（已加载×3、反复推荐未加载×0.5、紧急×0.5）
        rec_count = _SESSION_REC_COUNT.setdefault(session_id, {})
        now = time.time()
        fresh = []
        for s in result:
            name = s["name"]
            cooldown = _smart_cooldown(session_id, name, s.get("phase", "BUILD"), user_message)
            if cooldown < 0:
                # 返回 -1 → 用户明确不需要，跳过此 skill
                continue
            if name in rec_count:
                last_t, _ = rec_count[name]
                if now - last_t < cooldown:
                    continue  # 仍在冷却期内，跳过此 skill
            rec_count[name] = (now, rec_count.get(name, (0, 0))[1] + 1)
            fresh.append(s)

        # 按阶段排序
        fresh.sort(key=lambda x: PHASE_ORDER.index(x["phase"]) if x["phase"] in PHASE_ORDER else 99)
        # 截断：按阶段排序后取 top N（冷却期内已跳过，无需 shown_recently 排序）
        max_total = _max_total_recommendations()
        if max_total > 0 and len(fresh) > max_total:
            fresh = fresh[:max_total]
            # 恢复阶段排序
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

        conf = _compute_confidence(fresh)
        threshold = _confidence_threshold()
        if conf < threshold:
            stats["skipped_low_conf"] += 1
            logger.info("[ssr] B 层置信度不足 (%.3f < %.2f)，跳过推荐", conf, threshold)
            return None
        rec = _format_recommendation(fresh)
        if rec and session_id:
            _POST_LLM_CACHE[session_id] = rec
        stats["hits_b"] += 1
        if stats["calls"] % _STATS_LOG_INTERVAL == 0:
            _log_session_stats(session_id)
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
    global _SKILL_INDEX, _BROKEN_SKILLS, _A_RULES, _EMBEDDING_INDEX

    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("post_llm_call", _post_llm_call)

    # 启动时构建索引
    try:
        _SKILL_INDEX, _BROKEN_SKILLS = _build_skill_index()
    except Exception as e:
        logger.warning("[ssr] 索引构建失败: %s", e)

    # 加载 A 层规则 + 清理过期 + 清理单英文词
    _A_RULES = _load_a_rules()
    logger.info("[ssr] 加载 A 层规则: %d 条", len(_A_RULES))
    _cleanup_a_rules()
    logger.info("[ssr] 清理后 A 层规则: %d 条", len(_A_RULES))

    # 自动生成 A 层规则（基于本地 skill description，不绑定特定 skill 集）
    added = 0
    if _auto_gen_enabled():
        auto_gen = _auto_gen_a_rules()
        for k, v in auto_gen.items():
            if k not in _A_RULES:
                _A_RULES[k] = v
                added += 1
        # 不覆盖已有规则——B 层升级的规则优先级更高
        _save_a_rules(_A_RULES)
        logger.info("[ssr] auto-gen: +%d 条 → A 层共 %d 条", added, len(_A_RULES))
    else:
        logger.info("[ssr] auto-gen 已关闭（ssr.auto_gen_rules: false）")

    # Phase 2: Embedding 索引构建
    emb_count = 0
    try:
        existing = _load_embedding_index()
        if existing:
            _EMBEDDING_INDEX = existing
            _sync_embeddings()
            emb_count = len(_EMBEDDING_INDEX)
            logger.info("[ssr] embedding 索引: %d skill（增量同步）", emb_count)
        else:
            logger.info("[ssr] embedding 索引首次构建中...")
            _EMBEDDING_INDEX = _build_embedding_index()
            emb_count = len(_EMBEDDING_INDEX)
            logger.info("[ssr] embedding 索引构建完成: %d skill", emb_count)
    except Exception as e:
        logger.warning("[ssr] embedding 索引失败（降级关键词匹配）: %s", e)
        _EMBEDDING_INDEX = {}

    logger.info("[ssr] 插件注册完成 | skill: %d | 残骸: %d | A层: %d+%d | emb: %d | B层: %s",
                len(_SKILL_INDEX), len(_BROKEN_SKILLS),
                len(_A_RULES) - added, added,
                emb_count, _b_provider())

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

    # 残骸报告
    if _BROKEN_SKILLS:
        logger.warning(
            "[ssr] 检测到 %d 个残骸 skill: %s",
            len(_BROKEN_SKILLS),
            ", ".join(_BROKEN_SKILLS[:10]),
        )
