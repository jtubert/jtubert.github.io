#!/usr/bin/env python3
"""A digest of what happened on jtubert.com, from the GA4 Data API.

    python3 tools/ga-report.py            # the last 7 days
    python3 tools/ga-report.py --days 1   # yesterday and today

Auth deliberately does NOT use the machine's default credentials. Those belong
to the Tombras account and live at a single fixed path; this site is personal
and its property is owned by the gmail account, so the credential for it sits
in its own CLOUDSDK_CONFIG directory and the two never collide. Set it up once:

    CLOUDSDK_CONFIG=~/.config/gcloud-personal gcloud auth application-default login \
      --account=jtubert@gmail.com \
      --scopes=https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform

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
QUOTA_PROJECT = "jtubert-analytics"
CONFIG_DIR = os.path.expanduser("~/.config/gcloud-personal")
API = "https://analyticsdata.googleapis.com/v1beta/properties/{}:runReport"


def token():
    if not os.path.isdir(CONFIG_DIR):
        sys.exit(
            "No personal credential yet. Run this once:\n\n"
            f"  CLOUDSDK_CONFIG={CONFIG_DIR} gcloud auth application-default login \\\n"
            "    --account=jtubert@gmail.com \\\n"
            "    --scopes=https://www.googleapis.com/auth/analytics.readonly,"
            "https://www.googleapis.com/auth/cloud-platform\n"
        )
    env = dict(os.environ, CLOUDSDK_CONFIG=CONFIG_DIR)
    r = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"],
        env=env, capture_output=True, text=True,
    )
    if r.returncode:
        sys.exit(f"Could not get a token:\n{r.stderr.strip()}")
    return r.stdout.strip()


def report(tok, dimensions, metrics, days, limit=15, order_metric=None, dim_filter=None):
    body = {
        "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "today"}],
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
    }
    if order_metric:
        body["orderBys"] = [{"metric": {"metricName": order_metric}, "desc": True}]
    if dim_filter:
        body["dimensionFilter"] = dim_filter

    req = urllib.request.Request(
        API.format(PROPERTY),
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
            # user credentials need a project to bill the quota to
            "x-goog-user-project": QUOTA_PROJECT,
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
    a = ap.parse_args()
    tok = token()
    d = a.days

    print(f"\njtubert.com  ·  last {d} day{'s' if d != 1 else ''}  ·  property {PROPERTY}")

    tot = report(tok, [], ["activeUsers", "sessions", "screenPageViews", "averageSessionDuration"], d)
    for _, m in rows(tot):
        print(f"\n  {m[0]} users   {m[1]} sessions   {m[2]} views   "
              f"{float(m[3]):.0f}s average session")

    table("Most visited pages",
          report(tok, ["pagePath"], ["screenPageViews", "activeUsers"], d, order_metric="screenPageViews"),
          ["views", "users"])

    table("Where they came from",
          report(tok, ["sessionSource", "sessionMedium"], ["sessions"], d, limit=10, order_metric="sessions"),
          ["sessions"])

    table("Events",
          report(tok, ["eventName"], ["eventCount"], d, limit=25, order_metric="eventCount"),
          ["count"])

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
