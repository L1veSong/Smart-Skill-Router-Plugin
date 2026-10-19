#!/usr/bin/env python3
"""
SSR GREEN 基准测试 — 验证双阈值过滤 + 关键词兜底
=====================================================
用法: python3 references/ssr-green-benchmark-v2.py

测试 5 个 GREEN 场景，模拟完整的 A 层匹配流程：
  1. 关键词精确匹配（re.search on a_rules.json keys）
  2. Embedding 语义匹配（Ollama bge-m3 1024维）
  3. 合并去重（关键词优先）
  4. 双阈值过滤（similarity_floor + confidence_threshold）
  5. 结果判定

依赖: Ollama 运行中，bge-m3 模型已 pull
阈值来源: ~/.hermes/config.yaml → ssr.similarity_floor / ssr.confidence_threshold
          未配置时默认: similarity_floor=0.35, confidence_threshold=0.40

GREEN 5 场景（来自 ssr-red-baseline.md）：
  1. "帮我设计一个响应式导航栏"      → brainstorming, ui-ux-pro-max, popular-web-designs
  2. "这段 Python 代码报 KeyError 帮我看看" → diagnose, systematic-debugging
  3. "生成一个 ASCII 猫咪图"         → ascii-art
  4. "帮我写论文的 Related Work 部分" → research-paper-writing, paper-spine-research
  5. "分析贵州茅台的均线走势"         → technical-analysis, tushare-finance

通过标准: ≥3/5, 目标: ≥4/5

历史结果:
  2026-06-09 v1 (force 模式, floor=0.25, conf=0.25): 5/5 — 全部关键词命中
  2026-06-09 v2 (双阈值, floor=0.35, conf=0.40):      5/5 — 关键词兜底，embedding 无影响
"""

import json
import math
import re
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

try:
    import requests
except ImportError:
    print("需要 requests: pip3 install requests")
    sys.exit(1)

# ── 路径 ──────────────────────────────────────────
SSR_DIR = Path.home() / ".hermes" / "plugins" / "ssr"
A_RULES_PATH = SSR_DIR / "a_rules.json"
EMBEDDINGS_PATH = SSR_DIR / "embeddings.json"
CONFIG_PATH = Path.home() / ".hermes" / "config.yaml"

# ── 默认阈值 ──────────────────────────────────────
SIMILARITY_FLOOR = 0.35
CONFIDENCE_THRESHOLD = 0.40


def load_config():
    """从 config.yaml 读取 SSR 配置中的阈值"""
    global SIMILARITY_FLOOR, CONFIDENCE_THRESHOLD
    if not CONFIG_PATH.exists() or yaml is None:
        return
    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {}
        ssr = cfg.get("ssr", {})
        SIMILARITY_FLOOR = ssr.get("similarity_floor", SIMILARITY_FLOOR)
        CONFIDENCE_THRESHOLD = ssr.get("confidence_threshold", CONFIDENCE_THRESHOLD)
    except Exception:
        pass


# ── bge-m3 Embedding ──────────────────────────────
def embed_text(text: str) -> list:
    """调用 Ollama bge-m3 获取 1024 维向量"""
    try:
        resp = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "bge-m3", "prompt": text},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("embedding", [])
    except Exception as e:
        print(f"  [WARN] Ollama embedding 失败: {e}")
    return []


