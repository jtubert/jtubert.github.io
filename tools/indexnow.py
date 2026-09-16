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
the gh CLI, and only continues once it has succeeded. It then checks the CDN
rather than trusting it: GitHub Pages stamps every file with the deploy's time
in Last-Modified, so any page whose Last-Modified is older than the run's
creation is still the previous build, and the whole set is re-read until none
is. A fixed 20-second sleep stood in for that check before, and if the CDN had
not caught up, the old HTML was fingerprinted, recorded as current, and the
change went unsubmitted until some later deploy.

Nothing is recorded unless the run completes. A page answering an HTTP error,
an unreachable network, or a CDN that never catches up all exit with a message
and leave the recorded fingerprints as they were.
"""

import argparse, email.utils, glob, hashlib, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.jtubert.com"
HOST = "www.jtubert.com"
REPO = "jtubert/jtubert.github.io"
ENDPOINT = "https://api.indexnow.org/indexnow"
STATE = os.path.join(ROOT, "tools", ".indexnow-sent.json")
CDN_TIMEOUT = 600
HEADERS = {"User-Agent": "jtubert-indexnow/1.0", "Cache-Control": "no-cache"}


def key():
    found = [f for f in glob.glob(os.path.join(ROOT, "*.txt"))
             if re.fullmatch(r"[0-9a-f]{32}\.txt", os.path.basename(f))]
    if len(found) != 1:
        sys.exit(f"Expected exactly one IndexNow key file at the repo root, found {len(found)}.")
    return os.path.basename(found[0])[:-4]


def pages():
    """Every URL the sitemap lists, from the files the generator wrote."""
    with open(os.path.join(ROOT, "_data", "nav.json"), encoding="utf-8") as f:
        nav = json.load(f)
    urls = [f"{SITE}/", f"{SITE}/about/", f"{SITE}/work/"]
    for g in nav["years"]:
        urls += [f"{SITE}/work/{it['id']}/" for it in g["items"]]
    return urls


def fetch(url):
    """(status, body, Last-Modified as a datetime or None).

    urlopen raises on an HTTP error status, so an error page is never returned,
    and so never fingerprinted. Both that and a network failure exit with a
    message instead of a traceback."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            lm = r.headers.get("Last-Modified")
            return (r.status, r.read().decode("utf-8", "replace"),
                    email.utils.parsedate_to_datetime(lm) if lm else None)
    except urllib.error.HTTPError as e:
        sys.exit(f"{url.split('?')[0]} answered HTTP {e.code}. Not submitting; nothing recorded.")
    except OSError as e:   # URLError, timeouts, DNS and TLS failures
        sys.exit(f"Could not reach {url.split('?')[0]}: {getattr(e, 'reason', e)}. "
                 "Not submitting; nothing recorded.")


def fingerprint(url):
    """(sha256 of the page with whitespace collapsed, its Last-Modified)."""
    _, html, lm = fetch(f"{url}?nocache={int(time.time())}")
    return hashlib.sha256(re.sub(r"\s+", " ", html).encode()).hexdigest(), lm


def wait_for_deploy():
    """Wait for the Actions run deploying HEAD to succeed. Returns when it was
    created, which every page of that build will be newer than."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    deadline = time.time() + 900
    seen = False
    while time.time() < deadline:
        r = subprocess.run(["gh", "run", "list", "--repo", REPO, "--commit", head,
                            "--json", "status,conclusion,createdAt"], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"Could not read the deploy run through gh:\n{r.stderr.strip()}")
        runs = json.loads(r.stdout or "[]")
        if runs:
            seen = True
            # This repo has one workflow, whose build and deploy are jobs in the
            # same run, so a completed run means the site was deployed.
            if all(x["status"] == "completed" for x in runs):
                bad = [x for x in runs if x["conclusion"] != "success"]
                if bad:
                    sys.exit(f"The deploy for {head[:7]} finished as {bad[0]['conclusion']}. Not submitting.")
                return min(datetime.fromisoformat(x["createdAt"].replace("Z", "+00:00")) for x in runs)
        time.sleep(15)
    sys.exit(f"No successful deploy for {head[:7]} within 15 minutes"
             + ("" if seen else " (no run was ever started for it)") + ". Not submitting.")


def read_live(urls, since=None):
    """Fingerprint each URL. Given `since`, the deploy run's creation time, a page
    whose Last-Modified predates it is still the CDN's copy of the previous
    build, so the set is re-read until none is, or the run gives up having
    recorded nothing."""
    deadline = time.time() + CDN_TIMEOUT
    while True:
        got = {u: fingerprint(u) for u in urls}
        stale = [u for u, (_, lm) in got.items() if since and lm and lm < since]
        if not stale:
            return {u: h for u, (h, _) in got.items()}
        if time.time() > deadline:
            sys.exit(f"{len(stale)} page(s) still served from before the deploy after "
                     f"{CDN_TIMEOUT // 60} minutes, for example {stale[0]}. "
                     "Not submitting; nothing recorded.")
        time.sleep(15)


def load_state():
    if not os.path.exists(STATE):
        return {}
    with open(STATE, encoding="utf-8") as f:
        data = json.load(f)
    # the first format stored dates, which are not comparable to fingerprints
    return data.get("hashes", {}) if data.get("version") == 2 else {}


def save_state(hashes):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"version": 2, "hashes": hashes}, f, indent=1)


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
    except OSError as e:
        sys.exit(f"Could not reach IndexNow: {getattr(e, 'reason', e)}. Nothing submitted or recorded.")
    if code not in (200, 202):
        sys.exit(f"IndexNow returned HTTP {code}.")
    return code


def report(code, send):
    print(f"IndexNow: submitted {len(send)} URL{'s' if len(send) != 1 else ''} (HTTP {code}):")
    for u in send[:12]:
        print(f"  {u}")
    if len(send) > 12:
        print(f"  ... and {len(send) - 12} more")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--urls", default="")
    a = ap.parse_args()

    k = key()
    since = wait_for_deploy() if a.wait else None

    status, body, _ = fetch(f"{SITE}/{k}.txt")
    if status != 200 or body.strip() != k:
        sys.exit(f"{SITE}/{k}.txt is not live with the right contents yet, so IndexNow would reject it.")

    old = load_state()

    if a.urls:
        # Read and record only the named pages. This used to read every page
        # and record them all, which marked changes on the pages not named as
        # already sent, so a later ordinary run would never have submitted them.
        send = [u.strip() for u in a.urls.split(",") if u.strip()]
        now = read_live(send, since)
        code = submit(k, send)
        old.update(now)
        save_state(old)
        report(code, send)
        return

    urls = pages()
    now = read_live(urls, since)

    if a.seed:
        save_state(now)
        print(f"IndexNow: recorded {len(now)} live pages, submitted nothing.")
        return

    send = urls if (a.all or not old) else [u for u in urls if old.get(u) != now[u]]
    if not send:
        save_state(now)
        print("IndexNow: no page changed since the last submission.")
        return

    code = submit(k, send)
    save_state(now)
    report(code, send)


if __name__ == "__main__":
    main()
