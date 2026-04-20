#!/usr/bin/env python3
"""
Rank filtered Reddit posts by automation-opportunity quality using Claude,
then write a Markdown digest.

Usage:  cat posts.json | python3 rank_and_write.py <output_path>
"""

import json
import os
import sys
from datetime import datetime, timezone
from anthropic import Anthropic

MODEL = "claude-opus-4-5"  # upgrade/downgrade as you like
MAX_POSTS_TO_RANK = 40      # cap token usage on busy days

RANKING_PROMPT = """You are analyzing Reddit posts from small business owners to find people who are clearly wrestling with a repetitive, manual process that could be automated. These are potential leads for an automation consultant or SaaS builder.

For each post below, score it 1-10 on AUTOMATION OPPORTUNITY QUALITY using this rubric:

- 9-10: Owner describes a specific, recurring manual process; clear pain; business seems real and viable; the automation is concrete (e.g., "I spend 2 hours every morning copying orders from Shopify into QuickBooks")
- 7-8: Clear pain around a manual process, but either the process is vague or the business context is thin
- 5-6: Some automation angle, but the post is mostly a general question, a vent, or the pain is minor
- 3-4: Mentions automation keywords but isn't really about a solvable pain point (e.g., asking for SaaS ideas, or bragging)
- 1-2: False positive from keyword matching; not actually an automation opportunity

For each post, return:
- score (integer 1-10)
- pain_summary (one sentence: what manual process is hurting them)
- suggested_solution (one sentence: what kind of automation would help)
- reasoning (one sentence: why this score)

Return a JSON array, one object per post, in the SAME ORDER as input. Each object must have keys: id, score, pain_summary, suggested_solution, reasoning. Return ONLY the JSON array, no prose before or after.

Posts to analyze:
"""


def rank_posts(client: Anthropic, posts: list[dict]) -> list[dict]:
    """Send posts to Claude, get structured rankings back."""
    compact = [
        {
            "id": i,
            "subreddit": p["subreddit"],
            "title": p["title"],
            "body": p["body"],
        }
        for i, p in enumerate(posts)
    ]

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": RANKING_PROMPT + json.dumps(compact, indent=2),
        }],
    )

    text = resp.content[0].text.strip()
    # Strip markdown fences if the model added them despite instructions
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        if text.startswith("json"):
            text = text[4:].lstrip()

    try:
        rankings = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[error] failed to parse Claude's JSON: {e}", file=sys.stderr)
        print(f"[error] raw response:\n{text[:1000]}", file=sys.stderr)
        sys.exit(1)

    # Merge rankings back into post data
    by_id = {r["id"]: r for r in rankings}
    merged = []
    for i, p in enumerate(posts):
        r = by_id.get(i, {})
        merged.append({**p, **{k: v for k, v in r.items() if k != "id"}})
    return merged


def render_markdown(ranked: list[dict]) -> str:
    """Render ranked leads as a Markdown digest."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ranked_sorted = sorted(ranked, key=lambda r: r.get("score", 0), reverse=True)

    lines = [
        f"# SMB Automation Leads — {today}",
        "",
        f"Scanned r/smallbusiness, r/Entrepreneur, r/EntrepreneurRideAlong. "
        f"Found {len(ranked)} candidate posts after keyword pre-filter.",
        "",
        "---",
        "",
    ]

    high = [r for r in ranked_sorted if r.get("score", 0) >= 7]
    mid = [r for r in ranked_sorted if 5 <= r.get("score", 0) < 7]

    if high:
        lines += ["## 🔥 High-quality leads (score ≥ 7)", ""]
        for r in high:
            lines += _render_lead(r)
    else:
        lines += ["## 🔥 High-quality leads (score ≥ 7)", "", "_None today._", ""]

    if mid:
        lines += ["## 👀 Worth a look (score 5–6)", ""]
        for r in mid:
            lines += _render_lead(r, compact=True)

    lines += [
        "---",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat()} — "
        f"{len(high)} high-quality, {len(mid)} mid-quality, "
        f"{len(ranked) - len(high) - len(mid)} low-quality filtered out._",
    ]
    return "\n".join(lines)


def _render_lead(r: dict, compact: bool = False) -> list[str]:
    score = r.get("score", "?")
    title = r.get("title", "").strip()
    lines = [
        f"### [{score}/10] {title}",
        "",
        f"**r/{r['subreddit']}** · {r.get('num_comments', 0)} comments · "
        f"[View post]({r['url']})",
        "",
        f"**Pain:** {r.get('pain_summary', 'n/a')}  ",
        f"**Solution angle:** {r.get('suggested_solution', 'n/a')}  ",
    ]
    if not compact:
        lines += [
            f"**Why this score:** {r.get('reasoning', 'n/a')}",
            "",
        ]
        body_preview = r.get("body", "")[:400].replace("\n", " ")
        if body_preview:
            lines += [f"> {body_preview}{'…' if len(r.get('body', '')) > 400 else ''}", ""]
    else:
        lines += [""]
    return lines


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: rank_and_write.py <output_path>", file=sys.stderr)
        sys.exit(2)

    output_path = sys.argv[1]
    posts = json.load(sys.stdin)

    if not posts:
        md = f"# SMB Automation Leads — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n_No candidate posts found today._\n"
        with open(output_path, "w") as f:
            f.write(md)
        print(f"[info] no posts — wrote empty digest to {output_path}", file=sys.stderr)
        return

    # Cap posts sent to Claude
    if len(posts) > MAX_POSTS_TO_RANK:
        print(f"[info] capping {len(posts)} posts to top {MAX_POSTS_TO_RANK} by score", file=sys.stderr)
        posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)[:MAX_POSTS_TO_RANK]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[error] ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    ranked = rank_posts(client, posts)
    md = render_markdown(ranked)

    with open(output_path, "w") as f:
        f.write(md)
    print(f"[info] wrote digest to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
