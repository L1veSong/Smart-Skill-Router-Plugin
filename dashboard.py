"""
SSR Dashboard v0.3.0 — A 层规则 + B 层配置管理
启动: python3 ~/.hermes/plugins/ssr/dashboard.py
端口: 8766
"""
import json
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

RULES_PATH = Path(__file__).resolve().parent / "a_rules.json"
HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"
CONFIG_PATH = Path.home() / ".hermes" / "config.yaml"
MODEL_SCORES_PATH = Path(__file__).resolve().parent / "model_scores.json"


def load_rules():
    if not RULES_PATH.exists():
        return {}
    with open(RULES_PATH) as f:
        return json.load(f)


def save_rules(rules):
    with open(RULES_PATH, "w") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def load_config():
    """读取 ssr 配置节。"""
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f)
        ssr = cfg.get("ssr", {})
        b_layer = ssr.get("b_layer", {})
        return {
            "mode": ssr.get("mode", "suggest"),
            "scan": ssr.get("scan_mode", "startup"),
            "enabled": ssr.get("enabled", True),
            "b_provider": b_layer.get("provider", "main"),
            "b_model": b_layer.get("model", ""),
            "b_url": b_layer.get("base_url", ""),
            "b_timeout": b_layer.get("timeout", 30),
            "b_key": b_layer.get("api_key", ""),
        }
    except Exception:
        return {}


def save_config(data: dict):
    """写入 ssr 配置节到 config.yaml。"""
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}

        ssr = cfg.setdefault("ssr", {})

        if "mode" in data:
            ssr["mode"] = data["mode"]
        if "scan" in data:
            ssr["scan_mode"] = data["scan"]
        if "enabled" in data:
            ssr["enabled"] = data["enabled"]

        if "provider" in data:
            b_layer = ssr.setdefault("b_layer", {})
            b_layer["provider"] = data["provider"]
        if "model" in data:
            b_layer = ssr.setdefault("b_layer", {})
            b_layer["model"] = data["model"]
        if "base_url" in data:
            b_layer = ssr.setdefault("b_layer", {})
            b_layer["base_url"] = data["base_url"]
        if "timeout" in data:
            b_layer = ssr.setdefault("b_layer", {})
            b_layer["timeout"] = data["timeout"]
        if "api_key" in data:
            b_layer = ssr.setdefault("b_layer", {})
            b_layer["api_key"] = data["api_key"]

        with open(CONFIG_PATH, "w") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        return True
    except Exception as e:
        print(f"save_config error: {e}")
        return False


def _get_stats() -> dict:
    """获取 SSR 运行统计：索引健康 + 规则数。不读 agent.log（阻塞服务器）。"""
    import re

    stats = {
        "rules_count": len(load_rules()),
        "health": "unknown",
    }

    # 检查 embedding 索引文件
    embed_path = Path(__file__).resolve().parent / "embeddings.json"
    if embed_path.exists():
        try:
            with open(embed_path) as f:
                emb_data = json.load(f)
            stats["embedding_count"] = len(emb_data)
            stats["index_size_kb"] = round(embed_path.stat().st_size / 1024, 1)
        except Exception:
            stats["embedding_count"] = 0
    else:
        stats["embedding_count"] = 0

    # agent.log 行数太多（15K+），subprocess grep 阻塞单线程服务器 → 去掉
    # 命中率数据改为仅在 model-info 面板中展示
    stats["total_hits_log"] = -1
    stats["last_hit_rate"] = 0

    # 总体健康判定
    if stats.get("embedding_count", 0) > 0 and stats.get("rules_count", 0) > 0:
        stats["health"] = "healthy"
    elif stats.get("embedding_count", 0) > 0 or stats.get("rules_count", 0) > 0:
        stats["health"] = "degraded"
    else:
        stats["health"] = "empty"

    return stats


def load_model_scores() -> dict:
    """加载模型评分数据。"""
    if not MODEL_SCORES_PATH.exists():
        return {}
    with open(MODEL_SCORES_PATH) as f:
        return json.load(f)


def get_model_info() -> dict:
    """获取当前 embedding 模型信息 + 评分 + 已安装模型列表。"""
    import subprocess

    scores = load_model_scores()

    # 读取当前配置的模型名
    current_model = ""
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f)
        emb = cfg.get("ssr", {}).get("embedding", {})
        current_model = emb.get("model", "")
    except Exception:
        pass

    # 获取 Ollama 已安装的 embedding 模型
    installed_models = []
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n")[1:]:  # skip header
            parts = line.split()
            if parts:
                name = parts[0].replace(":latest", "")
                if any(
                    kw in name.lower()
                    for kw in ("embed", "bge", "nomic", "text2vec")
                ):
                    installed_models.append(name)
    except Exception:
        pass

    # 组装模型列表
    models = []
    for name, info in scores.items():
        status = "active" if name == current_model else (
            "installed" if name in installed_models else "available"
        )
        models.append({
            "name": name,
            "dimension": info["dimension"],
            "size_mb": info["size_mb"],
            "chinese_score": info["chinese_score"],
            "english_score": info["english_score"],
            "overall": info["overall"],
            "scenario_en": info["scenario_en"],
            "scenario_zh": info["scenario_zh"],
            "status": status,
        })

    cur = scores.get(current_model, {})

    return {
        "current_model": current_model,
        "current_dimension": cur.get("dimension", 0),
        "current_size_mb": cur.get("size_mb", 0),
        "chinese_score": cur.get("chinese_score", 0),
        "english_score": cur.get("english_score", 0),
        "overall": cur.get("overall", 0),
        "scenario_en": cur.get("scenario_en", ""),
        "scenario_zh": cur.get("scenario_zh", ""),
        "models": models,
    }


class SSRHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/rules":
            rules = load_rules()
            result = []
            for pat, rule in rules.items():
                entry = dict(rule)
                entry["pattern"] = pat
                result.append(entry)
            self._json(result)
        elif self.path == "/api/config":
            self._json(load_config())
        elif self.path == "/api/stats":
            self._json(_get_stats())
        elif self.path == "/api/model-info":
            self._json(get_model_info())
        elif self.path in ("/", "/index.html"):
            self._html()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/rules":
            body = self._body()
            rules = load_rules()
            pat = body.get("pattern", "").strip()
            if not pat:
                self._json({"ok": False, "error": "pattern required"}, 400)
                return
            rules[pat] = {
                "skills": body.get("skills", []),
                "hits": 0, "last_hit": "", "source": "manual", "priority": 10,
            }
            save_rules(rules)
            self._json({"ok": True, "count": len(rules)})
        elif self.path == "/api/rules/reset":
            save_rules({})
            self._json({"ok": True})
        elif self.path == "/api/config":
            body = self._body()
            ok = save_config(body)
            self._json({"ok": ok})
        elif self.path == "/api/benchmark":
            self._json(_run_benchmark())
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path.startswith("/api/rules/"):
            old_pat = self.path.split("/api/rules/", 1)[1]
            body = self._body()
            rules = load_rules()
            if old_pat not in rules:
                self._json({"ok": False, "error": "rule not found"}, 404)
                return
            new_pat = body.get("pattern", old_pat)
            rule = rules.pop(old_pat)
            for k in ("skills", "hits", "last_hit", "source", "priority"):
                if k in body:
                    rule[k] = body[k]
            rules[new_pat] = rule
            save_rules(rules)
            self._json({"ok": True, "count": len(rules)})
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/rules/"):
            pat = self.path.split("/api/rules/", 1)[1]
            rules = load_rules()
            if pat not in rules:
                self._json({"ok": False, "error": "rule not found"}, 404)
                return
            del rules[pat]
            save_rules(rules)
            self._json({"ok": True, "count": len(rules)})
        else:
            self.send_error(404)

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _html(self):
        try:
            with open(HTML_PATH) as f:
                html = f.read()
        except Exception:
            html = "<h1>SSR Dashboard</h1><p>dashboard.html not found</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length > 0 else {}

    def log_message(self, format, *args):
        pass


def _run_benchmark() -> dict:
    """跑 test_ssr.py，解析 GREEN 基准结果。"""
    import subprocess
    test_path = Path.home() / ".hermes/skills/software-development/smart-skill-router/tests/ssr_tdd_baseline_test.py"
    if not test_path.exists():
        return {"ok": False, "error": "test_ssr.py not found"}

    try:
        result = subprocess.run(
            ["python3", str(test_path)],
            capture_output=True, text=True, timeout=60,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Benchmark timed out (30s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # 解析 TDD 测试输出
    import re
    scenes = []
    kw_score = emb_score = "?/5"
    emb_model = "?"

    # A 层分数: A层: X/5
    m = re.search(r"A层:\s*(\d+)/5", output)
    if m:
        kw_score = m.group(1) + "/5"

    # Embedding 分数和模型名 (匹配 📊 bge-large-zh-v1.5: 5/5 行)
    m = re.search(r"bge-[\w.-]+:\s+(\d+)/5", output)
    if m:
        emb_score = m.group(1) + "/5"
    # Embedding 模型名
    m = re.search(r"(bge-[\w.-]+):\s+\d+/5", output)
    if m:
        emb_model = m.group(1)

    # 逐场景解析: 场景 N: 标题\n...\nA层命中: [...] (✅|❌)
    scene_re = re.compile(
        r"场景 (\d+): (.+?)\n.*?A层命中: \[(.+?)\] (✅|❌)",
        re.DOTALL
    )
    for m in scene_re.finditer(output):
        scenes.append({
            "hit": m.group(4) == "✅",
            "name": m.group(2)[:60],
            "skills": [
                s.strip().strip("'\"")
                for s in m.group(3).split(",")
                if s.strip()
            ],
        })

    return {
        "ok": True,
        "keyword_score": kw_score,
        "embedding_score": emb_score,
        "embedding_model": emb_model,
        "scenes": scenes,
    }


def start(port=8766):
    server = HTTPServer(("127.0.0.1", port), SSRHandler)
    print(f"SSR Dashboard → http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    start()
