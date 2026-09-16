#!/usr/bin/env python3
"""
SSR 三维评分系统 — 调用真实 SSR plugin 测试

用法:
    python3 ssr_scoring_benchmark.py --mode total      # 全链路 (真实SSR)
    python3 ssr_scoring_benchmark.py --mode embedding  # embedding模型对比 (独立)
    python3 ssr_scoring_benchmark.py --mode gate       # 门控测试 (本地模型)
    python3 ssr_scoring_benchmark.py --mode all        # 三个一起

设计原则:
    - total/gate 直接 import 真实 SSR plugin，调用 _match_a_layer / _intent_gate
    - embedding 独立测试 — 测模型不是测代码，用户换模型对比用
    - 零硬编码: 模型名/端点/阈值全部从 config.yaml 读取
    - 50 条固定基准 (30信号+20噪音)，零隐私
"""

import argparse, json, math, os, re, sys, time
from pathlib import Path

import requests
import yaml

HOME = Path.home()
CONFIG_PATH = HOME / ".hermes" / "config.yaml"

# ═══════════════════════════════════════════
# 0. 配置
# ═══════════════════════════════════════════
with open(CONFIG_PATH) as f:
    cfg = yaml.safe_load(f)
ssr_cfg = cfg.get("ssr", {})

emb_cfg = ssr_cfg.get("embedding", {})
EMB_PROVIDER = emb_cfg.get("provider", "ollama")
EMB_MODEL = emb_cfg.get("model", "bge-large-zh-v1.5")
EMB_TIMEOUT = emb_cfg.get("timeout", 15)

gate_cfg = ssr_cfg.get("intent_gate", {})
GATE_ENABLED = gate_cfg.get("enabled", False)
GATE_PROVIDERS = gate_cfg.get("providers", [])
GATE_ON_ERROR = gate_cfg.get("on_error", "pass")

SIM_FLOOR = float(ssr_cfg.get("similarity_floor", 0.35))
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


# ═══════════════════════════════════════════
# 1. 导入真实 SSR plugin
# ═══════════════════════════════════════════
_SSR_MODULE = None

def _init_ssr():
    """初始化 SSR plugin 模块。成功返回 module，失败返回 None。"""
    global _SSR_MODULE
    if _SSR_MODULE is not None:
        return _SSR_MODULE

    plugin_path = HOME / ".hermes" / "plugins" / "ssr" / "__init__.py"
    if not plugin_path.exists():
        return None

    import importlib.util
    spec = importlib.util.spec_from_file_location("ssr_plugin", str(plugin_path))
    mod = importlib.util.module_from_spec(spec)

    # Mock context
    class _MockCtx:
        config_path = str(CONFIG_PATH)
        plugin_dir = str(plugin_path.parent)
        @staticmethod
        def register_hook(*args, **kwargs):
            pass

    try:
        spec.loader.exec_module(mod)
        mod._CONFIG_CACHE = ssr_cfg
        mod._CONFIG_PATH = str(CONFIG_PATH)
        mod._SKILL_INDEX, mod._BROKEN_SKILLS = mod._build_skill_index()
        mod._A_RULES = mod._load_a_rules()
        mod._cleanup_a_rules()
        existing = mod._load_embedding_index()
        mod._EMBEDDING_INDEX = existing if existing else {}
        _SSR_MODULE = mod
        return mod
    except Exception as e:
        print(f"[WARN] SSR plugin 初始化失败: {e}", file=sys.stderr)
        return None


# ═══════════════════════════════════════════
# 2. Embedding 独立测试（模型对比用）
# ═══════════════════════════════════════════
def _load_embeddings():
    p = HOME / ".hermes" / "plugins" / "ssr" / "embeddings.json"
    return json.loads(p.read_text()) if p.exists() else {}

def _embed_text(text: str) -> list:
    try:
        if EMB_PROVIDER == "ollama":
            resp = requests.post(f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMB_MODEL, "prompt": text}, timeout=EMB_TIMEOUT)
            if resp.status_code == 200:
                return resp.json().get("embedding", [])
        elif EMB_PROVIDER == "siliconflow":
            sf_key = emb_cfg.get("api_key", "")
            sf_base = emb_cfg.get("base_url", "https://api.siliconflow.cn/v1").rstrip("/")
            resp = requests.post(f"{sf_base}/embeddings",
                headers={"Authorization": f"Bearer {sf_key}", "Content-Type": "application/json"},
                json={"model": EMB_MODEL, "input": [text]}, timeout=EMB_TIMEOUT)
            if resp.status_code == 200:
                return resp.json().get("data", [{}])[0].get("embedding", [])
        # openai 等其他 provider 后续扩展
    except Exception:
        pass
    return []

