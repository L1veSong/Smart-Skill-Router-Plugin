"""
SSR Dashboard v0.2.0 — A 层规则 + B 层配置管理
启动: python3 ~/.hermes/plugins/ssr/dashboard.py
端口: 8766
"""
import json
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

RULES_PATH = Path(__file__).resolve().parent / "a_rules.json"
HTML_PATH = Path(__file__).resolve().parent / "dashboard.html"
CONFIG_PATH = Path.home() / ".hermes" / "config.yaml"


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


def start(port=8766):
    server = HTTPServer(("127.0.0.1", port), SSRHandler)
    print(f"SSR Dashboard → http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    start()
