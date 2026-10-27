"""TEST HARNESS ONLY. Invented SSO + Duo pages on 127.0.0.1 to exercise the login flow.

Not the real login service. Accepts one invented user/password pair.
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

GOOD = ("test-user", "test-pass-not-real")


LOGIN_FORM = ('<h1>Sign in</h1><form method="post" action="/login">'
              '<input name="u" type="text" placeholder="Username"><input name="p" type="password" placeholder="Password">'
              '<button type="submit">Log in</button></form>')
DUO_BODY = "<h1>Two-factor</h1><p>Check for a Duo Push on your phone</p>"
TRUST_BODY = '<h1>Is this your device?</h1><a href="/trust"><button>Yes, this is my device</button></a>'


def page(state, body=""):
    return "<html><body data-state=\"%s\">%s</body></html>" % (state, body)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _html(self, html, code=200, headers=None):
        data = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        s = self.server
        s.hits.append(("GET", self.path))
        authed = "sid=ok" in (self.headers.get("Cookie") or "")
        if self.path.startswith("/app"):
            self._html(page("logged_in", "<h1>Welcome</h1>") if authed else page("login_form", LOGIN_FORM))
        elif self.path.startswith("/duo"):
            if s.duo_approved:
                self._html(page("duo_trust_prompt", TRUST_BODY))
            else:
                self._html(page("duo_challenge", DUO_BODY))
        elif self.path.startswith("/trust"):
            s.trusted = True
            self._html(page("logged_in", "<h1>Welcome</h1>"), headers={"Set-Cookie": "sid=ok; Path=/"})
        else:
            self._html(page("login_form", LOGIN_FORM))

    def do_POST(self):
        s = self.server
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode())
        s.hits.append(("POST", self.path))
        if (form.get("u", [""])[0], form.get("p", [""])[0]) == GOOD:
            self._html(page("duo_challenge", DUO_BODY), headers={"Set-Cookie": "pre=1; Path=/"})
        else:
            self._html(page("login_form", "<p>bad credentials</p>" + LOGIN_FORM))


class MockSSO:
    def __init__(self):
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.server.hits, self.server.duo_approved, self.server.trusted = [], False, False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base(self):
        return "http://127.0.0.1:%d" % self.server.server_address[1]

    def approve_duo(self):
        self.server.duo_approved = True

    @property
    def login_posts(self):
        return sum(1 for m, _ in self.server.hits if m == "POST")

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
