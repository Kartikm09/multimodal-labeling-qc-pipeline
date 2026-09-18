"""Single-user loopback review server. Synthetic data only; no remote deployment."""

import argparse
import json
import re
import sqlite3
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .review_store import ReviewStore
from .temporal import export_cvat

ROOT = Path(__file__).resolve().parents[2]
CASE_IDS = ("known-boundaries", "ambiguous-contact")


def create_server(database, host="127.0.0.1", port=8765):
    if host != "127.0.0.1":
        raise ValueError("this local reviewer binds only to 127.0.0.1")
    store = ReviewStore(database)
    for identifier in CASE_IDS:
        if not store.history(identifier):
            store.create(
                json.loads((ROOT / f"fixtures/temporal/{identifier}.json").read_text())
            )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, body, content_type="application/json", headers=None):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; script-src 'self'; media-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def allowed_host(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            if not self.allowed_host():
                self.send(403, {"error": "loopback Host required"})
                return
            path = urlsplit(self.path).path
            if path == "/api/cases":
                self.send(200, {"cases": list(CASE_IDS)})
                return
            pieces = path.strip("/").split("/")
            if (
                len(pieces) in [3, 4]
                and pieces[:2] == ["api", "cases"]
                and pieces[2] in CASE_IDS
            ):
                identifier = pieces[2]
                if len(pieces) == 4:
                    if pieces[3] == "export.json":
                        self.send(200, store.latest(identifier)["document"])
                        return
                    if pieces[3] == "export.xml":
                        self.send(
                            200,
                            export_cvat(store.latest(identifier)["document"]).encode(),
                            "application/xml",
                        )
                        return
                else:
                    self.send(
                        200,
                        {
                            "history": store.history(identifier),
                            "rankings": store.rankings(identifier),
                        },
                    )
                    return
            files = {
                "/": (ROOT / "web/index.html", "text/html"),
                "/app.js": (ROOT / "web/app.js", "application/javascript"),
                "/style.css": (ROOT / "web/style.css", "text/css"),
            }
            files.update(
                {
                    f"/media/{identifier}.mp4": (
                        ROOT / f"fixtures/temporal/{identifier}.mp4",
                        "video/mp4",
                    )
                    for identifier in CASE_IDS
                }
            )
            if path not in files:
                self.send(404, {"error": "unknown path"})
                return
            file, mime = files[path]
            body = file.read_bytes()
            if mime == "video/mp4":
                headers = {"Accept-Ranges": "bytes"}
                request = self.headers.get("Range")
                if request:
                    match = (
                        re.fullmatch(r"bytes=(\d*)-(\d*)", request)
                        if len(request) <= 100
                        else None
                    )
                    if not match or not any(match.groups()):
                        self.send(
                            416, b"", mime, {"Content-Range": f"bytes */{len(body)}"}
                        )
                        return
                    start_text, end_text = match.groups()
                    if start_text:
                        start = int(start_text)
                        end = (
                            min(int(end_text), len(body) - 1)
                            if end_text
                            else len(body) - 1
                        )
                    else:
                        count = int(end_text)
                        start = max(0, len(body) - count)
                        end = len(body) - 1
                    if not 0 <= start <= end < len(body):
                        self.send(
                            416, b"", mime, {"Content-Range": f"bytes */{len(body)}"}
                        )
                        return
                    headers["Content-Range"] = f"bytes {start}-{end}/{len(body)}"
                    self.send(206, body[start : end + 1], mime, headers)
                    return
                self.send(200, body, mime, headers)
                return
            self.send(200, body, mime)

        def do_POST(self):
            origin = f"http://127.0.0.1:{self.server.server_port}"
            if not self.allowed_host() or self.headers.get("Origin") not in [
                None,
                origin,
            ]:
                self.send(403, {"error": "local origin required"})
                return
            if self.headers.get("Content-Type") != "application/json":
                self.send(415, {"error": "JSON required"})
                return
            pieces = urlsplit(self.path).path.strip("/").split("/")
            if (
                len(pieces) != 4
                or pieces[:2] != ["api", "cases"]
                or pieces[2] not in CASE_IDS
            ):
                self.send(404, {"error": "unknown case"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1_000_000:
                    raise ValueError("bounded JSON body required")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
                identifier = pieces[2]
                if pieces[3] == "revisions":
                    result = store.revise(
                        identifier,
                        payload["document"],
                        reviewer=payload["reviewer"],
                        reason=payload["reason"],
                        expected_revision=payload["expected_revision"],
                    )
                    self.send(201, result)
                elif pieces[3] == "rankings":
                    store.rank(
                        identifier,
                        payload["left"],
                        payload["right"],
                        payload["preference"],
                        payload["evidence"],
                    )
                    self.send(201, {"rankings": store.rankings(identifier)})
                else:
                    self.send(404, {"error": "unknown action"})
            except (ValueError, TypeError, KeyError, sqlite3.IntegrityError) as error:
                self.send(
                    409 if "stale review" in str(error) else 400, {"error": str(error)}
                )

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("reviews.sqlite"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--ephemeral",
        action="store_true",
        help="Use a fresh temporary store for browser tests",
    )
    args = parser.parse_args()
    temporary = tempfile.TemporaryDirectory() if args.ephemeral else None
    database = Path(temporary.name) / "reviews.sqlite" if temporary else args.database
    server = create_server(database, port=args.port)
    print(f"Synthetic local review: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if temporary:
            temporary.cleanup()


if __name__ == "__main__":
    main()
