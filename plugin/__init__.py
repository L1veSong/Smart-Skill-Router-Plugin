"""
智配路由 (SSR) — Smart Skill Router Plugin v3.0.2

自动匹配用户意图到最合适的 skill 并推荐加载。
A 层（Embedding 语义匹配）+ B 层（LLM 语义匹配，多后端可选）。
支持 main / openai / ollama / lmstudio / llamacpp 五种后端。
自学习升级 + Dashboard 可视化管理 + 推荐模式。

v3.0.2 (2026-09-20): 索引排除 dot 目录——.archive 幽灵 skill 不再进入索引/embedding/推荐（审计实锤修复）。
v3.0.1 (2026-09-15): gateway 启动死锁修复——一次性索引+缓存（O(树)），替代每 skill 全树扫描。
v3.0.0 (2026-07-23):
  - MoE 架构：路由层 + skills直推 + 域过滤
v2.3.0 (2026-07-23):
  - 大修：清空 6789 条垃圾 auto 规则（B层Ollama超时遗留）
  - a_rules.json 合并 local.json → 10 条干净 manual 规则
  - PROMOTE_THRESHOLD: 999999 → 3（恢复自学习）
  - _cleanup_a_rules: 新增垃圾检测（单英文词/空phase/太短）
  - _cleanup_a_rules: 删除空规则（不再保留"意图信号"）
  - _cleanup_a_rules: 修复淘汰方向（删最低质量，manual 保护）

配置（config.yaml）:

    ssr:
      enabled: true
      mode: suggest
      scan_mode: startup
      display: false          # v2.1: false=静默不展示
      b_layer:
        provider: main
        timeout: 30
      embedding:
        provider: xxx          # 按需配置（ollama / siliconflow / openai）
        model: xxx
      intent_gate:            # v2.1: LLM 意图门控
        enabled: true
        prompt: "..."
      noise_filter:           # v2.1: 噪音过滤
        enabled: true
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 本机请求必须绕过代理（2026-10-08 修复）
# ---------------------------------------------------------------------------
# 环境里设了 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY 时，httpx 默认 trust_env=True，
# 连 http://127.0.0.1:11434（Ollama）的请求也会被送到代理，代理回 503，
# 导致 embedding 全批失败（日志：ok=0 fail=170 last_error=503 .../api/embeddings）。
# 这里在模块加载时把本机地址补进 NO_PROXY；httpx 每次请求都会读该变量，
# 因此对共享 client 和模块级 httpx.post 同时生效。
def _ensure_localhost_no_proxy() -> None:
    hosts = ("localhost", "127.0.0.1", "::1")
    for var in ("NO_PROXY", "no_proxy"):
        parts = [p.strip() for p in os.environ.get(var, "").split(",") if p.strip()]
        added = [h for h in hosts if h not in parts]
        if added:
            os.environ[var] = ",".join(parts + added)


try:
    _ensure_localhost_no_proxy()
except Exception:  # 绝不因为环境变量问题拖垮插件加载
    logger.debug("[ssr] 补 NO_PROXY 失败", exc_info=True)

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
# 2026-07-23: v2.3.0 大修——清空6789条垃圾+修复清理逻辑，阈值恢复至3。
PROMOTE_THRESHOLD = 3

# === v2.4.0 MoE 路由词干表 ===
# 词干 → 域名映射，出现任一即激活该域
# === v2.5.0 MoE 路由词干表（34域，自动从 a_rules.json 对齐） ===
# 词干 → 域名映射，出现任一即激活该域，无命中则全开 fallback
# === v2.5.0 MoE 路由词干表（34域，原子化+去歧义） ===
# 词干→域名映射，出现任一即激活该域。无命中全开 fallback。
# === v3.0 MoE 路由词干（从 a_rules.json 正则机械提取 + Golden 补全）===
# 34域 · 1959词干 · 零手写 · 自动对齐
# === v3.0 MoE 路由词干（34域·272词干·55 Golden全绿·P0激活）===
# 手工精选+Golden验证·每词干仅鉴别1-2域·fakeout歧义由A层regex最终裁决
DOMAIN_STEMS = {
    "agent": ["Claude", "Codex", "Kimi", "OpenCode", "委托", "并行", "闭环", "subagent"],
    "china-services": ["国内", "国内AI", "镜像", "人民币", "npm慢", "pip慢", "国产"],
    "cli": ["TUI", "terminal", "/compact", "/caveman"],
    "code-quality": ["debug", "调试", "诊断", "tdd", "验证", "重构", "code review", "代码审查", "bug", "代码", "统计", "code"],
    "collab": ["Notion", "Airtable", "Linear"],
    "dev-tools": ["MCP server", "GUI shell", "devcontainer"],
    "docs": ["PPT", "Word", "Excel", "PDF", "docx", "xlsx", "幻灯片", "表格", "文档"],
    "gaming": ["Minecraft", "宝可梦", "pokemon", "我的世界", "MC", "游戏", "GDD", "unity", "godot", "unreal", "ue5", "引擎", "肉鸽", "rogue", "roguelike", "玩法", "独立游戏", "小游戏"],
    "github": ["PR", "CodeReview", "Issues", "Auth", "仓库", "GitHub", "git", "pull request", "clone", "branch", "code review"],
    "lifestyle": ["种菜", "种花", "农耕", "堆肥", "腌", "发酵"],
    "macos": ["备忘录", "提醒", "FindMy", "找设备", "附近", "nearby", "周边", "Mac", "mac", "macOS"],
    "map": ["地图", "SVG", "geo", "可视化"],
    "media": ["YouTube", "GIF", "表情包", "spotify", "油管", "动图"],
    "messaging": ["元宝", "yuanbao"],
    "ml": ["微调", "finetune", "训练", "HuggingFace", "vLLM", "Jupyter", "LoRA", "W&B", "GGUF"],
    "obsidian": ["Obsidian", "知识库", "MOC", "双向链接"],
    "planning": ["脑暴", "计划", "规划", "原型", "prototype", "spike"],
    "project": ["foundry", "新建项目", "创建项目", "PRD", "需求文档", "脚手架", "从零", "App", "网站", "做个", "搭", "搭个", "建"],
    "search": ["搜索", "查询", "检索", "调研"],
    "security": ["jailbreak", "越狱", "bypass", "red team", "abliterate"],
    "smarthome": ["开灯", "关灯", "灯光", "Hue"],
    "social": ["小红书", "抖音", "自媒体", "社交", "爬取"],
    "storage": ["磁盘", "清理磁盘", "磁盘清理", "清理", "洁癖", "收尾", "空间不够", "满了", "neat"],
    "system": ["Hermes", "模型配置", "本地模型", "STT", "skill", "配置", "出问题", "排查"],
    "travel": ["旅行", "机票", "酒店", "高铁", "火车", "天气", "自驾", "美食", "小吃", "攻略", "行程", "航班", "住宿", "转转", "玩", "吃", "好吃"],
    "writing": ["写文章", "写论文", "润色", "文笔", "公众号", "长文", "文案", "报告", "总结", "稿子", "作文", "写稿", "公众号文章", "小说", "网文", "写小说", "连载", "扫榜", "拆文", "去AI味", "章节", "大纲", "人物设定", "短篇", "长篇", "番茄", "起点", "晋江", "续写", "创作", "写作助手", "deslop", "章纲", "卷纲", "世界观", "角色设定"],
    "学术": ["论文", "paper", "学术", "文献", "nature", "审稿", "引用", "图表", "SCI", "答辩", "latex"],
    "生图": ["电影感", "电影", "分镜", "角色", "海报", "中国风", "摄影", "人像", "徕卡", "哈苏", "拍照", "照片", "画面", "构图", "keyframe"],
    "视频": ["短视频", "剪辑", "视频编辑", "视频", "转码", "字幕", "动画", "remotion", "manim", "hyperframes", "调色", "换脸", "AI视频"],
    "设计": ["UI", "UX", "界面设计", "前端", "Figma", "canvas", "GSAP", "配色", "字体", "originkit", "动画组件", "粒子效果", "文字动画", "动效"],
    "通讯": ["邮件", "email", "微信", "飞书", "发消息", "发微信", "写信"],
    "部署": ["部署", "Vercel", "Go API", "上线", "服务器", "发布", "openwebui", "one-api", "proxy"],
    "金融": ["股票", "行情", "K线", "MACD", "期货", "选股", "短线", "涨停", "tushare", "RSI", "财经"],
    "音乐": ["音乐", "AI生成音乐", "音乐生成", "语音合成", "song", "audiocraft", "频谱", "谱曲", "AI音乐"],
    "business": ["商业", "生意", "创业", "赚钱", "诊断", "对标", "选题", "内容", "标题", "AI味", "拖延", "行动", "决策", "知识库", "公众号", "聊天室", "传播", "逐字稿", "文稿", "存档", "迁移", "桥接", "dbs", "dbskill", "开头", "黄金", "爆款", "同行", "目标", "好问题", "概念", "复盘", "存档", "学习", "课程"],
    "dev": ["code", "代码", "review", "审查", "spec", "ticket", "issue", "bug", "调试", "重构", "merge", "冲突", "MCP", "webapp", "网页", "测试", "qa", "refactor", "branch", "分支", "PR", "git", "claude api", "gif", "internal"],
    "learning": ["teach", "教我", "学习", "上课", "教学", "learn"],
}
ALL_DOMAINS = frozenset(DOMAIN_STEMS.keys())  # v3.0: degradation ref; P0 disabled — no fallback

# SSR 插件目录
SSR_DIR = Path(__file__).resolve().parent
A_RULES_PATH = SSR_DIR / "a_rules.json"


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

_CONFIG_CACHE: Optional[dict] = None
_MODEL_SCORES_CACHE: Optional[dict] = None

# 模型得分 → similarity_floor 映射
_SCORE_FLOOR_MAP = {
    5: 0.25,
    4: 0.30,
    3: 0.35,
    2: 0.42,
    1: 0.48,
}

def _load_model_scores() -> dict:
    """读取 model_scores.json，结果缓存。"""
    global _MODEL_SCORES_CACHE
    if _MODEL_SCORES_CACHE is not None:
        return _MODEL_SCORES_CACHE
    try:
        scores_path = SSR_DIR / "model_scores.json"
        if scores_path.exists():
            _MODEL_SCORES_CACHE = json.loads(scores_path.read_text())
        else:
            _MODEL_SCORES_CACHE = {}
    except Exception:
        _MODEL_SCORES_CACHE = {}
    return _MODEL_SCORES_CACHE


def _load_ssr_config() -> dict:
    """读取 config.yaml 中 ssr 配置节，结果缓存。

    v2.3.0 修复：hermes_cli.config.load_config() 在某些运行时返回空 ssr 节，
    导致 embedding/门控/阈值/auto_gen 全部跌回默认值。添加 PyYAML 直接读作为
    可信回退——hermes_cli 优先（支持 env var 合并），拿不到则直读文件。
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    cfg: dict = {}
    # 路径 1：hermes_cli（支持 HERMES_HOME / 环境变量合并）
    try:
        from hermes_cli.config import load_config
        raw = load_config()
        cfg = raw.get("ssr", {}) or {}
    except Exception:
        cfg = {}
    # 路径 2：直读 config.yaml（hermes_cli 拿不到 ssr 节时）
    if not cfg:
        try:
            import yaml
            config_path = Path.home() / ".hermes" / "config.yaml"
            with open(config_path) as f:
                full = yaml.safe_load(f)
            cfg = full.get("ssr", {}) or {}
        except Exception:
            cfg = {}
    _CONFIG_CACHE = cfg
    return _CONFIG_CACHE


