#!/usr/bin/env python3
"""Tell IndexNow which pages changed, so Bing (and the AI search products that
draw on Bing's index) pick them up on deploy rather than on their next crawl.

    python3 tools/indexnow.py           # submit pages whose lastmod changed
    python3 tools/indexnow.py --all     # submit every page
    python3 tools/indexnow.py --wait    # first wait for GitHub Pages to publish

The key is not a secret: IndexNow proves ownership by fetching it back from
https://www.jtubert.com/<key>.txt, so it has to be public. It is the one
32-character hex .txt file at the repo root.

"Changed" is judged against _data/lastmod.json, the git-derived dates the
generator writes, compared with what this script last submitted. Resubmitting
everything on every deploy is what IndexNow asks sites not to do.

--wait matters because `npm run deploy` returns as soon as git push does, a
minute or more before GitHub Pages serves the new build. Submitting then would
send Bing to the old pages. It polls the live sitemap until its dates match the
ones just generated, then submits.
"""

import argparse, glob, json, os, re, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.jtubert.com"
HOST = "www.jtubert.com"
ENDPOINT = "https://api.indexnow.org/indexnow"
STATE = os.path.join(ROOT, "tools", ".indexnow-sent.json")


def key():
    found = [f for f in glob.glob(os.path.join(ROOT, "*.txt"))
             if re.fullmatch(r"[0-9a-f]{32}\.txt", os.path.basename(f))]
    if len(found) != 1:
        sys.exit(f"Expected exactly one IndexNow key file at the repo root, found {len(found)}.")
    return os.path.basename(found[0])[:-4]


def expected():
    """{url: lastmod} for every page, from the files the generator just wrote."""
    lm = json.load(open(os.path.join(ROOT, "_data", "lastmod.json"), encoding="utf-8"))
    nav = json.load(open(os.path.join(ROOT, "_data", "nav.json"), encoding="utf-8"))
    pages = {f"{SITE}/": lm.get("home", ""), f"{SITE}/about/": lm.get("about", ""),
             f"{SITE}/work/": lm.get("work", "")}
    for g in nav["years"]:
        for it in g["items"]:
            pages[f"{SITE}/work/{it['id']}/"] = lm["entries"].get(it["id"], "")
    return pages


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "jtubert-indexnow/1.0",
                                               "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")


def live_sitemap():
    _, xml = fetch(f"{SITE}/sitemap.xml?nocache={int(time.time())}")
    out = {}
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", block)
        mod = re.search(r"<lastmod>(.*?)</lastmod>", block)
        if loc:
            out[loc.group(1).strip()] = mod.group(1).strip() if mod else ""
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--wait", action="store_true")
    a = ap.parse_args()

    k = key()
    want = expected()

    if a.wait:
        deadline = time.time() + 600
        while True:
            try:
                live = live_sitemap()
                if all(live.get(u) == d for u, d in want.items()):
                    break
            except Exception:
                pass
            if time.time() > deadline:
                sys.exit("The live sitemap never caught up with this build in 10 minutes. Not submitting.")
            time.sleep(15)

    try:
        status, body = fetch(f"{SITE}/{k}.txt")
        if status != 200 or body.strip() != k:
            raise ValueError
    except Exception:
        sys.exit(f"{SITE}/{k}.txt is not live with the right contents yet, so IndexNow would reject it.")

    sent = {}
    if os.path.exists(STATE) and not a.all:
        sent = json.load(open(STATE, encoding="utf-8"))
    urls = [u for u, d in want.items() if a.all or sent.get(u) != d]
    if not urls:
        print("IndexNow: nothing changed since the last submission.")
        return

    payload = json.dumps({"host": HOST, "key": k, "keyLocation": f"{SITE}/{k}.txt",
                          "urlList": urls}).encode()
    req = urllib.request.Request(ENDPOINT, data=payload, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        sys.exit(f"IndexNow refused the submission: HTTP {e.code} {e.read().decode(errors='replace')[:300]}")

    if code not in (200, 202):
        sys.exit(f"IndexNow returned HTTP {code}.")
    sent.update({u: want[u] for u in urls})
    json.dump(sent, open(STATE, "w", encoding="utf-8"), indent=1)
    print(f"IndexNow: submitted {len(urls)} URL{'s' if len(urls) != 1 else ''} (HTTP {code}).")


if __name__ == "__main__":
    main()