def _cosine(a, b):
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    return dot/(na*nb) if na>0 and nb>0 else 0.0

def embedding_search(msg_vec, emb_data, top_n=12, sim_floor=None):
    floor = sim_floor if sim_floor is not None else SIM_FLOOR
    scores = []
    for name, entry in emb_data.items():
        if "embedding" not in entry:
            continue
        sim = _cosine(msg_vec, entry["embedding"])
        if sim >= floor:
            scores.append((sim, name))
    scores.sort(reverse=True)
    return [n for _,n in scores[:top_n]]


# ═══════════════════════════════════════════
# 3. 门控测试（本地 Ollama 模型）
# ═══════════════════════════════════════════
def gate_classify_local(msg: str) -> bool:
    """使用本地 Ollama 模型做意图二分类
    
    从 intent_gate.providers 中找 ollama provider，调用本地模型。
    找不到 ollama provider → 返回 True (放行)。
    """
    ollama_prov = None
    for p in GATE_PROVIDERS:
        if p.get("provider") == "ollama":
            ollama_prov = p
            break
    if not ollama_prov:
        return True  # 无本地模型，放行

    model = ollama_prov.get("model", "")
    timeout = ollama_prov.get("timeout", 5)
    if not model:
        return True

    prompt = (
        "判断这条消息是否需要加载AI技能来完成。只回答YES或NO，不要解释。\n"
        f"消息: {msg}\n"
        "回答(YES/NO):"
    )
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "think": False},
            timeout=timeout)
        if resp.status_code == 200:
            answer = resp.json().get("response", "").strip().upper()
            return "YES" in answer
    except Exception:
        pass
    return True  # 超时/错误 → 放行


