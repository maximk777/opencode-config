#!/usr/bin/env python3
"""Local htmx console that reassigns tier files to models listed by `opencode models`."""
import html
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOST, PORT = "127.0.0.1", 7777
ALLOWED_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


def opencode_models():
    return subprocess.run(["opencode", "models"], capture_output=True, text=True, timeout=120).stdout


def list_models(runner=opencode_models):
    return [l.strip() for l in runner().splitlines() if "/" in l.strip() and " " not in l.strip()]


def read_tiers(repo=REPO):
    return {p.name: p.read_text().strip() for p in sorted((Path(repo) / "tiers").iterdir()) if p.is_file()}


def repo_git(*args):
    subprocess.run(["git", "-C", str(REPO), *args], check=True, capture_output=True)


def write_tier(repo, name, model, models, git=repo_git):
    tiers = read_tiers(repo)
    if name not in tiers:
        raise ValueError(f"unknown tier {name}")
    if model not in models:
        raise ValueError(f"unknown model {model}")
    (Path(repo) / "tiers" / name).write_text(model + "\n")
    git("add", f"tiers/{name}")
    git("commit", "-m", f"chore(tiers): set {name} to {model.split('/', 1)[1]}", "--", f"tiers/{name}")


def render_row(name, current, models):
    options = "".join(
        f'<option value="{html.escape(m)}"{" selected" if m == current else ""}>{html.escape(m)}</option>' for m in models
    )
    return (
        f'<tr id="tier-{name}"><td>{name}</td><td>{html.escape(current)}</td>'
        f'<td><form hx-post="/tier/{name}" hx-target="#tier-{name}" hx-swap="outerHTML">'
        f'<select name="model">{options}</select> <button>Assign</button></form></td></tr>'
    )


class Handler(BaseHTTPRequestHandler):
    models = []

    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/static/htmx.min.js":
            return self.send(200, (REPO / "console" / "static" / "htmx.min.js").read_bytes(), "application/javascript")
        if self.path != "/":
            return self.send(404, "not found")
        rows = "".join(render_row(n, m, self.models) for n, m in read_tiers().items())
        page = (REPO / "console" / "templates" / "index.html").read_text().replace("{{rows}}", rows)
        self.send(200, page)

    def do_POST(self):
        # A browser always sends Origin on cross-site POSTs; requests without it (curl) come from this machine anyway.
        origin = self.headers.get("Origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return self.send(403, "forbidden origin")
        if not self.path.startswith("/tier/"):
            return self.send(404, "not found")
        name = self.path.rsplit("/", 1)[1]
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        model = form.get("model", [""])[0]
        try:
            write_tier(REPO, name, model, self.models)
        except (ValueError, subprocess.CalledProcessError) as e:
            return self.send(400, f'<tr id="tier-{name}"><td colspan="3">error: {html.escape(str(e))}</td></tr>')
        self.send(200, render_row(name, model, self.models))


def main():
    Handler.models = list_models()
    print(f"model console on http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
