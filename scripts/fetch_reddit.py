#!/usr/bin/env python3
"""
Fetch recent posts from SMB subreddits via pullpush.io (community Reddit archive)
and filter for automation pain signals.
"""

import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta

SUBREDDITS = ["smallbusiness", "Entrepreneur", "EntrepreneurRideAlong"]
LOOKBACK_HOURS = 26
POSTS_PER_SUB = 100

PAIN_SIGNALS = [
    "manually", "by hand", "copy paste", "copy and paste", "copy-paste",
    "spreadsheet", "excel sheet", "tedious", "repetitive", "takes forever",
    "hours a day", "hours a week", "every day i", "every week i",
    "is there a way", "is there an app", "is there software", "is there a tool",
    "how do you handle", "how do you manage", "how do you track",
    "automate", "automation", "streamline", "workflow",
    "drowning in", "overwhelmed with", "struggling with",
    "follow up", "follow-up", "track leads", "tracking leads",
    "no-code", "nocode", "zapier", "make.com",
    "wastes time", "waste of time", "time sink", "soul crushing",
]

USER_AGENT = "macos:smb-leads-scanner:v0.2 (by /u/humaiddb)"


def fetch_subreddit(sub):
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).timestamp())
    params = urllib.parse.urlencode({
        "subreddit": sub,
        "after": cutoff_ts,
        "size": POSTS_PER_SUB,
        "sort": "desc",
        "sort_type": "created_utc",
    })
    url = f"https://api.pullpush.io/reddit/search/submission/?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"[warn] r/{sub}: HTTP {e.code}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[warn] r/{sub}: {e}", file=sys.stderr)
        return []
    return data.get("data", [])


def matches_pain(text):
    t = text.lower()
    return [sig for sig in PAIN_SIGNALS if sig in t]


def main():
    candidates = []
    for sub in SUBREDDITS:
        posts = fetch_subreddit(sub)
        print(f"[info] r/{sub}: fetched {len(posts)} posts", file=sys.stderr)
        time.sleep(2)
        for p in posts:
            if p.get("stickied") or p.get("over_18"):
                continue
            title = p.get("title", "")
            body = p.get("selftext", "")
            if body in ("[removed]", "[deleted]"):
                body = ""
            signals = matches_pain(f"{title}\n{body}")
            if not signals:
                continue
            permalink = p.get("permalink", "")
            if not permalink.startswith("/"):
                permalink = f"/r/{sub}/comments/{p.get('id', '')}/"
            candidates.append({
                "subreddit": sub,
                "title": title,
                "body": body[:2500],
                "url": f"https://reddit.com{permalink}",
                "author": p.get("author", ""),
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "created_iso": datetime.fromtimestamp(
                    p.get("created_utc", 0), tz=timezone.utc
                ).isoformat(),
                "matched_signals": signals,
            })

    print(f"[info] found {len(candidates)} candidate posts", file=sys.stderr)
    json.dump(candidates, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