# ═══════════════════════════════════════════
# 4. 50 条基准数据
# ═══════════════════════════════════════════
BENCHMARK_DATA = [
    # ═══ 信号 30 条 ═══
    # 格式: (类别, 消息, 精准匹配, 相关可接受)
    # 设计×4
    ("信号-设计", "帮我设计一个暗色仪表盘",
     ["brainstorming", "ui-ux-pro-max", "frontend-design", "design-taste-frontend"],
     ["canvas-design", "dashboard", "design-html"]),
    ("信号-设计", "帮我设计一个响应式导航栏",
     ["brainstorming", "ui-ux-pro-max", "frontend-design"],
     ["canvas-design", "frontend-design"]),
    ("信号-设计", "帮我改一下这个按钮的颜色",
     ["ui-ux-pro-max", "frontend-design", "redesign-existing-projects"],
     ["canvas-design"]),
    ("信号-设计", "帮我设计一个登录页面",
     ["brainstorming", "ui-ux-pro-max", "frontend-design", "high-end-visual-design"],
     ["canvas-design", "design-taste-frontend"]),

    # 调试×3
    ("信号-调试", "这段Python代码报KeyError帮我看看",
     ["diagnose", "systematic-debugging", "code-simplifier"],
     ["python-debugpy", "delegate-reasonix"]),
    ("信号-调试", "函数返回None排查一下为什么",
     ["diagnose", "systematic-debugging"],
     ["delegate-reasonix", "python-debugpy"]),
    ("信号-调试", "接口超时怎么解决",
     ["diagnose", "systematic-debugging"],
     ["free-api-integration", "openwebui-hermes-performance-diagnosis"]),

    # 金融×2
    ("信号-金融", "分析贵州茅台的均线走势",
     ["technical-analysis", "tushare-finance", "stock-screen-monitor"],
     []),
    ("信号-金融", "北向资金最近流向怎么样",
     ["tushare-finance", "finance-news-analyzer", "stock-screen-monitor"],
     []),

    # 旅行×2
    ("信号-旅行", "规划北京自驾到南昌的路线",
     ["road-trip-planner", "travel-skill", "trip-planner-generator"],
     []),
    ("信号-旅行", "帮我规划三天上海旅游攻略",
     ["travel-skill", "travel-plan-html-editor", "trip-website-generator"],
     []),

    # 学术×2
    ("信号-学术", "帮我写论文的文献综述部分",
     ["research-paper-writing", "survey", "paper-spine-research"],
     ["nature-writing", "academic-pipeline", "deep-research", "academic-paper", "nature-academic-search"]),
    ("信号-学术", "帮我把这段文字降重",
     ["research-paper-writing", "paper-spine-humanize"],
     ["paper-spine-rewrite", "nature-polishing"]),

    # 部署×2
    ("信号-部署", "部署网站到Vercel",
     ["deploy-to-vercel"],
     ["vercel-cli-with-tokens"]),
    ("信号-部署", "用Docker部署后端服务",
     ["hermes-s6-container-supervision"],
     []),

    # PPT×2
    ("信号-PPT", "生成季度PPT汇报",
     ["pptx", "powerpoint"],
     []),
    ("信号-PPT", "做一份产品介绍演示文稿",
     ["pptx", "powerpoint"],
     []),

    # 地图×2
    ("信号-地图", "画中国地图显示GDP分布",
     ["geographic-visualization", "svg-geo-map", "geojson-svg-map", "geographic-viz"],
     []),
    ("信号-地图", "帮我做一张旅游路线图",
     ["svg-geo-map", "geojson-svg-map", "geographic-visualization", "travel-skill"],
     []),

    # ASCII×1
    ("信号-ASCII", "画一个ASCII猫咪",
     ["ascii-art"],
     []),

    # 微信×1
    ("信号-微信", "发微信给朋友说晚点到",
     ["wechat-desktop-send"],
     []),

    # 通用×9
    ("信号-通用", "写一个Python脚本处理CSV文件",
     ["xlsx", "code-simplifier", "writing-plans"],
     []),
    ("信号-通用", "帮我分析Nginx日志",
     ["diagnose", "hermes-memory-optimization"],
     ["openwebui-hermes-performance-diagnosis", "blogwatcher"]),
    ("信号-通用", "把这段翻译成英文", 
     [],
     ["paper-spine-translate", "lingo"]),
    ("信号-通用", "优化这个慢SQL",
     ["code-simplifier"],
     ["vercel-optimize", "skill-optimization-workflow"]),
    ("信号-通用", "解释一下这段代码", ["understand-explain"], []),
    ("信号-通用", "帮我配置一下环境变量", 
     [],
     ["hermes-platform-config", "application"]),
    ("信号-通用", "帮我想一个变量名", 
     [],
     ["brainstorming"]),
    ("信号-通用", "这个正则怎么匹配手机号", 
     [],
     ["code-simplifier", "brainstorming"]),
    ("信号-通用", "Git合并冲突怎么解决", ["using-git-worktrees"], []),

    # ═══ 噪音 20 条 ═══
    ("噪音-极短", "嗯嗯", None, None),
    ("噪音-极短", "哦", None, None),
    ("噪音-极短", "OK", None, None),
    ("噪音-寒暄", "谢谢你的帮助", None, None),
    ("噪音-寒暄", "好的我明白了", None, None),
    ("噪音-寒暄", "你觉得呢", None, None),
    ("噪音-寒暄", "今天天气怎么样", None, None),
    ("噪音-寒暄", "行吧", None, None),
    ("噪音-闲聊", "昨天看了个电影还不错", None, None),
    ("噪音-闲聊", "这个颜色好看吗", None, None),
    ("噪音-闲聊", "你觉得哪个好", None, None),
    ("噪音-闲聊", "周末去哪玩", None, None),
    ("噪音-闲聊", "我饿了", None, None),
    ("噪音-反问", "能行吗", None, None),
    ("噪音-反问", "确定吗", None, None),
    ("噪音-反问", "真的假的", None, None),
    ("噪音-反问", "不是吧", None, None),
    ("噪音-无意义", "...", None, None),
    ("噪音-无意义", "？？？", None, None),
    ("噪音-无意义", "哈哈", None, None),
]

N_SIGNAL = sum(1 for _,_,e,_ in BENCHMARK_DATA if e is not None)
N_NOISE = sum(1 for _,_,e,_ in BENCHMARK_DATA if e is None)


# ═══════════════════════════════════════════
# 5. 评分引擎
# ═══════════════════════════════════════════

