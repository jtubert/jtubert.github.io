#!/usr/bin/env python3
"""A digest of what happened on jtubert.com, from the GA4 Data API.

    python3 tools/ga-report.py            # the last 7 days
    python3 tools/ga-report.py --days 1   # yesterday and today
    python3 tools/ga-report.py --now      # the last 30 minutes

--now exists because runReport reads PROCESSED data, and GA4 takes 24 to 48
hours to process a new property's first data into standard reports. Until that
catches up every dated section is legitimately empty while the site is being
visited, which looks broken and is not. runRealtimeReport has no such lag.

Auth runs as a service account, ga-reader@jtubert-analytics, for two reasons.

The first is that the obvious route does not work: Google blocks the gcloud
CLI's own OAuth client from requesting analytics.readonly ("This app is
blocked"), because it is a sensitive scope and that client is not verified for
it. A service account key skips OAuth consent altogether.

The second is that this is a personal site. The machine's default credentials
belong to the Tombras account and ADC lives at one fixed path, so authenticating
there would overwrite the credential the Tombras SDKs rely on. This one is kept
in its own CLOUDSDK_CONFIG directory and the two never collide.

The key is at ~/.config/jtubert-analytics/ga-reader.json, mode 600, outside the
repo. It is a real credential: never commit it or paste it anywhere.

Access is granted in GA, not in GCP: the service account address is added as a
Viewer under Admin -> Property access management.

There is nothing to pip install. gcloud mints the token and urllib does the rest.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

PROPERTY = "257388699"
CONFIG_DIR = os.path.expanduser("~/.config/gcloud-personal")
API = "https://analyticsdata.googleapis.com/v1beta/properties/{}:runReport"
# Backup to GA4's built-in "AI Assistant" channel, for assistants it does not know yet.
AI_SOURCES = (r"chatgpt\.com|chat\.openai\.com|perplexity\.ai|gemini\.google\.com|"
              r"claude\.ai|copilot\.microsoft\.com|you\.com|meta\.ai")
API_NOW = "https://analyticsdata.googleapis.com/v1beta/properties/{}:runRealtimeReport"


SA_EMAIL = "ga-reader@jtubert-analytics.iam.gserviceaccount.com"
KEY = os.path.expanduser("~/.config/jtubert-analytics/ga-reader.json")
SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def token():
    if not os.path.exists(KEY):
        sys.exit(
            f"No key at {KEY}.\nRecreate it with:\n\n"
            "  gcloud iam service-accounts keys create ~/.config/jtubert-analytics/ga-reader.json \\\n"
            f"    --iam-account={SA_EMAIL} --project=jtubert-analytics --account=jtubert@gmail.com\n"
        )
    env = dict(os.environ, CLOUDSDK_CONFIG=CONFIG_DIR)

    def mint():
        return subprocess.run(
            ["gcloud", "auth", "print-access-token", "--account", SA_EMAIL, "--scopes", SCOPE],
            env=env, capture_output=True, text=True,
        )

    r = mint()
    if r.returncode:
        # first run on this machine, or the isolated config was cleared
        subprocess.run(["gcloud", "auth", "activate-service-account", "--key-file", KEY],
                       env=env, capture_output=True, text=True)
        r = mint()
    if r.returncode:
        sys.exit(f"Could not get a token:\n{r.stderr.strip()}")
    return r.stdout.strip()


def report(tok, dimensions, metrics, days, limit=15, order_metric=None, dim_filter=None,
           realtime=False):
    body = {
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
    }
    if not realtime:
        body["dateRanges"] = [{"startDate": f"{days}daysAgo", "endDate": "today"}]
    if order_metric:
        body["orderBys"] = [{"metric": {"metricName": order_metric}, "desc": True}]
    if dim_filter:
        body["dimensionFilter"] = dim_filter

    req = urllib.request.Request(
        (API_NOW if realtime else API).format(PROPERTY),
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        # A parameter that was never registered as a custom dimension is not an
        # error worth stopping for; the section just gets skipped.
        if e.code == 400 and "customEvent:" in detail:
            return None
        if e.code == 403:
            sys.exit(
                f"\nGA denied access to property {PROPERTY}.\n\n"
                f"Add {SA_EMAIL} as a Viewer:\n"
                "  GA4 -> Admin -> Property access management -> + -> Add users\n"
            )
        sys.exit(f"\nGA API returned {e.code}:\n{detail}\n")


def rows(res):
    for r in (res or {}).get("rows", []):
        yield ([d["value"] for d in r.get("dimensionValues", [])],
               [m["value"] for m in r.get("metricValues", [])])


def table(title, res, headers, width=52, note=None):
    print(f"\n{title}")
    print("-" * (len(title)))
    if res is None:
        print(f"  (skipped: {note})" if note else "  (no data)")
        return
    got = list(rows(res))
    if not got:
        print("  nothing in this range")
        return
    for dims, mets in got:
        label = " / ".join(dims)[:width]
        print(f"  {label:<{width}}  " + "  ".join(f"{m:>8}" for m in mets))
    print(f"  {'':<{width}}  " + "  ".join(f"{h:>8}" for h in headers))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--now", action="store_true", help="the last 30 minutes, with no processing lag")
    a = ap.parse_args()
    tok = token()
    d = a.days

    if a.now:
        print(f"\njtubert.com  ·  right now  ·  property {PROPERTY}")
        live = report(tok, [], ["activeUsers"], d, realtime=True)
        for _, m in rows(live):
            print(f"\n  {m[0]} active user{'' if m[0] == '1' else 's'} in the last 30 minutes")
        table("Pages being read",
              report(tok, ["unifiedScreenName"], ["activeUsers"], d, realtime=True,
                     order_metric="activeUsers"),
              ["users"])
        table("Events firing",
              report(tok, ["eventName"], ["eventCount"], d, limit=25, realtime=True,
                     order_metric="eventCount"),
              ["count"])
        print()
        return

    print(f"\njtubert.com  ·  last {d} day{'s' if d != 1 else ''}  ·  property {PROPERTY}")

    tot = report(tok, [], ["activeUsers", "sessions", "screenPageViews", "averageSessionDuration"], d)
    got = list(rows(tot))
    for _, m in got:
        print(f"\n  {m[0]} users   {m[1]} sessions   {m[2]} views   "
              f"{float(m[3]):.0f}s average session")
    if not got:
        print("\n  No processed data in this range.\n"
              "  GA4 takes 24 to 48 hours to process a new property's first data into\n"
              "  standard reports, and this endpoint only reads processed data. If the\n"
              "  site is being visited now, `--now` will show it.")

    table("Most visited pages",
          report(tok, ["pagePath"], ["screenPageViews", "activeUsers"], d, order_metric="screenPageViews"),
          ["views", "users"])

    table("Where they came from",
          report(tok, ["sessionSource", "sessionMedium"], ["sessions"], d, limit=10, order_metric="sessions"),
          ["sessions"])

    table("Events",
          report(tok, ["eventName"], ["eventCount"], d, limit=25, order_metric="eventCount"),
          ["count"])

    # People who arrived from an AI answer. GA4's default channel group has its
    # own "AI Assistant" channel, classified by Google upstream, so that label is
    # the primary test; the source list is kept as a backup for any assistant
    # Google does not recognise yet. Either way it only sees click-throughs from a
    # cited link: an answer that mentions him without a click leaves no trace
    # here, which is what Bing Webmaster Tools' AI Performance report is for.
    table("Arrived from AI assistants",
          report(tok, ["sessionDefaultChannelGroup", "sessionSource", "landingPage"], ["sessions"], d,
                 limit=20, order_metric="sessions",
                 dim_filter={"orGroup": {"expressions": [
                     {"filter": {"fieldName": "sessionDefaultChannelGroup",
                                 "stringFilter": {"matchType": "EXACT", "value": "AI Assistant"}}},
                     {"filter": {"fieldName": "sessionSource", "stringFilter": {
                         "matchType": "PARTIAL_REGEXP", "value": AI_SOURCES}}},
                 ]}}),
          ["sessions"])

    # These three read event parameters, which the Data API can only return once
    # they are registered as custom dimensions in GA4. Until then they skip.
    hint = "register link_kind as a custom dimension in GA4"
    table("Outbound clicks by kind",
          report(tok, ["customEvent:link_kind"], ["eventCount"], d, limit=10, order_metric="eventCount"),
          ["count"], note=hint)

    table("How people moved between posts",
          report(tok, ["customEvent:method"], ["eventCount"], d, limit=10, order_metric="eventCount"),
          ["count"], note="register method as a custom dimension in GA4")

    table("Backdrop shown",
          report(tok, ["customEvent:backdrop_id"], ["eventCount"], d, limit=10, order_metric="eventCount"),
          ["count"], note="register backdrop_id as a custom dimension in GA4")

    print()


if __name__ == "__main__":
    main()