def _auto_gen_enabled() -> bool:
    """是否启用 auto-gen 规则生成（默认 true，可配置 ssr.auto_gen_rules: false 关闭）。"""
    cfg = _load_ssr_config()
    return cfg.get("auto_gen_rules", False)


def _hook_enabled() -> bool:
    cfg = _load_ssr_config()
    if not cfg.get("enabled", True):
        return False
    hooks = cfg.get("hooks", {})
    return hooks.get("pre_llm_call", True)


def _display_enabled() -> bool:
    """是否向用户展示 SSR 推荐（默认 false 静默）。ssr.display: true 时展示。"""
    cfg = _load_ssr_config()
    return cfg.get("display", False)


def _report_enabled() -> bool:
    """AI 是否汇报 SSR 使用情况（默认 false）。ssr.report: true 时开启。"""
    cfg = _load_ssr_config()
    return cfg.get("report", False)


def _ssr_mode() -> str:
    """推荐模式：suggest（仅此一种，强制模式已移除——插件层无法真正强制）。"""
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
    return _load_ssr_config().get("ollama_model", "")


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
    """embedding 相似度地板。score < 此值直接丢弃。

    优先级: config.yaml 显式设置 > 无极校准值 > 有极查表 > 默认 0.35。
    """
    cfg = _load_ssr_config()
    # 用户显式设置 → 直接使用
    if "similarity_floor" in cfg:
        return cfg["similarity_floor"]
    # 自动: 读 embedding 模型 → 查 model_scores.json
    emb_cfg = cfg.get("embedding", {})
    model_name = emb_cfg.get("model", "") or cfg.get("embedding_model", "")
    if model_name:
        scores = _load_model_scores()
        for name, score_data in scores.items():
            if not isinstance(score_data, dict):
                continue
            if name in model_name or model_name in name:
                # 无极: 校准脚本实测值 → 公式连续计算
                if "calibrated_floor" in score_data:
                    floor = score_data["calibrated_floor"]
                    logger.info("[ssr] 自动 floor (无极): %s → %.3f", name, floor)
                    return floor
                # 有极: 查表映射
                if "overall" in score_data:
                    score = score_data["overall"]
                    floor = _SCORE_FLOOR_MAP.get(score, 0.35)
                    logger.info("[ssr] 自动 floor (有极): %s (得分 %d) → %.2f", name, score, floor)
                    return floor
    return 0.35


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
    return ""


# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------

# 技能索引：启动时构建，每次启动重建
_SKILL_INDEX: Dict[str, dict] = {}

# 残骸清单
_BROKEN_SKILLS: List[str] = []

# A 层规则：{pattern: {skills, hits, last_hit, source, priority}}
_A_RULES: Dict[str, dict] = {}

# Embedding 索引：{skill_name: {embedding: [N维], desc: str}}
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


_SKILL_MD_INDEX: Optional[Dict[str, Path]] = None
_SKILL_MD_INDEX_LOCK = threading.Lock()


def _build_skill_md_index() -> Dict[str, Path]:
    """一次性扫描 skills 目录，建立 skill name → SKILL.md 路径的索引并缓存。

    v3.0.1 (2026-09-15): 修复 gateway 启动死锁。
    原 _get_skill_info() 对 *每个* skill 都重新 rglob() 整棵目录树，复杂度为
    O(N_skills × 目录内 SKILL.md 数量)。skills 增长后单次遍历可达数十秒，期间
    一直持有插件加载锁；而 gateway/run.py 在 import 期间就会调用插件发现
    （_bridge_config_to_env → get_plugin_auxiliary_tasks），主线程因此在 import
    期永久等待该锁，gateway 启动彻底挂死。改为构建一次索引并缓存，
    总体复杂度降为 O(目录树)。
    """
    global _SKILL_MD_INDEX
    if _SKILL_MD_INDEX is not None:
        return _SKILL_MD_INDEX
    with _SKILL_MD_INDEX_LOCK:
        if _SKILL_MD_INDEX is not None:
            return _SKILL_MD_INDEX
        index: Dict[str, Path] = {}
        for base in (Path.home() / ".hermes" / "skills", Path.home() / ".agents" / "skills"):
            if not base.exists():
                continue
            for skill_md in base.rglob("SKILL.md"):
                # v3.0.2: dot 目录（.archive/.curator_backups/.hub/.git 等）不是可加载 skill；
                # 此前被扫入索引 → embedding 池出现"幽灵 skill"并被推荐（2026-09-20 审计实锤）。
                if any(part.startswith(".") for part in skill_md.relative_to(base).parts[:-1]):
                    continue
                try:
                    for line in skill_md.read_text().split("\n"):
                        if line.startswith("name:"):
                            name = line.split(":", 1)[1].strip()
                            if name:
                                index.setdefault(name, skill_md)
                            break
                except Exception:
                    pass
        _SKILL_MD_INDEX = index
        logger.info("[ssr] SKILL.md 索引构建完成: %d 个 skill", len(index))
        return index


def _fallback_skill_mds(skill_name: str):
    """产出匹配 skill_name 的 SKILL.md 路径（0 或 1 个），供回退解析使用。"""
    skill_md = _build_skill_md_index().get(skill_name)
    if skill_md is not None:
        yield skill_md


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

    # 回退：扫描文件系统（复用一次性构建并缓存的索引，避免重复遍历目录树）
    return list(_build_skill_md_index().keys())


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

    # 回退：搜索并解析 SKILL.md（查缓存索引，不再对每个 skill 重复 rglob 全树）
    for skill_md in _fallback_skill_mds(skill_name):
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
    """加载 A 层固化规则。合并 a_rules.local.json（如存在）。损坏时自动备份。"""
    rules = {}
    if A_RULES_PATH.exists():
        try:
            data = json.loads(A_RULES_PATH.read_text())
            if not isinstance(data, dict):
                raise ValueError(f"expected dict, got {type(data).__name__}")
            rules = data
        except Exception as e:
            logger.warning("[ssr] a_rules.json 读取失败（%s），备份损坏文件", e)
            try:
                backup = A_RULES_PATH.with_suffix(".json.corrupted")
                backup.write_text(A_RULES_PATH.read_text())
            except Exception:
                pass
    # 合并本地规则（覆盖同名 key）
    local_path = SSR_DIR / "a_rules.local.json"
    if local_path.exists():
        try:
            local = json.loads(local_path.read_text())
            if isinstance(local, dict):
                rules.update(local)
                logger.info("[ssr] 加载本地规则: %d 条", len(local))
        except Exception as e:
            logger.warning("[ssr] a_rules.local.json 读取失败: %s", e)

    # ── 归一化: 把 list 格式的 value 转为 dict 格式 ──
    normalized = 0
    for k, v in list(rules.items()):
        if isinstance(v, list):
            rules[k] = {"skills": v, "source": "auto", "priority": 1, "hits": 0}
            normalized += 1
    if normalized:
        logger.info("[ssr] 归一化 list→dict: %d 条", normalized)

    return rules