def run_total(ssr_mod, quick: bool = False) -> dict:
    """全链路：_match_a_layer → _llm_screen（真实 SSR 管线）。

    quick=True: 跳过所有 LLM 调用，纯 A 层匹配。零 API 依赖。
    """
    t0 = time.time()
    sig_hit = sig_top3 = noi_silent = 0
    exact_score = related_score = 0  # 三档评分
    max_possible = 0
    llm_used = 0
    gate_blocked = 0
    cat_hits = {}
    applicable = 0
    skipped = []

    for cat, msg, expected, acceptable in BENCHMARK_DATA:
        is_noise = expected is None
        cat_name = cat.split("-", 1)[1] if "-" in cat else cat
        if cat_name not in cat_hits:
            cat_hits[cat_name] = [0, 0, 0]  # [精准, 相关, 不相关]

        if not is_noise and (expected or acceptable):
            available = [e for e in expected if e in ssr_mod._EMBEDDING_INDEX]
            if acceptable:
                available_acc = [e for e in acceptable if e in ssr_mod._EMBEDDING_INDEX]
            else:
                available_acc = []
            if not available and not available_acc:
                skipped.append(f"{cat_name}:{expected}")
                continue
            expected = available
            acceptable = available_acc
            max_possible += 2  # 满分=精准2分

        # ① 意图门控 — quick 模式跳过，仅非 quick 时测噪音门控
        if is_noise:
            if not quick:
                try:
                    gate_pass = ssr_mod._intent_gate(msg)
                except Exception:
                    gate_pass = True
                if not gate_pass:
                    gate_blocked += 1
                    noi_silent += 1
                    cat_hits[cat_name][0] += 1
                continue
            else:
                # quick: 不测门控，噪音直接跳过
                continue
        else:
            applicable += 1
            cat_hits[cat_name][1] += 1

        # ② _match_a_layer
        try:
            candidates = ssr_mod._match_a_layer(msg)
        except Exception:
            candidates = None

        if candidates is None:
            continue

        cand_names = [r["name"] for r in candidates[:20]]

        # ③ LLM 筛选 — quick 模式或 llm_screen=false 时跳过
        use_llm = not quick and ssr_cfg.get("llm_screen", False)
        if use_llm:
            try:
                screened = ssr_mod._llm_screen(msg, cand_names)
                llm_used += 1
            except Exception:
                screened = None

            if screened is None:
                names = cand_names
            elif screened:
                names = [r["name"] for r in screened]
            else:
                names = []
        else:
            names = cand_names

        top3 = names[:3]
        # 三档评分: 精准(2分) > 相关(1分) > 不相关(0分)
        if expected and any(e in names for e in expected):
            exact_score += 2
            sig_hit += 1
            sig_top3 += 1 if any(e in top3 for e in expected) else 0
            cat_hits[cat_name][0] += 1
        elif acceptable and any(e in names for e in acceptable):
            related_score += 1
            sig_hit += 1
            cat_hits[cat_name][1] += 1
        else:
            cat_hits[cat_name][2] += 1

    return {
        "signal_hit": sig_hit, "signal_top3": sig_top3,
        "exact_score": exact_score, "related_score": related_score,
        "max_possible": max_possible,
        "noise_silent": noi_silent, "llm_calls": llm_used,
        "cat_hits": cat_hits, "applicable": applicable,
        "skipped": skipped, "gate_blocked": gate_blocked,
        "total_ms": int((time.time() - t0) * 1000),
    }


