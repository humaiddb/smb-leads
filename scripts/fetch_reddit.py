#!/usr/bin/env python3
"""Fetch recent posts from SMB subreddits via Reddit's RSS feeds."""

import json
import sys
import time
import html
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

SUBREDDITS = ["smallbusiness", "Entrepreneur", "EntrepreneurRideAlong"]
LOOKBACK_HOURS = 26

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

USER_AGENT = "macos:smb-leads-scanner:v0.3 (by /u/humaiddb)"
NS = {"atom": "http://www.w3.org/2005/Atom"}


def fetch_subreddit(sub):
    url = f"https://www.reddit.com/r/{sub}/new/.rss?limit=100"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        print(f"[warn] r/{sub}: HTTP {e.code}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[warn] r/{sub}: {e}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"[warn] r/{sub}: XML parse error: {e}", file=sys.stderr)
        return []

    posts = []
    for entry in root.findall("atom:entry", NS):
        title_el = entry.find("atom:title", NS)
        link_el = entry.find("atom:link", NS)
        content_el = entry.find("atom:content", NS)
        updated_el = entry.find("atom:updated", NS)
        author_el = entry.find("atom:author/atom:name", NS)

        title = title_el.text if title_el is not None else ""
        link = link_el.get("href") if link_el is not None else ""
        content_html = content_el.text if content_el is not None else ""
        updated = updated_el.text if updated_el is not None else ""
        author = author_el.text if author_el is not None else ""

        content_text = re.sub(r"<[^>]+>", " ", html.unescape(content_html or ""))
        content_text = re.sub(r"\s+", " ", content_text).strip()

        try:
            created_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except ValueError:
            created_dt = datetime.now(timezone.utc)

        posts.append({
            "title": title or "",
            "url": link,
            "author": author.replace("/u/", ""),
            "body": content_text[:3000],
            "created_dt": created_dt,
        })
    return posts


def matches_pain(text):
    t = text.lower()
    return [sig for sig in PAIN_SIGNALS if sig in t]


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    candidates = []

    for sub in SUBREDDITS:
        posts = fetch_subreddit(sub)
        print(f"[info] r/{sub}: fetched {len(posts)} posts", file=sys.stderr)
        time.sleep(2)
        recent = 0
        for p in posts:
            if p["created_dt"] < cutoff:
                continue
            recent += 1
            signals = matches_pain(f"{p['title']}\n{p['body']}")
            if not signals:
                continue
            candidates.append({
                "subreddit": sub,
                "title": p["title"],
                "body": p["body"][:2500],
                "url": p["url"],
                "author": p["author"],
                "score": 0,
                "num_comments": 0,
                "created_iso": p["created_dt"].isoformat(),
                "matched_signals": signals,
            })
        print(f"[info] r/{sub}: {recent} within {LOOKBACK_HOURS}h window", file=sys.stderr)

    print(f"[info] found {len(candidates)} candidate posts", file=sys.stderr)
    json.dump(candidates, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
