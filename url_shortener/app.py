"""
URL Shortener
-------------
Run:  python app.py
Open: http://localhost:8001
"""
import json
import os
import random
import sqlite3
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE  = os.path.join(BASE_DIR, "urls.db")


# ── Database ──────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code   TEXT    UNIQUE NOT NULL,
            original_url TEXT    NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            clicks       INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def shorten_url(original_url):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT short_code FROM urls WHERE original_url = ?", (original_url,))
    row = c.fetchone()
    if row:
        conn.close()
        return row[0]
    while True:
        code = generate_short_code()
        c.execute("SELECT id FROM urls WHERE short_code = ?", (code,))
        if not c.fetchone():
            break
    c.execute("INSERT INTO urls (short_code, original_url) VALUES (?, ?)", (code, original_url))
    conn.commit()
    conn.close()
    return code


def get_original_url(short_code):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT original_url FROM urls WHERE short_code = ?", (short_code,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?", (short_code,))
        conn.commit()
    conn.close()
    return row[0] if row else None


def get_all_urls():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT short_code, original_url, created_at, clicks FROM urls ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [{"short_code": r[0], "original_url": r[1], "created_at": r[2], "clicks": r[3]} for r in rows]


# ── HTTP Server ───────────────────────────────────────────────────────────────

HTML_PAGE = open(os.path.join(BASE_DIR, "index.html")).read()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress console logs

    def _json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())

        elif path == "/api/urls":
            self._json(get_all_urls())

        elif path.startswith("/s/"):
            original = get_original_url(path[3:])
            if original:
                self.send_response(302)
                self.send_header("Location", original)
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Short URL not found.")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        path = urlparse(self.path).path

        if path == "/api/shorten":
            url = body.get("url", "").strip()
            if not url:
                return self._json({"error": "URL is required."}, 400)
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            code = shorten_url(url)
            self._json({"short_code": code, "short_url": f"http://localhost:8001/s/{code}"})
        else:
            self.send_response(404)
            self.end_headers()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = 8001
    print(f"URL Shortener -> http://localhost:{port}")
    HTTPServer(("", port), Handler).serve_forever()