def run_embedding() -> dict:
    """Embedding 模型对比测试（独立，不依赖 SSR 代码）"""
    emb_data = _load_embeddings()
    if not emb_data:
        return None

    # 从 model_scores.json 加载当前模型的校准 floor
    model_scores_path = HOME / ".hermes" / "plugins" / "ssr" / "model_scores.json"
    model_scores = json.loads(model_scores_path.read_text()) if model_scores_path.exists() else {}
    model_key = EMB_MODEL.split("/")[-1] if "/" in EMB_MODEL else EMB_MODEL
    calibrated_floor = model_scores.get(model_key, {}).get("calibrated_floor", SIM_FLOOR)

    t0 = time.time()
    sig_hit = sig_top3 = noi_silent = 0
    applicable = 0

    for cat, msg, expected, _ in BENCHMARK_DATA:
        is_noise = expected is None
        
        if not is_noise and expected:
            available = [e for e in expected if e in emb_data]
            if not available:
                continue
            expected = available

        vec = _embed_text(msg)
        if not vec:
            if is_noise:
                noi_silent += 1
            continue

        top12 = embedding_search(vec, emb_data, top_n=12, sim_floor=calibrated_floor)
        top3 = top12[:3]

        if is_noise:
            if not top12:
                noi_silent += 1
        else:
            applicable += 1
            if expected and any(e in top12 for e in expected):
                sig_hit += 1
            elif not expected:
                sig_hit += 1
            if expected and any(e in top3 for e in expected):
                sig_top3 += 1
            elif not expected and top3:
                sig_top3 += 1

    return {
        "signal_hit": sig_hit, "signal_top3": sig_top3,
        "noise_silent": noi_silent, "applicable": applicable,
        "total_ms": int((time.time() - t0) * 1000),
    }


def run_gate() -> dict:
    """门控测试（本地 Ollama 模型）"""
    t0 = time.time()
    noi_ok = sig_ok = 0

    for cat, msg, expected, _ in BENCHMARK_DATA:
        answer = gate_classify_local(msg)
        if expected is None:  # 噪音 → 期望 NO
            if not answer:
                noi_ok += 1
        else:  # 信号 → 期望 YES
            if answer:
                sig_ok += 1

    return {
        "noise_correct": noi_ok, "signal_correct": sig_ok,
        "total_ms": int((time.time() - t0) * 1000),
    }


def compute_scores(results: dict, mode: str) -> dict:
    """三档评分：相关度(精准+相关) + 噪音 + 门控。"""
    scores = {}
    r = results.get(mode, {})

    if mode == "total" and r:
        ex = r.get("exact_score", 0)
        rel = r.get("related_score", 0)
        mx = r.get("max_possible", 1)
        relevance = (ex + rel) / mx * 100 if mx > 0 else 0
        noise_silent = r.get("noise_silent", 0)
        # quick 模式不测噪音 → 纯相关度评分；正常模式 → 相关度+噪音加权
        if noise_silent > 0:
            noise_rate = (noise_silent / N_NOISE) * 100 if N_NOISE else 0
            scores["total"] = round(relevance * 0.7 + noise_rate * 0.3, 1)
        else:
            scores["total"] = round(relevance, 1)

    if mode == "embedding" and r:
        n = r.get("applicable", N_SIGNAL)
        hit_rate = (r["signal_hit"] / n) * 100 if n else 0
        noise_count = N_NOISE - r["noise_silent"]
        noise_rate = 100 if noise_count == 0 else (50 if noise_count <= 2 else 0)
        scores["embedding"] = round(hit_rate * 0.6 + noise_rate * 0.4, 1)

    if mode == "gate" and r:
        noi_rate = (r["noise_correct"] / N_NOISE) * 100 if N_NOISE else 0
        sig_rate = (r["signal_correct"] / N_SIGNAL) * 100 if N_SIGNAL else 0
        scores["gate"] = round(noi_rate * 0.6 + sig_rate * 0.4, 1)

    return scores


def score_label(s: float) -> str:
    if s >= 90: return "优秀"
    if s >= 75: return "可用"
    if s >= 55: return "勉强"
    return "不可用"