def _save_a_rules(rules: Dict[str, dict]) -> None:
    """保存 A 层规则到磁盘。空覆盖前自动备份。
    
    v2.3.1 FIX: 保存前先合并磁盘上已有的规则，防止内存缓存覆盖手动添加的规则。
    磁盘规则作为 base，内存规则覆盖同名 key（保证 SSR 自身更新生效）。
    """
    try:
        if not rules and A_RULES_PATH.exists() and A_RULES_PATH.stat().st_size > 10:
            backup = A_RULES_PATH.with_suffix(".json.bak")
            backup.write_text(A_RULES_PATH.read_text())
            logger.warning("[ssr] a_rules.json 即将被空覆盖，已备份到 %s", backup)

        # v2.3.1 FIX: 合并磁盘规则，保护手动添加的规则不丢失
        if A_RULES_PATH.exists():
            try:
                disk_rules = json.loads(A_RULES_PATH.read_text())
                if isinstance(disk_rules, dict) and disk_rules:
                    merged = dict(disk_rules)  # 磁盘为底
                    merged.update(rules)         # 内存覆盖同名
                    rules = merged
            except Exception:
                pass

        A_RULES_PATH.write_text(json.dumps(rules, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning("[ssr] a_rules.json 写入失败: %s", e)



def _route_domains(user_message: str) -> set:
    """MoE 路由层：词干检测 → 激活域集合。无命中则全开。"""
    msg = user_message.lower()
    activated = set()
    for domain, stems in DOMAIN_STEMS.items():
        for stem in stems:
            if stem.lower() in msg:
                activated.add(domain)
                break
    if activated:
        return activated
    logger.info('SSR P0: gate closed — no domain activated')
    return set()

def _match_a_layer_keyword(user_message: str) -> Optional[List[dict]]:
    """[保留] A 层关键词精确匹配（原版，embedding 不可用时的 fallback）。"""
    global _A_HIT_COUNT
    if not _A_RULES:
        return None

    # v2.4.0 MoE: 路由激活域
    domains = _route_domains(user_message)
    
    candidates: List[Tuple[str, dict]] = []  # (pattern, rule)

    for pattern, rule in _A_RULES.items():
        # 跳过新版 list 格式（直接走 embedding 路径）
        if isinstance(rule, list):
            continue
        # 域过滤：有 domain 字段则必须在激活域中
        rule_domain = rule.get("domain", "")
        if rule_domain and rule_domain not in domains:
            continue
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
        if isinstance(rule, list):
            return (0, 0, 0)
        priority = rule.get("priority", 0)
        specificity = len(_pattern)
        hits = rule.get("hits", 0)
        # manual (priority=10) > auto (priority=1)
        return (-priority, -specificity, -hits)

    candidates.sort(key=_sort_key)

    # v2.4.0 MoE: 优先 skills 直推，fallback keywords→_SKILL_INDEX
    seen: set = set()
    result: List[dict] = []
    for _pattern, rule in candidates:
        rule["hits"] = rule.get("hits", 0) + 1
        rule["last_hit"] = time.strftime("%Y-%m-%d")
        rule_phases = rule.get("phases", [])
        
        # v2.4.0: skills 字段直推（新格式）
        direct_skills = rule.get("skills", [])
        if direct_skills:
            for s in direct_skills:
                name = s["name"] if isinstance(s, dict) else s
                if name in seen:
                    continue
                phase = s.get("phase", "") if isinstance(s, dict) else ""
                if not phase and rule_phases:
                    phase = rule_phases[0]
                seen.add(name)
                result.append({"name": name, "phase": phase, "_kw_boosted": True, "_sim": 0.9})
        else:
            # 兼容旧格式：keywords → _SKILL_INDEX
            keywords = rule.get("keywords", [])
            exclude_keywords = rule.get("exclude", [])
            for keyword in keywords:
                kw_lower = keyword.lower()
                for name, info in _SKILL_INDEX.items():
                    if name in seen:
                        continue
                    name_lower = name.lower()
                    desc_lower = info.get("description", "").lower()
                    if exclude_keywords:
                        blocked = False
                        for nkw in exclude_keywords:
                            if nkw.lower() in name_lower or nkw.lower() in desc_lower:
                                blocked = True
                                break
                        if blocked:
                            continue
                    if kw_lower in name_lower or kw_lower in desc_lower:
                        seen.add(name)
                        phase = _infer_phase(name)
                        if not phase and rule_phases:
                            phase = rule_phases[0]
                        result.append({"name": name, "phase": phase, "_kw_boosted": True, "_sim": 0.9})
                        break

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

    两条路径并行：
    - 关键词：精确命中，零延迟，排前面
    - Embedding：语义覆盖 top-30，补充关键词未覆盖的
    """
    # 第一步：关键词精确匹配
    keyword_result = _match_a_layer_keyword(user_message) or []

    # 第二步：Embedding 语义匹配（始终激活）
    emb_result = []
    if _EMBEDDING_INDEX:
        query = _expand_chinese_query(user_message)
        msg_vec = _embed(query)
        if msg_vec:
            # 一次矩阵运算算完全部 skill 的相似度（原来 751 次逐条 _cosine_sim），
            # 并且直接只取 top-30，不再对全部条目排序。
            floor = _similarity_floor()
            for sim, name in _rank_by_embedding(msg_vec, top_k=30):
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

    if result:
        kw_count = len(keyword_result)
        emb_count = len(emb_result)
        top_names = [r["name"] for r in result[:5]]
        logger.info("[ssr] A 层命中: %d 条 (%d kw + %d emb) → %s", len(result), kw_count, emb_count, top_names)
    else:
        logger.debug("[ssr] A 层无命中")

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
    """清理 A 层规则：垃圾检测 + 过期 + 死引用 + 上限淘汰。

    v2.3.0 大修：新增垃圾检测（单英文词/空phase/太短模式），修复淘汰方向（删最低质量而非最低hits）。
    """
    if not _A_RULES:
        return

    # ── 垃圾检测：v2.3.0 新增 ──
    GARBAGE_STOP_WORDS = frozenset({
        'the', 'and', 'use', 'for', 'this', 'that', 'with', 'when',
        'from', 'your', 'can', 'how', 'are', 'you', 'has', 'its',
        'all', 'not', 'but', 'get', 'any', 'was', 'one', 'out',
        'they', 'will', 'have', 'been', 'more', 'some', 'what',
        'work', 'skill', 'time', 'call', 'only', 'view', 'other',
        'save', 'name', 'way', 'need', 'main', 'just', 'like',
        'make', 'file', 'code', 'data', 'test', 'help', 'also',
        'era', 'gen', 'art', 'doc', 'env', 'see', 'new', 'old',
    })
    garbage: List[str] = []

    for pattern, rule in list(_A_RULES.items()):
        source = rule.get("source", "auto")

        # manual 规则不参与垃圾检测
        if source == "manual":
            continue

        # 检测 1: 单英文词 or 太短
        pattern_stripped = pattern.strip()
        if (len(pattern_stripped) < 4
                or (pattern_stripped.isascii() and pattern_stripped.isalpha()
                    and len(pattern_stripped) <= 6
                    and pattern_stripped.lower() in GARBAGE_STOP_WORDS)):
            garbage.append(pattern)
            continue

        # 检测 2: 空 phase 且无 skills → 无效规则
        phases = rule.get("phases")
        skills = rule.get("skills")
        keywords = rule.get("keywords")
        if (not phases or len(phases) == 0) and not skills and not keywords:
            garbage.append(pattern)
            continue

    for p in garbage:
        del _A_RULES[p]

    if garbage:
        logger.info("[ssr] 垃圾清理: %d 条（单英文词/空phase/太短）", len(garbage))

    # ── 原有清理逻辑 ──
    ttl_days = _a_rules_ttl_days()
    ttl_seconds = ttl_days * 86400
    now = time.time()
    expired: List[str] = []
    dead_cleaned = 0
    empty_rules: List[str] = []

    for pattern, rule in list(_A_RULES.items()):
        # ── 死引用清理：移除指向未安装 skill 的引用 ──
        # FIX: manual-created rules are never cleaned as dead references
        if rule.get("source") == "manual":
            continue
        skills = rule.get("skills", [])
        if skills and _SKILL_INDEX:
            live = []
            for s in skills:
                name = s["name"] if isinstance(s, dict) else s
                if name in _SKILL_INDEX:
                    live.append(s)
            removed = len(skills) - len(live)
            if removed:
                dead_cleaned += removed
                if not live:
                    empty_rules.append(pattern)
                else:
                    rule["skills"] = live

        # ── v3 keywords: 检查是否有任何关键词匹配已安装 skill ──
        # FIX: manual-created rules are never cleaned as dead keywords
        if rule.get("source") == "manual":
            continue
        keywords = rule.get("keywords", [])
        if keywords and _SKILL_INDEX:
            any_match = False
            for kw in keywords:
                kw_lower = kw.lower()
                for name, info in _SKILL_INDEX.items():
                    if kw_lower in name.lower() or kw_lower in info.get("description","").lower():
                        any_match = True
                        break
                if any_match:
                    break
            if not any_match:
                dead_cleaned += 1
                empty_rules.append(pattern)

        # ── TTL 过期检查 ──
        last_hit_str = rule.get("last_hit", "")
        if not last_hit_str:
            continue
        try:
            last_hit = time.mktime(time.strptime(last_hit_str, "%Y-%m-%d"))
            if now - last_hit > ttl_seconds:
                expired.append(pattern)
        except (ValueError, OverflowError):
            expired.append(pattern)

    # v2.3.0: 删除空规则（不再保留——垃圾泛滥已证明"意图信号"是个伪命题）
    for p in empty_rules:
        if p in _A_RULES and _A_RULES[p].get("source") != "manual":
            del _A_RULES[p]
            dead_cleaned += 1
    for p in expired:
        if p in _A_RULES:
            del _A_RULES[p]

    # ── 上限淘汰：v2.3.0 修复方向 ──
    # 按质量评分降序：manual > 有phase > 有skills > 长pattern > hits
    # 删最低质量的（末尾），保留高质量的（开头）
    max_rules = _a_rules_max()
    if len(_A_RULES) > max_rules:

        def _quality_score(item):
            _pattern, rule = item
            score = 0
            if rule.get("source") == "manual":
                score += 1000
            phases = rule.get("phases") or []
            score += len(phases) * 100
            skills = rule.get("skills") or []
            score += len(skills) * 10
            keywords = rule.get("keywords") or []
            score += len(keywords) * 5
            score += min(len(_pattern), 50)  # 更长的 pattern 更具体
            score += min(rule.get("hits", 0), 100) * 0.01  # hits 权重最低
            return score

        sorted_rules = sorted(_A_RULES.items(), key=_quality_score)  # 升序：低质量在前
        to_evict = len(_A_RULES) - max_rules
        evicted = 0
        for i in range(to_evict):
            if i >= len(sorted_rules):
                break
            pattern = sorted_rules[i][0]
            # manual 规则永不淘汰
            if _A_RULES[pattern].get("source") == "manual":
                continue
            del _A_RULES[pattern]
            evicted += 1
        if evicted:
            logger.info("[ssr] 上限淘汰: %d 条（按质量评分，manual 保护）", evicted)

    if dead_cleaned:
        logger.info("[ssr] A 层死引用清理: %d 个", dead_cleaned)
    if expired or empty_rules or dead_cleaned or garbage:
        _save_a_rules(_A_RULES)


def _auto_gen_a_rules() -> Dict[str, dict]:
    """从 _SKILL_INDEX 的 description 自动生成 A 层规则（v2 修复版）。

    两遍扫描：
      1. 建 {keyword: [skill_name, ...]} 频率表
      2. 只为 1~5 个 skill 共享的关键词建规则（过滤泛词）
    已有规则（用户手动添加的）不会被覆盖。
    """
    import re as _re

    STOP_WORDS = frozenset({
        'the', 'and', 'use', 'for', 'this', 'that', 'with', 'when',
        'from', 'your', 'can', 'how', 'are', 'you', 'has', 'its',
        'all', 'not', 'but', 'get', 'any', 'was', 'one', 'out',
    })
    MAX_SKILLS_PER_KW = 5   # 出现超过此数的关键词视为泛词，跳过

    # 第一遍：keyword → [skill_names]
    kw_to_skills: Dict[str, list] = {}
    for name, info in _SKILL_INDEX.items():
        desc = info.get("description", "")
        if not desc or len(desc) < 5:
            continue
        seen: set = set()
        for word in desc.lower().replace(",", " ").replace("/", " ").split():
            word = word.strip('()[]{}."\'')
            if _re.match(r'^[a-z]{3,}$', word) and word not in STOP_WORDS:
                seen.add(word)
        for cw in _re.findall(r'[\u4e00-\u9fff]{2,4}', desc):
            seen.add(cw)
        for kw in seen:
            kw_to_skills.setdefault(kw, []).append(name)

    # 第二遍：建规则（过滤泛词）
    rules: Dict[str, dict] = {}
    for kw, skill_names in kw_to_skills.items():
        if len(skill_names) > MAX_SKILLS_PER_KW:
            continue
        pattern = _re.escape(kw)
        rules[pattern] = {
            "keywords": [kw],
            "skills": skill_names,
            "source": "auto-gen",
        }
    return rules



# ---------------------------------------------------------------------------
# Embedding 语义匹配
# ---------------------------------------------------------------------------

def _expand_chinese_query(text: str) -> str:
    """中文查询 → 追加英文领域关键词，提升跨语言匹配精度。

    映射覆盖已知盲区：金融、UI、调试、音乐、旅行等。
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


# embedding 矩阵缓存：(key, names, 归一化后的矩阵)。key = (id(索引 dict), len)
# 后台同步会整体替换 _EMBEDDING_INDEX（id 变），热新增会追加条目（len 变），
# 两种情况都能自动失效，不需要额外的失效广播。
_EMB_MATRIX_CACHE = None
_NUMPY = None


def _numpy():
    """延迟导入 numpy；不可用时返回 None（自动降级纯 Python）。"""
    global _NUMPY
    if _NUMPY is None:
        try:
            import numpy as _np
            _NUMPY = _np
        except Exception:
            _NUMPY = False
    return _NUMPY or None


def _cosine_sim(a, b):
    """余弦相似度（numpy 优先，缺失时降级纯 Python）"""
    np = _numpy()
    if np is not None:
        try:
            va = np.asarray(a, dtype="float32")
            vb = np.asarray(b, dtype="float32")
            na = float(np.linalg.norm(va))
            nb = float(np.linalg.norm(vb))
            if na == 0.0 or nb == 0.0:
                return 0.0
            return float(np.dot(va, vb) / (na * nb))
        except Exception:
            pass
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _rank_by_embedding(query_vec, top_k: int = 30):
    """给全部已索引 skill 打分，返回 [(sim, name), ...] 降序。

    原来是 for 循环里逐条 _cosine_sim（751 条 × 4096 维 ≈ 300 万次 Python 级
    运算），这里换成一次 numpy 矩阵乘法：先把索引矩阵按行归一化并缓存，查询时
    只需 query 归一化后点积。numpy 缺失或构建失败时自动降级为逐条比对。
    """
    global _EMB_MATRIX_CACHE
    index = _EMBEDDING_INDEX
    if not index:
        return []
    np = _numpy()
    if np is None:
        return [(_cosine_sim(query_vec, entry["embedding"]), name)
                for name, entry in index.items()]

    cache_key = (id(index), len(index))
    names, matrix = None, None
    if _EMB_MATRIX_CACHE and _EMB_MATRIX_CACHE[0] == cache_key:
        _, names, matrix = _EMB_MATRIX_CACHE
    if matrix is None:
        try:
            names = list(index.keys())
            matrix = np.asarray([index[n]["embedding"] for n in names], dtype="float32")
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            matrix = matrix / norms
            _EMB_MATRIX_CACHE = (cache_key, names, matrix)
        except Exception as e:
            logger.debug("[ssr] embedding 矩阵构建失败，降级逐条比对: %s", e)
            return [(_cosine_sim(query_vec, entry["embedding"]), name)
                    for name, entry in index.items()]

    q = np.asarray(query_vec, dtype="float32")
    qn = float(np.linalg.norm(q))
    if qn == 0.0:
        return []
    sims = matrix @ (q / qn)
    k = min(top_k, len(names))
    if k <= 0:
        return []
    order = np.argsort(-sims)[:k]
    return [(float(sims[i]), names[i]) for i in order]


# embedding 调用健康度：失败不再只是 logger.debug（原来索引悄悄失败根本看不出来）
_EMBED_STATS = {"ok": 0, "fail": 0, "last_error": ""}
# 整批失败后按这个粒度降级重试，避免「一条坏 description 连累整批」
_EMBED_SALVAGE_CHUNK = 8
_EMBED_CLIENT = None
_EMBED_CLIENT_LOCK = threading.Lock()


def _embed_batch_size() -> int:
    """一批打包多少条 description（SiliconFlow /embeddings 支持 input 数组）。"""
    try:
        n = int(_load_ssr_config().get("embedding", {}).get("batch_size", 32))
    except Exception:
        n = 32
    return max(1, min(n, 128))


def _embed_max_retries() -> int:
    """单批失败后重试几次（指数退避）。"""
    try:
        n = int(_load_ssr_config().get("embedding", {}).get("max_retries", 2))
    except Exception:
        n = 2
    return max(0, min(n, 5))


def _get_embed_client():
    """共享的 httpx.Client：复用连接。

    原来每次 httpx.post 都新建连接，经代理时要重新 CONNECT + TLS 握手；
    批量场景下握手次数从「条数」降到「批数」。
    """
    global _EMBED_CLIENT
    if _EMBED_CLIENT is None:
        with _EMBED_CLIENT_LOCK:
            if _EMBED_CLIENT is None:
                import httpx
                _EMBED_CLIENT = httpx.Client(
                    timeout=_embed_timeout(),
                    limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
                )
    return _EMBED_CLIENT


def _post_embed_batch(texts, url, headers, timeout):
    """发一批 embedding（单次请求，不重试）。异常向上抛。"""
    payload = {"model": _embed_model(), "input": texts, "encoding_format": "float"}
    resp = _get_embed_client().post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    out = [None] * len(texts)
    for i, item in enumerate(data):
        if i < len(out):
            out[i] = item.get("embedding")
    return out


def _embed_batch_with_retry(texts, url, headers, timeout, retries):
    """一批带重试。成功返回 (结果列表, None)；全部失败返回 (None, 最后一次异常)。"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            return _post_embed_batch(texts, url, headers, timeout), None
        except Exception as e:
            last_err = e
            _EMBED_STATS["last_error"] = "%s: %s" % (type(e).__name__, e)
            if attempt < retries:
                delay = 0.5 * (2 ** attempt)
                logger.warning("[ssr] embedding 批失败（第 %d 次），%.1fs 后重试: %s",
                               attempt + 1, delay, e)
                time.sleep(delay)
    return None, last_err


def _embed_many(texts):
    """批量 embedding：返回与 texts 等长的列表，失败位置为 None。

    - siliconflow: /embeddings 支持 input 数组，一次算一整批（原来一条一次请求）。
    - ollama: /api/embeddings 只接受单条，保持逐条，但共用同一个 client。
    失败会重试 ``_embed_max_retries()`` 次（指数退避）；整批仍失败则保持 None，
    并累加到 _EMBED_STATS，便于在注册日志/健康度里看到。
    """
    texts = list(texts)
    if not texts:
        return []
    provider = _embed_provider()
    timeout = _embed_timeout()
    retries = _embed_max_retries()
    out = [None] * len(texts)

    if provider == "siliconflow":
        key = _embed_api_key()
        if not key:
            logger.warning("[ssr] embedding siliconflow 无 api_key，跳过 %d 条", len(texts))
            _EMBED_STATS["fail"] += len(texts)
            _EMBED_STATS["last_error"] = "no api_key"
            return out
        url = _embed_base_url().rstrip("/") + "/embeddings"
        headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
        result, err = _embed_batch_with_retry(texts, url, headers, timeout, retries)
        if result is not None:
            out = result
        elif len(texts) > 1:
            # 整批失败：切成小批再试，避免「一条坏条目连累整批」。
            # 降级组只重试 1 次，控制最坏耗时与请求数。
            logger.warning("[ssr] embedding 整批失败（%d 条），降级为每 %d 条一组重试: %s",
                           len(texts), _EMBED_SALVAGE_CHUNK, err)
            for start in range(0, len(texts), _EMBED_SALVAGE_CHUNK):
                sub = texts[start:start + _EMBED_SALVAGE_CHUNK]
                sub_result, sub_err = _embed_batch_with_retry(sub, url, headers, timeout, 1)
                if sub_result is not None:
                    out[start:start + len(sub)] = sub_result
                else:
                    logger.warning("[ssr] embedding 降级组仍失败（%d 条），本次跳过: %s",
                                   len(sub), sub_err)
        else:
            logger.warning("[ssr] embedding 单条失败（已重试 %d 次），跳过: %s", retries, err)
        got = sum(1 for v in out if v)
        _EMBED_STATS["ok"] += got
        _EMBED_STATS["fail"] += len(out) - got
        if got < len(out):
            logger.warning("[ssr] embedding 本批成功 %d/%d", got, len(out))
        return out

    # 其它后端（含 ollama）：逐条，但复用连接 + 重试
    for i, text in enumerate(texts):
        for attempt in range(retries + 1):
            try:
                if provider == "ollama":
                    from urllib.parse import urljoin
                    url = urljoin(_ollama_url(), "/api/embeddings")
                    resp = _get_embed_client().post(
                        url, json={"model": _embed_model(), "prompt": text},
                        timeout=timeout)
                    resp.raise_for_status()
                    out[i] = resp.json().get("embedding")
                else:
                    logger.warning("[ssr] embedding 后端 %s 未实现", provider)
                if out[i]:
                    _EMBED_STATS["ok"] += 1
                break
            except Exception as e:
                _EMBED_STATS["last_error"] = "%s: %s" % (type(e).__name__, e)
                if attempt < retries:
                    time.sleep(0.5 * (2 ** attempt))
                else:
                    _EMBED_STATS["fail"] += 1
                    logger.debug("[ssr] embedding 单条失败（%s）: %s", provider, e)
    return out


def _embed(text):
    """单条 embedding（保持旧接口不变）。失败返回 None。"""
    return _embed_many([text])[0]


def _cleanup_stale_embed_tmp() -> int:
    """清理残留的 embeddings.json.tmp.* 临时文件。

    写索引用「先写临时文件再 os.replace」（原子写），但进程被 kill -9 时来不及
    清理，会留下半成品临时文件。这里只删「不属于本进程」且「超过 1 小时没动」的，
    避免误删另一个 hermes 进程正在写的临时文件。
    """
    removed = 0
    try:
        for path in SSR_DIR.glob("embeddings.json.tmp.*"):
            if path.name.rsplit(".", 1)[-1] == str(os.getpid()):
                continue
            try:
                if time.time() - path.stat().st_mtime < 3600:
                    continue
                path.unlink()
                removed += 1
            except Exception:
                continue
    except Exception:
        pass
    if removed:
        logger.info("[ssr] 清理残留 embedding 临时文件: %d 个", removed)
    return removed


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
    """持久化 embedding 索引（原子写：先写临时文件，写完整体替换）。

    原来直接 open(path, "w") 覆写约 70MB 的索引：若进程在写入中途退出（例如启动
    等待超时被 Desktop 杀掉），文件会留下被截断的半成品；下次
    _load_embedding_index() 解析失败返回 {}，就会走 _build_embedding_index()
    全量重建数百条 embedding，反而把启动彻底卡死。os.replace() 是原子操作，
    任何时刻中断都只会留下「完整的旧索引」或「完整的新索引」。
    """
    path = SSR_DIR / "embeddings.json"
    tmp_path = path.with_name("%s.tmp.%d" % (path.name, os.getpid()))
    try:
        with open(tmp_path, "w") as f:
            json.dump(index, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        logger.warning("[ssr] embedding 索引保存失败: %s", e)
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass



# 推荐结果缓存（session_id → formatted recommendation）
_POST_LLM_CACHE: Dict[str, str] = {}


def _post_llm_call(text: str = "", session_id: str = "", **kwargs) -> str:
    """post_llm_call hook: 将 SSR 推荐前置到回答开头。
    
    遵循 display 开关：ssr.display=false（静默）不注入、ssr.display=true 注入。
    """
    if not session_id:
        return text
    if not _display_enabled():
        return text
    rec = _POST_LLM_CACHE.pop(session_id, "")
    if not rec:
        return text
    return rec + "\n---\n" + text



def _make_embed_progress(label):
    """生成批量 embedding 的进度打印回调（每 200 条或最后一条打一次）。"""
    def _progress(done, total):
        if done % 200 == 0 or done == total:
            logger.info("[ssr] embedding %s: %d/%d", label, done, total)
    return _progress


def _embed_in_batches(items, on_progress=None):
    """把 [(name, desc), ...] 分批算 embedding，返回 {name: {"embedding","desc"}}。

    只有成功拿到向量的条目才会出现在返回值里；失败的批次整批跳过，
    由调用方在下次启动/热更新时重试。
    """
    result = {}
    if not items:
        return result
    batch_size = _embed_batch_size()
    total = len(items)
    done = 0
    for start in range(0, total, batch_size):
        chunk = items[start:start + batch_size]
        vecs = _embed_many([desc for _, desc in chunk])
        for (name, desc), vec in zip(chunk, vecs):
            if vec:
                result[name] = {"embedding": vec, "desc": desc}
        done += len(chunk)
        if on_progress:
            on_progress(done, total)
    return result


def _build_embedding_index():
    """为所有 skill description 构建 embedding 索引。全量构建（批量 + 进度）。"""
    items = [(name, info.get("description", ""))
             for name, info in _SKILL_INDEX.items()
             if info.get("description") and len(info.get("description", "")) >= 5]
    total = len(items)
    logger.info("[ssr] embedding 索引构建：%d 条待算（批大小 %d）",
                total, _embed_batch_size())
    index = _embed_in_batches(items, on_progress=_make_embed_progress("索引构建"))
    _save_embedding_index(index)
    logger.info("[ssr] embedding 索引构建完成: %d/%d skill（失败 %d）",
                len(index), total, total - len(index))
    return index


def _sync_embeddings():
    """增量更新 embedding 索引：新增 skill + description 发生变更的 skill。

    description 变更是靠「旧索引里本来就存了 desc 字段」来比对的，不引入新字段，
    因此对历史索引完全向后兼容：老条目 desc 没变 → 不会重算（不会触发全量重建）。
    """
    global _EMBEDDING_INDEX
    existing = _load_embedding_index()
    current = set(_SKILL_INDEX.keys())
    indexed = set(existing.keys())

    new_skills = current - indexed
    removed = indexed - current

    # description 变更检测（原来只比对键名，改了描述不会重算向量）
    stale = set()
    for name in (current & indexed):
        old_desc = (existing.get(name) or {}).get("desc")
        cur_desc = _SKILL_INDEX[name].get("description", "")
        if old_desc and cur_desc and old_desc != cur_desc:
            stale.add(name)

    for name in removed:
        del existing[name]

    todo = []
    for name in sorted(new_skills | stale):
        desc = _SKILL_INDEX[name].get("description", "")
        if not desc or len(desc) < 5:
            continue
        todo.append((name, desc))

    built = {}
    if todo:
        built = _embed_in_batches(todo, on_progress=_make_embed_progress("增量同步"))
        existing.update(built)

    if new_skills or removed or stale:
        _save_embedding_index(existing)
        logger.info("[ssr] embedding 增量: 新增 %d / 描述变更 %d / 删除 %d -> %d skill"
                    "（待算 %d，成功 %d）",
                    len(new_skills), len(stale), len(removed), len(existing),
                    len(todo), len(built))

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
    """热删除：从 embedding 索引移除 + 清理 A 层死引用（v2+v3 兼容）。"""
    global _INDEX_DIRTY
    # Embedding 索引
    if name in _EMBEDDING_INDEX:
        del _EMBEDDING_INDEX[name]
    try:
        idx = _load_embedding_index()
        if name in idx:
            del idx[name]
            _save_embedding_index(idx)
    except Exception:
        _INDEX_DIRTY = True
    # A 层规则清理
    # FIX: skip manual-created rules in hot-remove cleanup
    dead_count = 0
    for pattern, rule in list(_A_RULES.items()):
        if rule.get("source") == "manual":
            continue
        # v2 格式: skills
        if "skills" in rule:
            skills = rule["skills"]
            live = [s for s in skills if (s["name"] if isinstance(s,dict) else s) != name]
            if len(live) < len(skills):
                dead_count += len(skills) - len(live)
                rule["skills"] = live
        # v3 格式: keywords
        if "keywords" in rule and name in rule["keywords"]:
            rule["keywords"] = [kw for kw in rule["keywords"] if kw != name]
            dead_count += 1
    if dead_count:
        _save_a_rules(_A_RULES)
        logger.info("[ssr] 热删除 %s → A 层清理 %d 个引用", name, dead_count)
    return True


def _promote_to_a(pattern: str, skills: List[dict]) -> None:
    """B 层匹配升级到 A 层 — v3 keywords 格式。
    
    从匹配模式提取关键词，不拆 skill 名。
    """
    phases = list(set(s.get("phase", "") for s in skills if s.get("phase")))
    # 从 regex pattern 提取实义词
    keywords = []
    import re
    # 移除 regex 语法，保留字面量
    parts = re.split(r'[\|\(\)\.\*\+\?\^\[\]\{\}]', pattern)
    for part in parts:
        part = part.strip()
        if len(part) >= 2:
            keywords.append(part.lower())
    keywords = list(set(keywords))[:12]

    _A_RULES[pattern] = {
        "keywords": keywords,
        "phases": phases,
        "hits": PROMOTE_THRESHOLD,
        "last_hit": time.strftime("%Y-%m-%d"),
        "source": "auto",
    }
    _mark_a_dirty()
    logger.info("[ssr] B→A 升级 (v3): %s → keywords=%s", pattern, keywords[:5])


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


def _llm_screen(user_message: str, candidates: List[str]) -> Optional[List[dict]]:
    """LLM 语境筛查：从候选 skill 中挑出真正相关的。

    Returns: 筛选后 [{name,phase}]，[]=全不相关，None=调用失败降级放行
    """
    if not candidates:
        return []

    skill_lines = []
    for name in candidates[:15]:
        info = _SKILL_INDEX.get(name, {})
        desc = info.get("description", "")[:80]
        skill_lines.append(f"- {name}: {desc}")

    prompt = f"""审查这些技能是否与用户消息真正相关。

用户消息：「{user_message}」

候选技能：
{chr(10).join(skill_lines)}

返回 JSON: {{"relevant": ["技能名1"]}}
规则：只返回真正相关的。全不相关返回空数组。不要解释。"""

    try:
        import httpx, yaml as _yaml
        config_path = Path.home() / ".hermes" / "config.yaml"
        with open(config_path) as f:
            cfg = _yaml.safe_load(f)
        bl = cfg.get("ssr", {}).get("b_layer", {})
        model = bl.get("model", "qwen3.5:4b")
        base_url = (bl.get("base_url", "") or "http://localhost:11434").rstrip("/").removesuffix("/v1")
        api_key = bl.get("api_key", "")
        if not api_key:
            main_cfg = _load_main_model_config()
            api_key = main_cfg.get("api_key", "")
            base_url = (main_cfg.get("base_url", "") or base_url).rstrip("/").removesuffix("/v1")
        provider = bl.get("provider", "main")

        # 本地 Ollama 用原生 /api/chat（推理模型需 think:false，OpenAI shim 不透传）
        _is_ollama = (provider == "ollama") or (not api_key and "localhost" in base_url)
        if _is_ollama:
            resp = httpx.post(
                f"{base_url.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": f"不要用代码围栏包裹JSON。只返回纯JSON。\n{prompt}"}],
                    "think": False,
                    "stream": False,
                    "options": {"num_predict": 300},
                },
                timeout=_b_timeout(),
            )
            if resp.status_code != 200:
                logger.warning("[ssr] LLM 筛查 HTTP %d", resp.status_code)
                return None
            content = resp.json().get("message", {}).get("content", "")
        else:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = httpx.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 300, "temperature": 0,
                      "thinking": {"type": "disabled"}},
                timeout=_b_timeout(),
            )
            if resp.status_code != 200:
                logger.warning("[ssr] LLM 筛查 HTTP %d", resp.status_code)
                return None
            content = resp.json()["choices"][0]["message"]["content"]

        start = content.find('{')
        if start == -1:
            return None
        depth = 0
        end = start
        in_string = False
        escape = False
        for i, ch in enumerate(content[start:], start):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        raw = content[start:end+1].strip()
        # Sanitize unquoted keys: {key: val} -> {"key": val}
        raw = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', raw)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            try:
                import ast
                py_raw = raw.replace("true", "True").replace("false", "False").replace("null", "None")
                parsed = ast.literal_eval(py_raw)
            except Exception:
                return None
        relevant = set(parsed.get("relevant", []))
        if not relevant:
            return []

        result = []
        for name in relevant:
            if name in _SKILL_INDEX:
                result.append({"name": name, "phase": _infer_phase(name)})
        return result

    except Exception as e:
        logger.info("[ssr] LLM 筛查失败（降级放行）: %s", e)
        return None


def _call_llm_screen_direct(prompt: str) -> Optional[List[dict]]:
    """直接调 LLM 判断意图+匹配（无候选时的独立匹配兜底）。"""
    import httpx, yaml as _yaml
    config_path = Path.home() / ".hermes" / "config.yaml"
    with open(config_path) as f:
        cfg = _yaml.safe_load(f)
    bl = cfg.get("ssr", {}).get("b_layer", {})
    model = bl.get("model", "qwen3.5:4b")
    base_url = (bl.get("base_url", "") or "http://localhost:11434").rstrip("/").removesuffix("/v1")
    api_key = bl.get("api_key", "")
    if not api_key:
        main_cfg = _load_main_model_config()
        api_key = main_cfg.get("api_key", "")
        base_url = (main_cfg.get("base_url", "") or base_url).rstrip("/").removesuffix("/v1")

    try:
        provider = bl.get("provider", "main")
        _is_ollama = (provider == "ollama") or (not api_key and "localhost" in base_url)
        if _is_ollama:
            resp = httpx.post(
                f"{base_url.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": f"不要用代码围栏包裹JSON。只返回纯JSON。\n{prompt}"}],
                    "think": False, "stream": False,
                    "options": {"num_predict": 300},
                },
                timeout=_b_timeout(),
            )
            if resp.status_code != 200:
                logger.warning("[ssr] LLM 独立匹配 HTTP %d", resp.status_code)
                return None
            content = resp.json().get("message", {}).get("content", "")
        else:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = httpx.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 300, "temperature": 0,
                      "thinking": {"type": "disabled"}},
                timeout=_b_timeout(),
            )
            if resp.status_code != 200:
                logger.warning("[ssr] LLM 独立匹配 HTTP %d", resp.status_code)
                return None
            content = resp.json()["choices"][0]["message"]["content"]
        start = content.find('{')
        if start == -1:
            return None
        depth = 0
        end = start
        in_string = False
        escape = False
        for i, ch in enumerate(content[start:], start):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        raw = content[start:end+1].strip()
        # Sanitize unquoted keys: {key: val} -> {"key": val}
        raw = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', raw)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            try:
                import ast
                py_raw = raw.replace("true", "True").replace("false", "False").replace("null", "None")
                parsed = ast.literal_eval(py_raw)
            except Exception:
                return None
        if not parsed.get("need_skill", False):
            return []
        relevant = parsed.get("relevant", [])
        if not relevant:
            return []
        result = []
        for name in relevant:
            if name in _SKILL_INDEX:
                result.append({"name": name, "phase": _infer_phase(name)})
        return result
    except Exception as e:
        logger.info("[ssr] LLM 独立匹配失败（降级放行）: %s", e)
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


# ── LLM 意图门控 v2.3.0 ──
_INTENT_GATE_CACHE: Dict[str, bool] = {}

def _call_llm_intent(provider: str, model: str, base_url: str,
                     api_key: str, msg: str, timeout: int, gate_prompt: str = "") -> Optional[bool]:
    """调用 LLM 做意图二分类。返回 True/False/None(None=调用失败)。
    
    gate_prompt: 从 config.yaml → ssr.intent_gate.prompt 读取；为空则用默认 prompt。
    """
    # 默认 prompt（config 未配置时使用）
    default_prompt = "Does this user message need an AI skill? Answer only YES or NO."
    prompt = gate_prompt.strip() if gate_prompt else default_prompt
    try:
        import httpx

        # ollama 走 /api/generate，支持 think:false 跳过推理
        if provider == "ollama":
            r = httpx.post(
                f"{base_url.rstrip('/')}/api/generate",
                json={
                    "model": model,
                    "prompt": f"{prompt}\nMessage: {msg}\nAnswer:",
                    "stream": False,
                    "think": False,
                },
                timeout=timeout,
            )
            if r.status_code == 200:
                answer = r.json().get("response", "").strip().upper()
                return "YES" in answer
            return None

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        r = httpx.post(
            f"{base_url.rstrip('/').removesuffix('/v1')}/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Answer only YES or NO. Do not explain."},
                    {"role": "user", "content": f"{prompt}\n\nMessage: \"{msg}\""}
                ],
                "max_tokens": 3,
                "temperature": 0,
                "thinking": {"type": "disabled"},
            },
            timeout=timeout,
        )
        if r.status_code == 200:
            answer = r.json()["choices"][0]["message"]["content"].strip().upper()
            return "YES" in answer
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# 自循环学习 (v2.1)
# ═══════════════════════════════════════════════════════════

_PREFS_PATH = SSR_DIR / "preferences.json"
_SESSION_RECOMMENDED: set = set()


def _load_preferences() -> dict:
    """加载 skill 偏好分数。{skill_name: score}"""
    try:
        if _PREFS_PATH.exists():
            return json.loads(_PREFS_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_preferences(prefs: dict) -> None:
    """持久化偏好分数。"""
    try:
        _PREFS_PATH.write_text(json.dumps(prefs, ensure_ascii=False, indent=2))
    except Exception:
        pass


def _boost_skill(skill_name: str, delta: float = 1.0) -> None:
    """用户采纳推荐 → 加分。"""
    prefs = _load_preferences()
    prefs[skill_name] = prefs.get(skill_name, 0) + delta
    _save_preferences(prefs)
    logger.info(f"[ssr] 自循环: +{delta} → {skill_name} (总 {prefs[skill_name]})")


def _penalize_skill(skill_name: str, delta: float = 0.5) -> None:
    """用户忽略推荐 → 扣分。"""
    prefs = _load_preferences()
    prefs[skill_name] = max(-10, prefs.get(skill_name, 0) - delta)
    _save_preferences(prefs)


def boost_skill(skill_name: str) -> None:
    """公开 API：用户手动加载了推荐过的 skill 时调用。"""
    if skill_name in _SESSION_RECOMMENDED:
        _boost_skill(skill_name)
        _SESSION_RECOMMENDED.discard(skill_name)


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
        logger.info("[ssr] 极短噪音拦截 → 静默 (%d字: %s)", len(msg), msg)
        return False

    cache_key = msg[:60]

    # 任务动词安全阀（共用——噪音过滤和元对话检测都需要）
    _TASK_VERBS = re.compile(
        r'(设计|写|生成|部署|画|做|创建|构建|实现|修复|分析|查询|搜索|查找|'
        r'计算|转换|优化|配置|安装|发送|测试|帮我|安排|规划|总结|翻译|'
        r'解释|对比|检查|调试|诊断|处理|整理|推荐|评估|'
        r'design|write|create|build|deploy|fix|analyze|search|find|'
        r'calculate|convert|configure|install|send|test|help|plan|'
        r'summarize|translate|explain|compare|debug|diagnose|review)'
    )

    # ── v2.1 P1: 元对话检测（零 token 正则预检）──
    _META_CONVO = re.compile(
        r'^/(?:moa|model|learn|skills|config|plan|goal|reset)\b|'
        r'^hermes\s|'
        r'(?:ssr|cmg|guard|canon|mnemonic|skill系统|plugin|provider|config\.yaml|\.env|'
        r'信号|命中率|benchmark|准确率|推荐质量|A层|B层|embedding|嵌入)'
        r'.*?(?:改|修|调|配|设置|怎么|如何|为什么|问题|bug|报错|噪音|静默|规则|匹配|阈值|推荐|怎么样|测|跑|验证|效果|高|低|对|准不准)|'
        r'(?:怎么|如何|为什么|帮我|能不能|有没有|调整|修改|配置|设置|配|改|换)'
        r'.*?(?:ssr|cmg|guard|canon|mnemonic|skill系统|plugin|moa|模型|model|provider|预设|preset|'
        r'信号|命中率|benchmark|推荐|embedding|A层|B层)',
        re.IGNORECASE
    )
    _STRONG_TASKS = re.compile(
        r'(设计|写|生成|部署|画|创建|构建|实现|修复|制作|开发|搭建|规划|'
        r'design|write|create|build|deploy|make|develop|implement|fix|generate|plan)',
        re.IGNORECASE
    )
    if _META_CONVO.search(msg):
        if not _STRONG_TASKS.search(msg):
            logger.info("[ssr] 元对话检测 → 静默")
            _INTENT_GATE_CACHE[cache_key] = False
            return False

    # ── 通用噪音过滤：全量模式从 config.yaml 读取，零硬编码 ──
    noise_cfg = _load_ssr_config().get("noise_filter", {})
    if noise_cfg.get("enabled", True):
        for pat in noise_cfg.get("patterns", []):
            try:
                if re.search(pat, msg, re.IGNORECASE):
                    # 安全阀：含任务动词 → 放行
                    if not _TASK_VERBS.search(msg):
                        logger.info("[ssr] 噪音过滤 → 静默")
                        _INTENT_GATE_CACHE[cache_key] = False
                        return False
            except re.error:
                continue

    # 缓存命中
    if cache_key in _INTENT_GATE_CACHE:
        return _INTENT_GATE_CACHE[cache_key]

    # 读配置
    cfg = _load_intent_gate_config()
    if not cfg.get("enabled", True):
        return True

    providers = cfg.get("providers", [])
    active = cfg.get("active", "")
    on_error = cfg.get("on_error", "pass")

    if not providers:
        return True

    # 只使用 active 指定的 provider，不遍历
    p = None
    if active:
        for prov in providers:
            if prov.get("provider") == active:
                p = prov
                break
    if not p:
        p = providers[0]  # 没设 active 或用第一个
    
    provider = p.get("provider", "")
    model = p.get("model", "")
    timeout = p.get("timeout", 10)

    if not model:
        if provider == "main":
            main_cfg = _load_main_model_config()
            model = main_cfg.get("default", "")
        if not model:
            _INTENT_GATE_CACHE[cache_key] = True
            return True

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
        _INTENT_GATE_CACHE[cache_key] = True
        return True

    if not base_url:
        _INTENT_GATE_CACHE[cache_key] = True
        return True

    result = _call_llm_intent(provider, model, base_url, api_key, msg, timeout, cfg.get("prompt", ""))
    if result is not None:
        _INTENT_GATE_CACHE[cache_key] = result
        return result

    # 调用失败 → 放行
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
        # api_key 可能在子节点（curator / triage_specifier 等）
        if not api_key:
            for sub_key in ("curator", "triage_specifier", "title_generation"):
                sub = model_cfg.get(sub_key, {})
                if isinstance(sub, dict) and sub.get("api_key"):
                    api_key = sub["api_key"]
                    break
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
            # api_key 可能在子节点
            if not api_key:
                for sub_key in ("curator", "triage_specifier", "title_generation"):
                    sub = model_cfg.get(sub_key, {})
                    if isinstance(sub, dict) and sub.get("api_key"):
                        api_key = sub["api_key"]
                        break
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
                {"role": "system", "content": f"列出与此消息最相关的至多3个技能名，JSON格式：{{\"skills\":[\"name1\",\"name2\"],\"phases\":[\"BUILD\",\"DISCOVER\"]}}。如确实无相关技能，返回{{\"skills\":[]}}。可用技能：\n{skill_list}"},
                {"role": "user", "content": f"「{user_message}」"},
            ],
            "temperature": 0,
            "max_tokens": 200,
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
    """格式化推荐消息，按阶段分组 — 单行紧凑输出（v2.1.0）。"""
    # 自循环：记录本次推荐
    for s in skills:
        _SESSION_RECOMMENDED.add(s["name"])
    phase_tag = {"DISCOVER": "D", "PLAN": "P", "BUILD": "B", "VERIFY": "V"}
    groups: Dict[str, list] = {}
    for s in skills:
        phase = s.get("phase", "BUILD")
        groups.setdefault(phase, [])
        name = s["name"]
        if s.get("shown_recently"):
            name = f"{name}(刚才)"
        groups[phase].append(name)
    parts = []
    max_display = _display_max()
    for phase in PHASE_ORDER:
        if phase not in groups:
            continue
        tag = phase_tag.get(phase, phase)
        names = groups[phase]
        if max_display > 0 and len(names) > max_display:
            shown = names[:max_display]
            rest = len(names) - max_display
            parts.append(f"[{tag}] {', '.join(shown)} …+{rest}")
        else:
            parts.append(f"[{tag}] {', '.join(names)}")
    body = " | ".join(parts)
    return f"[SSR] {body}"


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

    # ── v2.1.0 LLM 意图门控 ──
    if not _intent_gate(user_message):
        logger.debug("[ssr] 意图门控: NO → 静默")
        if _display_enabled():
            silence_msg = "[SSR] 本轮静默 (意图门控判定非任务请求)"
            if session_id:
                _POST_LLM_CACHE[session_id] = silence_msg
            return {"context": silence_msg}
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

        # ── A 层匹配（关键词 + embedding 候选召回）──
        candidates = _match_a_layer(user_message)

        # ── LLM 统一决策 ──
        if candidates:
            # 有候选：LLM 筛选确认（llm_screen=false 时跳过，直接用 A 层结果）
            candidate_names = [s["name"] for s in candidates[:20]]
            if _load_ssr_config().get("llm_screen", False):
                screened = _llm_screen(user_message, candidate_names)
                if screened is not None:
                    if screened or len(candidates) < 5:
                        result = screened
                    else:
                        logger.info("[ssr] LLM 筛查否决但 A 层命中 %d ≥ 5，信任 A 层", len(candidates))
                        result = candidates
                else:
                    result = candidates
            else:
                result = candidates
        else:
            # 无候选：LLM 独立匹配（兜底）
            all_list = [f"- {n}: {_SKILL_INDEX.get(n, {}).get('description', '')[:80]}" for n in list(_SKILL_INDEX.keys())[:200]]
            prompt = "你是技能路由器。可用技能:\n" + "\n".join(all_list) + "\n\n消息:「" + user_message + "」\n\n纯闲聊/感叹 → {\"need_skill\":false,\"relevant\":[]}\n有任务意图 → {\"need_skill\":true,\"relevant\":[\"技能名\"]}\n只JSON,最多5个。"
            screened = _call_llm_screen_direct(prompt)
            if screened is not None:
                result = screened
            else:
                stats["misses"] += 1
                return None

        if not result:
            stats["misses"] += 1
            a_hit_count = len(candidates) if candidates else 0
            logger.info("[ssr] LLM 筛查: 语境无关 → 静默 (A层 %d 命中)", a_hit_count)
            if _display_enabled():
                silence_msg = f"[SSR] 本轮静默 (A层 {a_hit_count} 条候选，LLM 筛查判定语境无关)"
                if session_id:
                    _POST_LLM_CACHE[session_id] = silence_msg
                return {"context": silence_msg}
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

        # ── display 开关：提前拦截，避免无用格式化和缓存写入 ──
        if not _display_enabled():
            stats["hits_b"] += 1
            return None

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

        # ── 格式化推荐 ──
        rec = _format_recommendation(fresh)
        if rec and session_id:
            _POST_LLM_CACHE[session_id] = rec  # 先缓存，确保 post_llm_call 总能拿到
        conf = _compute_confidence(fresh)
        threshold = _confidence_threshold()
        if conf < threshold:
            stats["skipped_low_conf"] += 1
            logger.info("[ssr] B 层置信度不足 (%.3f < %.2f)，跳过 pre 注入，post 仍会展示", conf, threshold)
            return None
        stats["hits_b"] += 1
        if stats["calls"] % _STATS_LOG_INTERVAL == 0:
            _log_session_stats(session_id)
        logger.info("[ssr] B 层命中: %s", [s["name"] for s in fresh])
        # ── report 模式：在推荐后追加汇报指令 ──
        if _report_enabled():
            skill_names = ", ".join(s["name"] for s in fresh)
            rec += f"\n[SSR-REPORT] 以上是 SSR 推荐。你必须在回复末尾附一行：`[SSR 使用] 推荐: {skill_names} | 已用: [列出] | 跳过: [列出+原因]`。如果本轮无 SSR 推荐则写 `[SSR 使用] 本轮无推荐`。"
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

    # 加载 A 层规则
    _A_RULES = _load_a_rules()
    logger.info("[ssr] 加载 A 层规则: %d 条", len(_A_RULES))

    # 自动生成 A 层规则（基于本地 skill description，不绑定特定 skill 集）
    added = 0
    if _auto_gen_enabled():
        auto_gen = _auto_gen_a_rules()
        for k, v in auto_gen.items():
            if k not in _A_RULES:
                _A_RULES[k] = v
                added += 1
        logger.info("[ssr] auto-gen: +%d 条 → A 层共 %d 条", added, len(_A_RULES))
    else:
        logger.info("[ssr] auto-gen 已关闭（ssr.auto_gen_rules: false）")

    # v2.3.0 修复：清理必须在 auto-gen 之后执行
    # auto-gen 从 skill description 提取关键词，可能产出单英文词等垃圾。
    # 清理→auto-gen→不清理 = auto-gen 垃圾永驻磁盘。
    _cleanup_a_rules()
    logger.info("[ssr] 清理后 A 层规则: %d 条", len(_A_RULES))
    # 清理后的结果必须持久化（不论 auto-gen 是否开启）
    _save_a_rules(_A_RULES)

    # 清理历史上被 kill -9 留下的 embedding 临时文件（只占磁盘，不影响读取）
    _cleanup_stale_embed_tmp()

    # Phase 2: Embedding 索引构建
    # 启动（plugin register）只做本地加载；联网计算新向量交给后台线程，避免联网
    # 请求把插件注册——也就是整个 hermes 启动——堵死（Desktop 等端口公告 90s 超时
    # 就会判定启动失败）。后台补齐之前，未索引的 skill 仍可由 A 层关键词匹配命中，
    # 补齐后自动参与语义检索。
    emb_count = 0
    try:
        existing = _load_embedding_index()
        if existing:
            _EMBEDDING_INDEX = existing
            emb_count = len(_EMBEDDING_INDEX)
            logger.info("[ssr] embedding 索引: %d skill（已加载，增量同步转入后台）", emb_count)

            def _background_embed_sync() -> None:
                try:
                    _sync_embeddings()
                    logger.info("[ssr] embedding 后台增量同步完成: %d skill | 本次 ok=%d fail=%d%s",
                                len(_EMBEDDING_INDEX), _EMBED_STATS["ok"], _EMBED_STATS["fail"],
                                (" | last_error=" + _EMBED_STATS["last_error"])
                                if _EMBED_STATS["last_error"] else "")
                except Exception as e:
                    logger.warning("[ssr] embedding 后台增量同步失败（继续用关键词匹配）: %s", e)

            threading.Thread(target=_background_embed_sync, name="ssr-embed-sync",
                             daemon=True).start()
        else:
            logger.info("[ssr] embedding 索引首次构建转入后台...")

            def _background_embed_build() -> None:
                global _EMBEDDING_INDEX
                try:
                    _EMBEDDING_INDEX = _build_embedding_index()
                    logger.info("[ssr] embedding 后台构建完成: %d skill | 本次 ok=%d fail=%d%s",
                                len(_EMBEDDING_INDEX), _EMBED_STATS["ok"], _EMBED_STATS["fail"],
                                (" | last_error=" + _EMBED_STATS["last_error"])
                                if _EMBED_STATS["last_error"] else "")
                except Exception as e:
                    logger.warning("[ssr] embedding 后台构建失败（降级关键词匹配）: %s", e)

            threading.Thread(target=_background_embed_build, name="ssr-embed-build",
                             daemon=True).start()
    except Exception as e:
        logger.warning("[ssr] embedding 索引加载失败（降级关键词匹配）: %s", e)
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
