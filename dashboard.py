"""
SSR Dashboard v3.0.2 — A 层规则 + B 层配置管理
启动: python3 ~/.hermes/plugins/ssr/dashboard.py
端口: 8768
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
        gate = ssr.get("intent_gate", {})
        providers = list(gate.get("providers", []))
        mc = cfg.get("model", {})
        for p in providers:
            if not p.get("model") and p.get("provider") == "main":
                p["model"] = mc.get("default", "")
        main_model = mc.get("default", "")
        emb_cfg = ssr.get("embedding", {})
        return {
            "mode": ssr.get("mode", "suggest"),
            "scan": ssr.get("scan_mode", "startup"),
            "enabled": ssr.get("enabled", True),
            "b_provider": b_layer.get("provider", "main"),
            "b_model": b_layer.get("model", ""),
            "b_url": b_layer.get("base_url", ""),
            "b_timeout": b_layer.get("timeout", 30),
            "b_key": b_layer.get("api_key", ""),
            "gate_enabled": gate.get("enabled", False),
            "gate_provider": gate.get("active", "ollama"),
            "gate_model": next((p.get("model", "") for p in gate.get("providers", []) if p.get("provider") == gate.get("active", "")), ""),

            "gate_url": gate.get("base_url", ""),
            "gate_key": gate.get("api_key", ""),
            "gate_providers": providers,
            "main_model": main_model,
            "emb_model": emb_cfg.get("model", ""),
            "emb_provider": emb_cfg.get("provider", ""),
            "emb_url": emb_cfg.get("base_url", ""),
            "emb_key": emb_cfg.get("api_key", ""),
            # v2.1 新增
            "llm_screen": ssr.get("llm_screen", False),
            "display": ssr.get("display", False),
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

        if "gate_provider" in data or "gate_model" in data or "gate_enabled" in data:
            gate = ssr.setdefault("intent_gate", {})
            if "gate_provider" in data:
                gate["active"] = data["gate_provider"]
            if "gate_model" in data:
                # 更新 providers 列表中匹配 active 的 model
                providers = gate.setdefault("providers", [])
                active = gate.get("active", "")
                found = False
                for p in providers:
                    if p.get("provider") == active:
                        p["model"] = data["gate_model"]; found = True; break
                if not found:
                    providers.append({"provider": active, "model": data["gate_model"]})
            if "gate_url" in data:
                gate["base_url"] = data["gate_url"]
            if "gate_key" in data:
                gate["api_key"] = data["gate_key"]
            if "gate_enabled" in data:
                gate["enabled"] = data["gate_enabled"]

        if "emb_model" in data:
            emb = ssr.setdefault("embedding", {})
            emb["model"] = data["emb_model"]
        if "emb_provider" in data:
            emb = ssr.setdefault("embedding", {})
            emb["provider"] = data["emb_provider"]
        if "emb_url" in data:
            emb = ssr.setdefault("embedding", {})
            emb["base_url"] = data["emb_url"]
        if "emb_key" in data:
            emb = ssr.setdefault("embedding", {})
            emb["api_key"] = data["emb_key"]

        # v2.1 新增字段
        if "llm_screen" in data:
            ssr["llm_screen"] = data["llm_screen"]
        if "display" in data:
            ssr["display"] = data["display"]

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

    # 组装模型列表 — 仅从 Ollama 已安装的
    seen = set()
    models = []
    # 先加当前配置的模型
    if current_model and current_model not in seen:
        seen.add(current_model)
        models.append({"name": current_model, "status": "active", "dimension": "", "size_mb": ""})
    # 再加 ollama 列表
    for name in installed_models:
        if name not in seen:
            seen.add(name)
            models.append({"name": name, "status": "installed", "dimension": "", "size_mb": ""})

    return {
        "current_model": current_model,
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
            entry = {
                "skills": body.get("skills", []),
                "hits": 0, "last_hit": "", "source": "manual", "priority": 10,
            }
            if body.get("phases"):
                entry["phases"] = body["phases"]
            rules[pat] = entry
            save_rules(rules)
            self._json({"ok": True, "count": len(rules)})
        elif self.path == "/api/rules/reset":
            # 重置前自动备份 a_rules.json（2026-09-20）
            try:
                import shutil, time
                if RULES_PATH.exists():
                    shutil.copy2(RULES_PATH, str(RULES_PATH) + ".bak." + time.strftime("%m%d%H%M"))
            except Exception:
                pass
            save_rules({})
            self._json({"ok": True})
        elif self.path == "/api/config":
            body = self._body()
            ok = save_config(body)
            self._json({"ok": ok})
        elif self.path == "/api/benchmark":
            self._json(_run_benchmark("all"))
        elif self.path == "/api/benchmark/total":
            self._json(_run_benchmark("total"))
        elif self.path == "/api/benchmark/embedding":
            self._json(_run_benchmark("embedding"))
        elif self.path == "/api/benchmark/gate":
            self._json(_run_benchmark("gate"))
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
            for k in ("skills", "phases", "hits", "last_hit", "source", "priority"):
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


def _run_benchmark(mode="all") -> dict:
    """跑三维评分系统 —— ssr_scoring_benchmark.py --mode <mode> --json"""
    import subprocess, json
    bench_path = Path(__file__).resolve().parent / "tests" / "ssr_scoring_benchmark.py"
    if not bench_path.exists():
        return {"ok": False, "error": "benchmark not found"}
    try:
        result = subprocess.run(
            ["python3", str(bench_path), "--mode", mode, "--json"],
            capture_output=True, text=True, timeout=300,
        )
        data = json.loads(result.stdout)
        return {"ok": True, **data}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def start(port=8768):
    server = HTTPServer(("127.0.0.1", port), SSRHandler)
    print(f"SSR Dashboard → http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    start()
