#!/usr/bin/env python3
"""Tell IndexNow which pages changed, so Bing (and the AI search products that
draw on Bing's index) pick them up on deploy rather than on their next crawl.

    python3 tools/indexnow.py           # submit pages whose live content changed
    python3 tools/indexnow.py --wait    # first wait for this commit's Pages deploy
    python3 tools/indexnow.py --all     # submit every page
    python3 tools/indexnow.py --seed    # record what is live now, submit nothing
    python3 tools/indexnow.py --urls a,b  # submit exactly these

The key is not a secret: IndexNow proves ownership by fetching it back from
https://www.jtubert.com/<key>.txt, so it has to be public. It is the one
32-character hex .txt file at the repo root.

"Changed" means the page's live HTML changed, fingerprinted with whitespace
collapsed. An earlier version compared the git-derived "last updated" dates
instead, and that missed real changes: those dates follow the post bodies, so
an edit to structured data or to /about/'s content made on a day the page
already carried left every date the same and nothing was sent. Built HTML is
byte-identical across rebuilds with no content change (only feed.xml carries a
timestamp, and it is not submitted), so a different fingerprint is a real change.

--wait follows the GitHub Actions run that deploys this exact commit, through
the gh CLI, and only continues once it has succeeded. The earlier version
polled the live sitemap until its dates matched, which returned at once
whenever the dates had not changed, before the deploy had even finished.
"""

import argparse, glob, hashlib, json, os, re, subprocess, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.jtubert.com"
HOST = "www.jtubert.com"
REPO = "jtubert/jtubert.github.io"
ENDPOINT = "https://api.indexnow.org/indexnow"
STATE = os.path.join(ROOT, "tools", ".indexnow-sent.json")


def key():
    found = [f for f in glob.glob(os.path.join(ROOT, "*.txt"))
             if re.fullmatch(r"[0-9a-f]{32}\.txt", os.path.basename(f))]
    if len(found) != 1:
        sys.exit(f"Expected exactly one IndexNow key file at the repo root, found {len(found)}.")
    return os.path.basename(found[0])[:-4]


def pages():
    """Every URL the sitemap lists, from the files the generator wrote."""
    nav = json.load(open(os.path.join(ROOT, "_data", "nav.json"), encoding="utf-8"))
    urls = [f"{SITE}/", f"{SITE}/about/", f"{SITE}/work/"]
    for g in nav["years"]:
        urls += [f"{SITE}/work/{it['id']}/" for it in g["items"]]
    return urls


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "jtubert-indexnow/1.0",
                                               "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")


def fingerprint(url):
    _, html = fetch(f"{url}?nocache={int(time.time())}")
    return hashlib.sha256(re.sub(r"\s+", " ", html).encode()).hexdigest()


def wait_for_deploy():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    deadline = time.time() + 900
    seen = False
    while time.time() < deadline:
        r = subprocess.run(["gh", "run", "list", "--repo", REPO, "--commit", head,
                            "--json", "status,conclusion"], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"Could not read the deploy run through gh:\n{r.stderr.strip()}")
        runs = json.loads(r.stdout or "[]")
        if runs:
            seen = True
            if all(x["status"] == "completed" for x in runs):
                bad = [x for x in runs if x["conclusion"] != "success"]
                if bad:
                    sys.exit(f"The deploy for {head[:7]} finished as {bad[0]['conclusion']}. Not submitting.")
                time.sleep(20)   # let the CDN pick up the new build
                return
        time.sleep(15)
    sys.exit(f"No successful deploy for {head[:7]} within 15 minutes"
             + ("" if seen else " (no run was ever started for it)") + ". Not submitting.")


def load_state():
    if not os.path.exists(STATE):
        return {}
    data = json.load(open(STATE, encoding="utf-8"))
    # the first format stored dates, which are not comparable to fingerprints
    return data.get("hashes", {}) if data.get("version") == 2 else {}


def save_state(hashes):
    json.dump({"version": 2, "hashes": hashes}, open(STATE, "w", encoding="utf-8"), indent=1)


def submit(k, urls):
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
    return code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--urls", default="")
    a = ap.parse_args()

    k = key()
    if a.wait:
        wait_for_deploy()

    try:
        status, body = fetch(f"{SITE}/{k}.txt")
        if status != 200 or body.strip() != k:
            raise ValueError
    except Exception:
        sys.exit(f"{SITE}/{k}.txt is not live with the right contents yet, so IndexNow would reject it.")

    urls = pages()
    old = load_state()
    now = {u: fingerprint(u) for u in urls}

    if a.seed:
        save_state(now)
        print(f"IndexNow: recorded {len(now)} live pages, submitted nothing.")
        return

    if a.urls:
        send = [u.strip() for u in a.urls.split(",") if u.strip()]
    elif a.all or not old:
        send = urls
    else:
        send = [u for u in urls if old.get(u) != now[u]]

    if not send:
        save_state(now)
        print("IndexNow: no page changed since the last submission.")
        return

    code = submit(k, send)
    save_state(now)
    print(f"IndexNow: submitted {len(send)} URL{'s' if len(send) != 1 else ''} (HTTP {code}):")
    for u in send[:12]:
        print(f"  {u}")
    if len(send) > 12:
        print(f"  ... and {len(send) - 12} more")


if __name__ == "__main__":
    main()
