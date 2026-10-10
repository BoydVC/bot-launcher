#!/usr/bin/env python3
"""Bot Launcher server (stdlib). Rebuilds catalog on start; serves on PORT (default 4262).
Routes: / , /api/catalog.json , /healthz , /tm/<shelf file> (only README/snapshot listed on shelf)."""
import http.server, json, os, sys, mimetypes, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
TM = "/workspace/tokenmax"
PORT = int(os.environ.get("PORT", "4262"))
subprocess.run([sys.executable, os.path.join(HERE, "build.py")], check=False)


def catalog():
    with open(os.path.join(HERE, "data", "catalog.json")) as f:
        return json.load(f)


class H(http.server.BaseHTTPRequestHandler):
    def send(self, code, body, ctype):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            c = catalog()
            tpl = open(os.path.join(HERE, "web", "index.html"), encoding="utf-8").read()
            page = (
                tpl.replace("/*__CATALOG__*/null", json.dumps(c).replace("</", "<\\/"))
                .replace("__BASE__", "/tm/")
            )
            return self.send(200, page, "text/html; charset=utf-8")
        if path == "/api/catalog.json":
            return self.send(200, json.dumps(catalog(), indent=1), "application/json")
        if path == "/healthz":
            return self.send(200, "bot-launcher ok", "text/plain")
        if path.startswith("/tm/"):
            rel = path[4:]
            allowed = {p for s in catalog()["shelf"] for p in (s.get("readme"), s.get("snapshot")) if p}
            if rel in allowed:
                fp = os.path.join(TM, rel)
                ctype = "text/plain; charset=utf-8" if rel.endswith(".md") else (
                    mimetypes.guess_type(fp)[0] or "application/octet-stream"
                )
                if ctype == "text/html":
                    ctype += "; charset=utf-8"
                return self.send(200, open(fp, "rb").read(), ctype)
        self.send(404, "not found", "text/plain")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
