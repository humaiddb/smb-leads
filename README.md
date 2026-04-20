# SMB Automation Lead Scanner

Daily scan of r/smallbusiness, r/Entrepreneur, and r/EntrepreneurRideAlong for small business owners describing manual processes that could be automated. Runs on GitHub Actions at 9:00 AM Dubai time and commits a ranked Markdown digest back to this repo.

## How it works

1. **Fetch** — `scripts/fetch_reddit.py` pulls the last ~26 hours of posts from the three subreddits and keyword-filters for automation pain signals ("manually", "hours a day", "is there a way", etc.)
2. **Rank** — `scripts/rank_and_write.py` sends the filtered candidates to Claude, which scores each 1–10 on automation-opportunity quality and returns structured JSON
3. **Write** — The ranked results are rendered as `leads/YYYY-MM-DD.md` and committed back to the repo

## Setup

1. **Create the repo** on GitHub (private is fine) and push these files
2. **Add your Anthropic API key** as a repo secret:
   - Repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `ANTHROPIC_API_KEY`
   - Value: your API key from console.anthropic.com
3. **Test it manually** — go to the Actions tab, pick "Daily SMB Lead Scan", click "Run workflow". First run should take 1–2 min.
4. **Check `leads/`** — your first digest should appear there.

After that it runs automatically at 05:00 UTC daily.

## Reading the output

Each day's file is split into two sections:
- **🔥 High-quality leads (≥7)** — worth reaching out; clear pain, concrete process
- **👀 Worth a look (5–6)** — maybe, if you have time

Each lead shows the pain summary, a suggested automation angle, and a link back to the original Reddit post.

## Tuning

- **Different subreddits** — edit `SUBREDDITS` in `fetch_reddit.py`
- **Different keywords** — edit `PAIN_SIGNALS` in the same file
- **Different model** — change `MODEL` in `rank_and_write.py` (defaults to `claude-opus-4-5`; swap to `claude-sonnet-4-5` for ~5x lower cost)
- **Different schedule** — edit the cron expression in `.github/workflows/daily-scan.yml`

## Gotchas

- GitHub Actions cron can drift 5–15 min during peak load. 9 AM might actually be 9:10 AM some days.
- Scheduled workflows on free accounts pause after 60 days of no repo activity. The daily commit keeps this repo active, so you're fine.
- Reddit's public JSON endpoint is unauthenticated and occasionally rate-limited. If you see empty results several days running, swap to PRAW with a free Reddit app.
