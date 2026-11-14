#!/usr/bin/env python3
"""Freesound APIv2: OAuth2 (PKCE) authorization and original-file downloads.

Credentials live outside the skill:
  ~/.config/freesound/credential.json  {"client_id","client_secret","redirect_uri"}
  ~/.config/freesound/token.json       access/refresh token, written by `auth`

  fs_api.py status
  fs_api.py auth [--no-browser] [--timeout 300]
  fs_api.py hq <out_dir> <sound_id>...
  fs_api.py search "<query>" [-n 10]
"""
import argparse, base64, hashlib, http.server, json, os, secrets, sys, threading
import time, urllib.parse, urllib.request, webbrowser
from pathlib import Path

CFG = Path.home() / ".config" / "freesound"
CRED = CFG / "credential.json"
TOKEN = CFG / "token.json"
API = "https://freesound.org/apiv2"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) fs-api"}


def die(msg):
    sys.exit(msg)


def load(path, name):
    try:
        return json.loads(path.read_text())
    except OSError:
        die(f"missing {name}: {path}")
    except ValueError:
        die(f"invalid JSON in {path}")


def save_token(d):
    CFG.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(json.dumps(d, indent=1))
    os.chmod(TOKEN, 0o600)


def b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def post_form(url, fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers={
        **UA, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def get_json(url, token=None):
    h = dict(UA)
    if token:
        h["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
        return json.loads(r.read())


def refresh_token(cred, tok):
    rt = tok.get("refresh_token")
    if not rt:
        die("token expired and no refresh_token; run `auth` again")
    fields = {"client_id": cred["client_id"], "grant_type": "refresh_token", "refresh_token": rt}
    if cred.get("client_secret"):
        fields["client_secret"] = cred["client_secret"]
    d = post_form(API + "/oauth2/access_token/", fields)
    d["expires_at"] = int(time.time()) + int(d.get("expires_in", 86400)) - 60
    save_token(d)
    return d


def valid_token(cred):
    tok = load(TOKEN, "token (run `auth` first)")
    if tok.get("expires_at", 0) > time.time():
        return tok["access_token"]
    return refresh_token(cred, tok)["access_token"]


def status(_):
    cred = load(CRED, "credential.json")
    print("credential:", CRED, "client_id", cred.get("client_id", "")[:6] + "…",
          "redirect", cred.get("redirect_uri"))
    try:
        tok = json.loads(TOKEN.read_text())
        left = int(tok.get("expires_at", 0) - time.time())
        print("token:", "valid" if left > 0 else "expired", f"({left}s left)" if left > 0 else "")
    except (OSError, ValueError):
        print("token: none")


def auth(a):
    cred = load(CRED, "credential.json")
    redirect = cred.get("redirect_uri") or "http://localhost:8765/callback"
    u = urllib.parse.urlparse(redirect)
    verifier = b64url(secrets.token_bytes(64))
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)
    q = urllib.parse.urlencode({
        "client_id": cred["client_id"], "response_type": "code", "redirect_uri": redirect,
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state})
    url = API + "/oauth2/authorize/?" + q
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            p = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(p.query)
            if p.path != u.path:
                self.send_response(404); self.end_headers(); return
            if qs.get("state", [""])[0] != state:
                got["error"] = "state mismatch"
            elif "code" in qs:
                got["code"] = qs["code"][0]
            else:
                got["error"] = qs.get("error_description", qs.get("error", ["no code"]))[0]
            body = b"<h2>Freesound authorization received.</h2><p>You can close this tab.</p>"
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = http.server.HTTPServer((u.hostname or "127.0.0.1", u.port or 80), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("authorize URL:\n" + url)
    if not a.no_browser:
        webbrowser.open(url)
    deadline = time.time() + a.timeout
    while time.time() < deadline and not got:
        time.sleep(0.5)
    srv.shutdown()
    if not got:
        die("authorization timed out")
    if "error" in got:
        die("authorization failed: " + got["error"])
    fields = {"client_id": cred["client_id"], "grant_type": "authorization_code",
              "code": got["code"], "redirect_uri": redirect, "code_verifier": verifier}
    if cred.get("client_secret"):
        fields["client_secret"] = cred["client_secret"]
    d = post_form(API + "/oauth2/access_token/", fields)
    d["expires_at"] = int(time.time()) + int(d.get("expires_in", 86400)) - 60
    save_token(d)
    print("token saved:", TOKEN)


def safe_name(s):
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in s).strip()[:120]


def hq(a):
    cred = load(CRED, "credential.json")
    token = valid_token(cred)
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    for i, sid in enumerate(a.ids):
        meta = get_json(f"{API}/sounds/{sid}/?fields=name,username,license,duration,type", token)
        req = urllib.request.Request(f"{API}/sounds/{sid}/download/",
                                     headers={**UA, "Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
            cd = r.headers.get("Content-Disposition", "")
            fn = ""
            if "filename=" in cd:
                fn = cd.split("filename=")[-1].strip('"')
            if not fn:
                fn = f"{sid}_{safe_name(meta.get('name', 'sound'))}.{meta.get('type', 'wav')}"
            dst = out / safe_name(fn)
            dst.write_bytes(data)
        print(f"{sid}\t{meta.get('license')}\t{meta.get('username')}\t{len(data)}\t{dst}")
        if i < len(a.ids) - 1:
            time.sleep(2)
    print("done", len(a.ids))


def search(a):
    cred = load(CRED, "credential.json")
    token = valid_token(cred)
    q = urllib.parse.urlencode({"query": a.query, "fields": "id,name,duration,license,username,num_downloads,avg_rating,num_ratings,description",
                                "page_size": a.n})
    d = get_json(API + "/search/text/?" + q, token)
    for x in d.get("results", []):
        print(f"fs:{x['id']}\t{x['name'][:60]}\t{x['duration']:.1f}s\t{x['license']}\t↓{x['num_downloads']} ★{x['avg_rating']:.1f}({x['num_ratings']})\t{x['username']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status").set_defaults(fn=status)
    p = sp.add_parser("auth"); p.add_argument("--no-browser", action="store_true"); p.add_argument("--timeout", type=int, default=300); p.set_defaults(fn=auth)
    p = sp.add_parser("hq"); p.add_argument("out_dir"); p.add_argument("ids", nargs="+"); p.set_defaults(fn=hq)
    p = sp.add_parser("search"); p.add_argument("query"); p.add_argument("-n", type=int, default=10); p.set_defaults(fn=search)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
