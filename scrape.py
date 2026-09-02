#!/usr/bin/env python3
"""Scrape a YouTube playlist's videos + view/like counts into data.json.

No API key and no third-party packages - it reads the public watch pages.
Usage: python scrape.py [PLAYLIST_ID]
"""
import datetime, json, re, sys, time, urllib.request, urllib.error

PLAYLIST = sys.argv[1] if len(sys.argv) > 1 else "PLpH_4mf13-A2GgNLVfExG8f5H98EyVSfL"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
           "Cookie": "CONSENT=YES+cb; SOCS=CAI"}


def get(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            return urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
        except Exception as exc:
            if attempt == tries - 1:
                raise
            print(f"  retry {attempt + 1} ({exc})", flush=True)
            time.sleep(3 * (attempt + 1))


def to_int(text):
    text = text.replace(",", "").strip()
    mult = {"K": 1e3, "M": 1e6, "B": 1e9}
    if text and text[-1] in mult:
        return int(float(text[:-1]) * mult[text[-1]])
    try:
        return int(float(text))
    except ValueError:
        return 0


def playlist_items(pid):
    html = get(f"https://www.youtube.com/playlist?list={pid}&hl=en&gl=US")
    blob = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not blob:
        raise SystemExit("could not find ytInitialData - YouTube markup changed or the request was blocked")
    data = json.loads(blob.group(1))
    found, seen = [], set()

    def walk(node):
        if isinstance(node, dict):
            lockup = node.get("lockupViewModel")
            if lockup:
                vid = lockup.get("contentId")
                try:
                    title = lockup["metadata"]["lockupMetadataViewModel"]["title"]["content"]
                except (KeyError, TypeError):
                    title = ""
                if vid and vid not in seen:
                    seen.add(vid)
                    found.append({"id": vid, "title": title})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    name = re.search(r'<meta name="title" content="([^"]*)"', html)
    return (name.group(1) if name else ""), found


def video_stats(item):
    html = get(f"https://www.youtube.com/watch?v={item['id']}&hl=en&gl=US")
    views = None
    for pat in (r'"viewCount":"(\d+)"',
                r'"viewCount":\{"simpleText":"([\d,]+) view',
                r'"videoViewCountRenderer".{0,200}?"simpleText":"([\d,]+) view',
                r'itemprop="interactionCount" content="(\d+)"',
                r'"interactionCount":"(\d+)"',
                r'"viewCountText":\{"simpleText":"([\d,]+) view',
                r'([\d,]+) views"'):
        m = re.search(pat, html)
        if m and to_int(m.group(1)) > 0:
            views = m
            break
    likes = re.search(r'"accessibilityText":"([\d.,KMB]+) likes?"', html)
    if likes:
        like_count = to_int(likes.group(1))
    else:
        alt = re.search(r"like this video along with ([\d,]+) other people", html)
        like_count = to_int(alt.group(1)) + 1 if alt else 0
    date = None
    for pat in (r'"publishDate":"([^"]+)"', r'"uploadDate":"([^"]+)"',
                r'itemprop="(?:datePublished|uploadDate)" content="([^"]+)"',
                r'"publishedTimeText":\{"simpleText":"([^"]+)"'):
        date = re.search(pat, html)
        if date:
            break
    channel = None
    for pat in (r'"author":"([^"]+)"', r'"ownerChannelName":"([^"]+)"',
                r'<link itemprop="name" content="([^"]+)"',
                r'"videoOwnerChannelName":"([^"]+)"'):
        channel = re.search(pat, html)
        if channel:
            break
    length = re.search(r'"lengthSeconds":"(\d+)"', html)
    return {"id": item["id"], "title": item["title"],
            "views": to_int(views.group(1)) if views else 0,
            "likes": like_count,
            "date": date.group(1)[:10] if date else "",
            "channel": channel.group(1) if channel else "",
            "duration": int(length.group(1)) if length else 0}


def main():
    title, items = playlist_items(PLAYLIST)
    print(f"{title}: {len(items)} videos", flush=True)
    if not items:
        raise SystemExit("no videos found - refusing to overwrite data.json")

    try:
        with open("data.json", encoding="utf-8") as fh:
            known = {r["id"]: r for r in json.load(fh)}
    except Exception:
        known = {}

    rows, failed = [], []
    for i, item in enumerate(items, 1):
        try:
            row = video_stats(item)
        except Exception as exc:
            print(f"{i:3}/{len(items)} FAILED {item['id']}: {exc}", flush=True)
            failed.append(item["id"])
            continue
        # YouTube withholds some fields from datacenter IPs; keep the last
        # good value rather than blanking the page out.
        old = known.get(row["id"], {})
        for field in ("title", "channel", "date", "duration"):
            if not row.get(field) and old.get(field):
                row[field] = old[field]
        rows.append(row)
        print(f"{i:3}/{len(items)} {row['views']:>7} views {row['likes']:>5} likes  {row['title'][:45]}", flush=True)
        time.sleep(0.5)

    if len(rows) < len(items) * 0.8:
        raise SystemExit(f"only {len(rows)}/{len(items)} videos scraped - refusing to overwrite data.json")

    # Sanity guards: YouTube sometimes withholds counts from datacenter IPs and
    # returns pages with no view numbers at all. Never let that clobber good data.
    total = sum(r["views"] for r in rows)
    zeros = sum(1 for r in rows if r["views"] == 0)
    if total == 0 or zeros > len(rows) * 0.5:
        raise SystemExit(f"view counts look withheld ({zeros}/{len(rows)} at zero) - refusing to overwrite data.json")
    previous = sum(r["views"] for r in known.values())
    if previous and total < previous * 0.5:
        raise SystemExit(f"total views fell {previous} -> {total} - refusing to overwrite data.json")

    with open("data.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open("updated.txt", "w", encoding="utf-8") as fh:
        fh.write(stamp + chr(10))
    print(f"wrote data.json ({len(rows)} videos, {len(failed)} failed) at {stamp}")


if __name__ == "__main__":
    main()
