#!/usr/bin/env python3
"""
SSR 无极阈值校准 — 实测 embedding 分布，输出公式参数。

用法:
    python3 calibrate_floor.py

输出:
    noise_baseline: 噪音消息的平均余弦相似度
    signal_avg:     信号消息的平均余弦相似度
    → floor = noise_baseline + (signal_avg - noise_baseline) × 0.25

写入 model_scores.json 的对应条目，后续 _similarity_floor() 自动读取。
"""

import json, math, os, sys, time
from pathlib import Path

import requests
import yaml

HOME = Path.home()
CONFIG_PATH = HOME / ".hermes" / "config.yaml"
SSR_DIR = HOME / ".hermes" / "plugins" / "ssr"

with open(CONFIG_PATH) as f:
    cfg = yaml.safe_load(f)

ssr_cfg = cfg.get("ssr", {})
emb_cfg = ssr_cfg.get("embedding", {})

PROVIDER = emb_cfg.get("provider", "ollama")
MODEL = emb_cfg.get("model", "bge-large-zh-v1.5")
TIMEOUT = emb_cfg.get("timeout", 30)
API_KEY = emb_cfg.get("api_key", "")
BASE_URL = emb_cfg.get("base_url", "https://api.siliconflow.cn/v1").rstrip("/")

# ── 校准消息集（10 噪音 + 10 信号）──
NOISE_MSGS = [
    "嗯嗯", "哦", "好的", "谢谢", "行吧",
    "今天天气怎么样", "你觉得呢", "哈哈", "周末去哪玩", "...",
]
SIGNAL_MSGS = [
    "帮我设计一个暗色仪表盘", "这段代码报KeyError", "分析股票均线走势",
    "帮我写论文", "部署到Vercel", "生成PPT汇报",
    "画中国地图", "规划自驾路线", "优化慢SQL", "帮我配置环境变量",
]


def embed_text(text: str) -> list:
    """调用 embedding API。"""
    if PROVIDER == "ollama":
        resp = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": MODEL, "prompt": text},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("embedding", [])
    elif PROVIDER in ("siliconflow", "openai"):
        headers = {"Content-Type": "application/json"}
        if API_KEY:
            headers["Authorization"] = f"Bearer {API_KEY}"
        endpoint = f"{BASE_URL}/embeddings" if PROVIDER == "siliconflow" else f"{BASE_URL}/v1/embeddings"
        resp = requests.post(
            endpoint,
            headers=headers,
            json={"model": MODEL, "input": text},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [{}])
            return data[0].get("embedding", []) if data else []
    elif PROVIDER == "main":
        # Hermes main model doesn't support embeddings, fallback
        return []
    return []


def cosine_sim(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def main():
    # Load embedding index
    emb_path = SSR_DIR / "embeddings.json"
    if not emb_path.exists():
        print("ERROR: embeddings.json 不存在，请先运行 SSR 初始化", file=sys.stderr)
        sys.exit(1)
    emb_index = json.loads(emb_path.read_text())

    # Get the model name as it appears in model_scores.json
    # Try to match MODEL against known names
    scores_path = SSR_DIR / "model_scores.json"
    scores = json.loads(scores_path.read_text()) if scores_path.exists() else {}

    noise_sims = []
    signal_sims = []

    print(f"校准 embedding 模型: {MODEL} (provider: {PROVIDER})")
    print(f"消息集: {len(NOISE_MSGS)} 噪音 + {len(SIGNAL_MSGS)} 信号\n")

    # ── 噪音消息 ──
    print("── 噪音消息 ──")
    for i, msg in enumerate(NOISE_MSGS):
        vec = embed_text(msg)
        if not vec:
            print(f"  [{i+1}] \"{msg[:20]}\" → 向量获取失败，跳过")
            continue
        # 取与所有 skill 的最大余弦相似度
        max_sim = 0.0
        for skill_name, entry in emb_index.items():
            if "embedding" in entry:
                sim = cosine_sim(vec, entry["embedding"])
                max_sim = max(max_sim, sim)
        noise_sims.append(max_sim)
        print(f"  [{i+1}] \"{msg[:20]}\" → max_sim={max_sim:.4f}")
        time.sleep(0.1)  # rate limit

    # ── 信号消息 ──
    print("\n── 信号消息 ──")
    for i, msg in enumerate(SIGNAL_MSGS):
        vec = embed_text(msg)
        if not vec:
            print(f"  [{i+1}] \"{msg[:20]}\" → 向量获取失败，跳过")
            continue
        max_sim = 0.0
        for skill_name, entry in emb_index.items():
            if "embedding" in entry:
                sim = cosine_sim(vec, entry["embedding"])
                max_sim = max(max_sim, sim)
        signal_sims.append(max_sim)
        print(f"  [{i+1}] \"{msg[:20]}\" → max_sim={max_sim:.4f}")
        time.sleep(0.1)

    if not noise_sims or not signal_sims:
        print("\nERROR: 向量获取失败，无法校准", file=sys.stderr)
        sys.exit(1)

    noise_baseline = sum(noise_sims) / len(noise_sims)
    signal_avg = sum(signal_sims) / len(signal_sims)
    floor = noise_baseline + (signal_avg - noise_baseline) * 0.25

    print(f"\n═══ 校准结果 ═══")
    print(f"noise_baseline: {noise_baseline:.4f}")
    print(f"signal_avg:     {signal_avg:.4f}")
    print(f"→ floor:       {floor:.4f}  (公式: noise + (signal-noise) × 0.25)")

    # ── 写入 model_scores.json ──
    # Find or create entry for this model
    matched_key = None
    for name in scores:
        if name in MODEL or MODEL in name:
            matched_key = name
            break

    if not matched_key:
        matched_key = MODEL.split("/")[-1] if "/" in MODEL else MODEL

    if matched_key not in scores:
        scores[matched_key] = {}

    scores[matched_key]["noise_baseline"] = round(noise_baseline, 4)
    scores[matched_key]["signal_avg"] = round(signal_avg, 4)
    scores[matched_key]["calibrated_floor"] = round(floor, 4)
    scores[matched_key]["calibrated_at"] = time.strftime("%Y-%m-%d")

    scores_path.write_text(json.dumps(scores, ensure_ascii=False, indent=2))
    print(f"\n已写入 model_scores.json → {matched_key}")
    print("SSR 重启后 _similarity_floor() 将自动使用校准值。")


if __name__ == "__main__":
    main()
