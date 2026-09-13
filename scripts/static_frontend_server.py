from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class SpaHandler(SimpleHTTPRequestHandler):
    backend_url = ""
    browser_api_base = ""

    def _is_api_request(self) -> bool:
        return urlsplit(self.path).path == "/api" or urlsplit(self.path).path.startswith("/api/")

    def _proxy_api_request(self) -> None:
        target = f"{self.backend_url.rstrip('/')}{self.path}"
        body = None
        content_length = self.headers.get("Content-Length")
        if content_length:
            body = self.rfile.read(int(content_length))

        request_headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"connection", "content-length", "host", "transfer-encoding"}
        }
        request_headers["X-Forwarded-For"] = self.client_address[0]
        proxy_request = urllib.request.Request(
            target,
            data=body,
            headers=request_headers,
            method=self.command,
        )

        try:
            with urllib.request.urlopen(proxy_request, timeout=300) as response:
                self.send_response(response.status)
                self._copy_response_headers(response.headers)
                self.end_headers()
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as error:
            self.send_response(error.code)
            self._copy_response_headers(error.headers)
            self.end_headers()
            payload = error.read()
            if payload:
                self.wfile.write(payload)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            self._send_json_error(502, f"后端服务暂不可用：{error}")

    def _copy_response_headers(self, headers) -> None:
        for key, value in headers.items():
            if key.lower() in {"connection", "transfer-encoding"}:
                continue
            self.send_header(key, value)

    def _send_json_error(self, status: int, detail: str) -> None:
        payload = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_index(self) -> None:
        index_path = Path(self.directory or os.getcwd()) / "index.html"
        try:
            content = index_path.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404)
            return
        # API requests already travel through this server's same-origin proxy.
        # Keeping the browser base empty avoids a CORS failure whenever a
        # temporary local verification instance uses a different backend port.
        api_script = f"<script>window.__TIBAN_API_BASE__={json.dumps(self.browser_api_base)}</script>"
        content = content.replace("</head>", f"{api_script}</head>", 1)
        payload = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self._is_api_request():
            self._proxy_api_request()
            return
        requested = self.translate_path(self.path)
        if not os.path.exists(requested) or Path(requested).is_dir():
            self._serve_index()
            return
        super().do_GET()

    def do_POST(self) -> None:
        self._proxy_api_request() if self._is_api_request() else self.send_error(405)

    def do_PUT(self) -> None:
        self._proxy_api_request() if self._is_api_request() else self.send_error(405)

    def do_PATCH(self) -> None:
        self._proxy_api_request() if self._is_api_request() else self.send_error(405)

    def do_DELETE(self) -> None:
        self._proxy_api_request() if self._is_api_request() else self.send_error(405)

    def do_OPTIONS(self) -> None:
        self._proxy_api_request() if self._is_api_request() else self.send_error(405)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5174)
    parser.add_argument("--root", required=True)
    parser.add_argument("--backend-url", default=os.environ.get("TIBAN_BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--browser-api-base", default=os.environ.get("TIBAN_BROWSER_API_BASE", ""))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    SpaHandler.backend_url = args.backend_url
    SpaHandler.browser_api_base = args.browser_api_base.rstrip("/")
    os.chdir(root)
    server = ThreadingHTTPServer((args.host, args.port), SpaHandler)
    print(f"Serving {root} on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