# ═══════════════════════════════════════════
# 6. 主入口
# ═══════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="SSR 三维评分系统")
    parser.add_argument("--mode", choices=["total", "embedding", "gate", "all"], default="all")
    parser.add_argument("--quick", action="store_true", help="跳过 LLM 调用，纯 A 层匹配（零 API 依赖，任何用户可跑）")
    parser.add_argument("--json", action="store_true", help="纯 JSON 输出")
    args = parser.parse_args()

    ssr_mod = _init_ssr() if args.mode in ("total", "all") else None

    if args.mode in ("total",) and not ssr_mod:
        print("ERROR: 无法初始化 SSR plugin，total 模式不可用", file=sys.stderr)
        sys.exit(1)

    emb_data = _load_embeddings() if args.mode in ("embedding", "all") else {}
    if args.mode in ("embedding",) and not emb_data:
        print("ERROR: embeddings.json 为空", file=sys.stderr)
        sys.exit(1)

    t_start = time.time()
    results = {}

    if args.mode in ("total", "all"):
        results["total"] = run_total(ssr_mod, quick=args.quick)
    if args.mode in ("embedding", "all"):
        results["embedding"] = run_embedding()
    if args.mode in ("gate", "all"):
        results["gate"] = run_gate()

    scores = {}
    for m in ["total", "embedding", "gate"]:
        s = compute_scores(results, m)
        scores.update(s)

    elapsed = round(time.time() - t_start, 1)

    if args.json:
        output = {
            "config": {
                "embedding_model": EMB_MODEL,
                "embedding_provider": EMB_PROVIDER,
                "gate_enabled": GATE_ENABLED,
                "gate_providers": [p.get("model","") for p in GATE_PROVIDERS if p.get("provider")=="ollama"],
                "similarity_floor": SIM_FLOOR,
                "n_signal": N_SIGNAL, "n_noise": N_NOISE,
                "ssr_loaded": ssr_mod is not None,
            },
            "results": results,
            "scores": scores,
            "elapsed_sec": elapsed,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    print(f"SSR 三维评分系统")
    print(f"embedding: {EMB_MODEL}({EMB_PROVIDER}) | gate: {'开' if GATE_ENABLED else '关'} | SSR插件: {'已加载' if ssr_mod else '独立模式'}")
    print(f"基准: {N_SIGNAL}信号 + {N_NOISE}噪音 = {N_SIGNAL+N_NOISE}条\n")

    for mode, label in [("total", "总评分"), ("embedding", "embedding裸分"), ("gate", "门控裸分")]:
        r = results.get(mode)
        s = scores.get(mode)
        if r is None or s is None:
            continue
        print(f"═══ {label}: {s:.1f} ({score_label(s)}) ═══")
        if mode == "total":
            llm = r.get('llm_calls', 0)
            app = r.get('applicable', N_SIGNAL)
            skipped = r.get('skipped', [])
            gb = r.get('gate_blocked', 0)
            ex = r.get('exact_score', 0)
            rel = r.get('related_score', 0)
            mx = r.get('max_possible', 0)
            total_rel = ex + rel
            pct = total_rel / mx * 100 if mx > 0 else 0
            print(f"  相关度: {total_rel}/{mx} ({pct:.0f}%)  |  精准 {ex} + 相关 {rel}")
            print(f"  信号命中: {r['signal_hit']}/{app} | top-3: {r['signal_top3']}/{app}")
            print(f"  噪音静默: {r['noise_silent']}/{N_NOISE} | 门控拦: {gb} | LLM: {llm} | 延迟: {r['total_ms']}ms")
            ch = r.get('cat_hits', {})
            if ch:
                cats = sorted([(k, v[0], v[1], v[2]) for k, v in ch.items() if (v[0]+v[1]+v[2]) > 0],
                             key=lambda x: (x[1]*2+x[2])/max(x[1]+x[2]+x[3],1), reverse=True)
                parts = []
                for k, ex, rel, irr in cats:
                    total = ex + rel + irr
                    score = ex * 2 + rel
                    max_s = total * 2
                    icon = '✅' if irr == 0 else '⚠️' if ex + rel > 0 else '❌'
                    parts.append(f"{icon} {k} {score}/{max_s}")
                print(f"  分类: {'  '.join(parts)}")
            noise_ch = {k: v for k, v in ch.items() if (v[0]+v[1]+v[2]) == 0}
            if noise_ch:
                nparts = [f"{k} {v[0]}" for k, v in sorted(noise_ch.items())]
                print(f"  噪音: {' | '.join(nparts)}")
            if skipped:
                print(f"  跳过(未安装): {', '.join(skipped)}")
        elif mode == "embedding":
            n = r.get('applicable', N_SIGNAL)
            print(f"  信号命中: {r['signal_hit']}/{n} | top-3: {r['signal_top3']}/{n}")
            print(f"  噪音静默: {r['noise_silent']}/{N_NOISE} | 延迟: {r['total_ms']}ms")
        elif mode == "gate":
            print(f"  噪音正确: {r['noise_correct']}/{N_NOISE} | 信号正确: {r['signal_correct']}/{N_SIGNAL}")
            print(f"  延迟: {r['total_ms']}ms")
        print()

    print(f"总耗时: {elapsed}s")


if __name__ == "__main__":
    main()