def cosine_sim(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


# ── 阶段推断 ──────────────────────────────────────
PHASE_MAP = {
    "brainstorming": "DISCOVER",
    "ideation": "DISCOVER",
    "survey": "DISCOVER",
    "deep-research": "DISCOVER",
    "planning-with-files": "PLAN",
    "plan": "PLAN",
    "writing-plans": "PLAN",
    "ui-ux-pro-max": "BUILD",
    "popular-web-designs": "BUILD",
    "frontend-design": "BUILD",
    "ascii-art": "BUILD",
    "algorithmic-art": "BUILD",
    "diagnose": "VERIFY",
    "systematic-debugging": "VERIFY",
    "dogfood": "VERIFY",
    "tdd": "VERIFY",
    "verification-before-completion": "VERIFY",
    "research-paper-writing": "BUILD",
    "paper-spine-research": "DISCOVER",
    "academic-paper": "BUILD",
    "technical-analysis": "BUILD",
    "tushare-finance": "BUILD",
}


def infer_phase(name: str) -> str:
    return PHASE_MAP.get(name, "BUILD")


# ── GREEN 测试用例 ────────────────────────────────
TESTS = [
    (
        "UI设计",
        "帮我设计一个响应式导航栏",
        ["brainstorming", "ui-ux-pro-max", "popular-web-designs"],
    ),
    (
        "代码调试",
        "这段 Python 代码报 KeyError 帮我看看",
        ["diagnose", "systematic-debugging"],
    ),
    ("ASCII艺术", "生成一个 ASCII 猫咪图", ["ascii-art"]),
    (
        "学术写作",
        "帮我写论文的 Related Work 部分",
        ["research-paper-writing", "paper-spine-research"],
    ),
    (
        "金融分析",
        "分析贵州茅台的均线走势",
        ["technical-analysis", "tushare-finance"],
    ),
]


# ═══════════════════════════════════════════════════
def run():
    # 加载配置
    load_config()
    print(f"阈值: similarity_floor={SIMILARITY_FLOOR}, confidence_threshold={CONFIDENCE_THRESHOLD}")

    # 加载 A 层规则
    if not A_RULES_PATH.exists():
        print("❌ a_rules.json 不存在")
        sys.exit(1)
    a_rules = json.loads(A_RULES_PATH.read_text())
    print(f"A 层规则: {len(a_rules)} 条")

    # 加载 Embedding 索引
    if not EMBEDDINGS_PATH.exists():
        print("❌ embeddings.json 不存在")
        sys.exit(1)
    emb_data = json.loads(EMBEDDINGS_PATH.read_text())
    print(f"Embedding 索引: {len(emb_data)} skill\n")

    results = []
    for label, msg, expected in TESTS:
        print(f"{'='*60}")
        print(f"测试: {label} | {msg}")
        print(f"期望: {expected}")

        # Step 1: A 层关键词匹配
        keyword_hits = []
        for pattern_key, rule in a_rules.items():
            try:
                if re.search(pattern_key, msg, re.IGNORECASE):
                    for skill_info in rule.get("skills", []):
                        name = (
                            skill_info
                            if isinstance(skill_info, str)
                            else skill_info.get("name", "")
                        )
                        phase = (
                            skill_info.get("phase", "")
                            if isinstance(skill_info, dict)
                            else infer_phase(name)
                        )
                        keyword_hits.append(
                            {"name": name, "phase": phase, "_source": "keyword"}
                        )
            except re.error:
                continue
        print(f"  关键词: {[h['name'] for h in keyword_hits]}")

        # Step 2: Embedding 语义匹配
        emb_hits = []
        msg_vec = embed_text(msg)
        if msg_vec and len(msg_vec) > 10:
            scores = []
            for name, entry in emb_data.items():
                if "embedding" not in entry:
                    continue
                sim = cosine_sim(msg_vec, entry["embedding"])
                if sim >= SIMILARITY_FLOOR:
                    scores.append((sim, name))
            scores.sort(reverse=True)
            for sim, name in scores[:30]:
                emb_hits.append(
                    {
                        "name": name,
                        "phase": infer_phase(name),
                        "_sim": round(sim, 4),
                        "_source": "embedding",
                    }
                )
        top5 = [(h["name"], h["_sim"]) for h in emb_hits[:5]]
        print(f"  Emb top-5: {top5}")

        # Step 3: 合并去重
        seen = set()
        merged = []
        for h in keyword_hits:
            if h["name"] not in seen:
                seen.add(h["name"])
                merged.append(h)
        for h in emb_hits:
            if h["name"] not in seen:
                seen.add(h["name"])
                merged.append(h)

        # Step 4: 置信度
        emb_sims = sorted(
            [h["_sim"] for h in merged if "_sim" in h], reverse=True
        )
        conf = 1.0 if not emb_sims else sum(emb_sims[:3]) / len(emb_sims[:3])
        pass_thresh = conf >= CONFIDENCE_THRESHOLD

        # Step 5: 判定
        hit_exp = [e for e in expected if e in [h["name"] for h in merged]]
        score = len(hit_exp) / len(expected) if expected else 0
        status = "✅" if pass_thresh and score >= 0.5 else "❌"

        print(f"  合并 ({len(merged)}): {[h['name'] for h in merged][:10]}...")
        print(f"  置信度={conf:.4f} 命中={hit_exp} {score:.0%} → {status}")
        print()

        results.append(
            {
                "label": label,
                "expected": expected,
                "hits": [h["name"] for h in merged],
                "confidence": conf,
                "pass_threshold": pass_thresh,
                "hit_score": score,
                "status": "PASS" if status == "✅" else "FAIL",
            }
        )
        time.sleep(0.3)

    # 汇总
    print(f"{'='*60}")
    print(
        f"GREEN 基准汇总 (floor={SIMILARITY_FLOOR}, conf={CONFIDENCE_THRESHOLD})"
    )
    print(f"{'='*60}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    for r in results:
        kw_ratio = sum(
            1 for h in r["hits"] if h in r["expected"]
        ) / len(r["expected"])
        print(
            f"  {r['status']:4s} | {r['label']:8s} "
            f"| conf={r['confidence']:.4f} "
            f"| 命中={kw_ratio:.0%} "
            f"| {[h for h in r['hits'][:5] if h in r['expected']]}"
        )
    print(f"\n通过: {passed}/{len(results)} "
          f"(≥3 及格, ≥4 目标)")
    return 0 if passed >= 3 else 1


if __name__ == "__main__":
    sys.exit(run())
