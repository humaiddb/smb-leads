#!/usr/bin/env python3
"""
Fetch recent posts from SMB subreddits and filter for automation pain signals.

Outputs JSON to stdout. The ranker script consumes it.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

SUBREDDITS = ["smallbusiness", "Entrepreneur", "EntrepreneurRideAlong"]
LOOKBACK_HOURS = 26  # slight overlap so we don't miss posts near the 24h boundary
POSTS_PER_SUB = 100  # reddit's /new.json max

# Broad pre-filter. The LLM does the nuanced ranking downstream.
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

USER_AGENT = "reddit-leads-scanner/0.1 by u/research_bot"


def fetch_subreddit(sub: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{sub}/new.json?limit={POSTS_PER_SUB}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"[warn] r/{sub}: HTTP {e.code}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[warn] r/{sub}: {e}", file=sys.stderr)
        return []
    return [c["data"] for c in data.get("data", {}).get("children", [])]


def matches_pain(text: str) -> list[str]:
    t = text.lower()
    return [sig for sig in PAIN_SIGNALS if sig in t]


def main() -> None:
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).timestamp()
    candidates = []

    for sub in SUBREDDITS:
        posts = fetch_subreddit(sub)
        time.sleep(2)  # be polite to reddit
        for p in posts:
            if p.get("created_utc", 0) < cutoff_ts:
                continue
            if p.get("stickied") or p.get("over_18"):
                continue
            title = p.get("title", "")
            body = p.get("selftext", "")
            signals = matches_pain(f"{title}\n{body}")
            if not signals:
                continue
            candidates.append({
                "subreddit": sub,
                "title": title,
                "body": body[:2500],  # trim to keep token costs reasonable
                "url": f"https://reddit.com{p.get('permalink', '')}",
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
