# Make a Sign Contest 2026 — Playlist Leaderboard

A single-page leaderboard for the YouTube playlist
[Make a Sign Contest 2026](https://www.youtube.com/playlist?list=PLpH_4mf13-A2GgNLVfExG8f5H98EyVSfL).

Sort all 48 entries by views, likes, like-to-view ratio, upload date, or original playlist order, and search by title/channel.

- `index.html` — the whole site (no build step, no dependencies)
- `data.json` — snapshot of the playlist stats

To refresh the numbers, regenerate `data.json` and commit it.

## Auto-refresh

`.github/workflows/refresh.yml` runs `scrape.py` every day at 05:17 UTC, and commits
`data.json` + `updated.txt` only if the numbers actually changed. You can also trigger it
by hand from the repo's **Actions** tab → *Refresh playlist stats* → *Run workflow*.

Run it locally with `python scrape.py` (no dependencies, Python 3.8+).
