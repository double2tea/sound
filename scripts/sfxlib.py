#!/usr/bin/env python3
"""Search and download SFX from several free libraries with one interface.

Providers (no API key):
  archive      Internet Archive audio items (licenses vary; check each item)
  mixkit       Mixkit free sound effects (Mixkit Free License)
  orangefree   Orange Free Sounds (CC BY-NC 4.0; non-commercial, attribution)

  sfxlib.py search "<query>" [--source archive|mixkit|orangefree|all] [-n 10]
  sfxlib.py get <out_dir> <provider:id>...

Keys printed by `search` are cached in ~/.cache/sfx-sources/multi.json.
"""
import argparse, html, json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mixkit_parse

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) sfx-libraries"}
CACHE = Path.home() / ".cache" / "sfx-sources"
INDEX = CACHE / "multi.json"
LICENSE = {
    "mixkit": "Mixkit Free License",
    "orangefree": "CC BY-NC 4.0",
    "archive": "check item",
}


def fetch(url, timeout=45, tries=3):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            if n == tries - 1:
                raise e if isinstance(e, OSError) else OSError(repr(e))
            time.sleep(1 + n)


def load_index():
    try:
        return json.loads(INDEX.read_text())
    except (OSError, ValueError):
        return {}


def save_index(rows):
    CACHE.mkdir(parents=True, exist_ok=True)
    idx = load_index()
    idx.update({r["key"]: r for r in rows})
    INDEX.write_text(json.dumps(idx, ensure_ascii=False))


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def search_archive(q, n):
    params = [("q", f'{q} AND mediatype:audio AND subject:"sound effects"'),
              ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "licenseurl"),
              ("fl[]", "downloads"), ("rows", str(n)), ("output", "json")]
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params)
    d = json.loads(fetch(url))
    out = []
    for x in d.get("response", {}).get("docs", []):
        ident = x.get("identifier", "")
        if not ident:
            continue
        out.append({"key": "archive:" + ident, "provider": "archive", "id": ident,
                    "title": x.get("title", ident), "duration": "-",
                    "license": x.get("licenseurl") or LICENSE["archive"],
                    "url": "https://archive.org/details/" + ident})
    return out


def search_mixkit(q, n):
    slug = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")
    url = f"https://mixkit.co/free-sound-effects/{slug}/"
    try:
        h = fetch(url).decode("utf-8", "replace")
    except Exception:
        url = "https://mixkit.co/free-sound-effects/?" + urllib.parse.urlencode({"q": q})
        h = fetch(url).decode("utf-8", "replace")
    out = []
    for item in mixkit_parse.parse_category_page(h, page_slug=slug):
        out.append({"key": "mixkit:" + item["id"], "provider": "mixkit", "id": item["id"],
                    "title": item["title"] or item["id"],
                    "duration": item["duration"] or "-",
                    "license": LICENSE["mixkit"], "url": item["preview_url"]})
        if len(out) >= n:
            break
    return out


def search_orangefree(q, n):
    url = "https://www.orangefreesounds.com/?" + urllib.parse.urlencode({"s": q})
    h = fetch(url).decode("utf-8", "replace")
    seen, out = set(), []
    for m in re.finditer(r'href="(https://orangefreesounds\.com/wp-content/uploads/[^"]+\.mp3)"', h):
        u = html.unescape(m.group(1))
        if u in seen:
            continue
        seen.add(u)
        name = urllib.parse.unquote(u.rsplit("/", 1)[-1])
        title = re.sub(r"[-_]+", " ", name.rsplit(".", 1)[0]).strip()
        out.append({"key": "orangefree:" + name, "provider": "orangefree", "id": name,
                    "title": title, "duration": "-",
                    "license": LICENSE["orangefree"], "url": u})
        if len(out) >= n:
            break
    return out


SEARCH = {"archive": search_archive, "mixkit": search_mixkit, "orangefree": search_orangefree}


def search(a):
    rows = []
    for src in (SEARCH if a.source == "all" else [a.source]):
        try:
            rows += SEARCH[src](a.query, a.n)
        except Exception as e:
            print(f"! {src}: {e}", file=sys.stderr)
    save_index(rows)
    for r in rows:
        print(f'{r["key"]}\t{r["title"][:60]}\t{r["duration"]}\t{r["license"]}\t{r["url"]}')
    if not rows:
        print("(none)")


def pick_archive_file(ident, wanted=None):
    d = json.loads(fetch("https://archive.org/metadata/" + urllib.parse.quote(ident)))
    files = d.get("files", [])
    audio = [f for f in files if f.get("format") in ("FLAC", "WAVE", "WAV", "OGG", "MP3")
             or re.search(r"\.(flac|wav|ogg|mp3)$", f.get("name", ""), re.I)]
    if wanted:
        for f in audio:
            if f["name"] == wanted:
                return f
        raise SystemExit(f"file not found in item: {wanted}")
    if not audio:
        raise SystemExit("no audio file in item")
    order = {"FLAC": 0, "WAVE": 1, "WAV": 1, "OGG": 2, "MP3": 3}
    audio.sort(key=lambda f: order.get(f.get("format"), 9))
    return audio[0]


def safe_name(s):
    return re.sub(r"[^\w.\- ]+", "_", s).strip()[:120]


def get(a):
    idx = load_index()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for key in a.keys:
        r = idx.get(key)
        if not r and key.startswith("archive:") and "/" in key:
            base = key.split("/", 1)[0]
            r = idx.get(base)
            if r:
                r = dict(r)
                r["id"] = key[len("archive:"):]
        if not r:
            print(f"FAIL {key}: not in cache; search first")
            continue
        try:
            if r["provider"] == "archive":
                ident, _, wanted = r["id"].partition("/")
                f = pick_archive_file(ident, wanted or None)
                url = "https://archive.org/download/" + urllib.parse.quote(ident) + "/" + urllib.parse.quote(f["name"])
                name = f["name"]
            else:
                url = r["url"]
                name = r["id"] if r["provider"] == "mixkit" else r["id"]
                if r["provider"] == "mixkit":
                    name = f'{r["id"]}_{safe_name(r["title"])}.mp3'
            data = fetch(url, timeout=300)
            dst = out / safe_name(name)
            dst.write_bytes(data)
            print(f'{key}\t{r["license"]}\t{len(data)}\t{dst}')
        except Exception as e:
            print(f"FAIL {key}: {e}")
        time.sleep(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("search")
    p.add_argument("query")
    p.add_argument("--source", choices=["archive", "mixkit", "orangefree", "all"], default="all")
    p.add_argument("-n", type=int, default=10)
    p.set_defaults(fn=search)
    p = sp.add_parser("get")
    p.add_argument("out_dir")
    p.add_argument("keys", nargs="+")
    p.set_defaults(fn=get)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
