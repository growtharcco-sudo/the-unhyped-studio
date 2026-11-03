"""Post every queued Reel whose time has come. Runs in GitHub Actions.

queue/<id>/post.json   caption, titles, post_at (ISO time with timezone)
queue/<id>/SKIP        if present, the post is cancelled (the veto)
media branch <id>/video.mp4, <id>/cover.png, served at $PAGES_BASE/<id>/...

Safe to re-run: what was already posted is recorded in queue/<id>/result.json and never posted twice.
"""
import datetime as dt, json, os, shutil, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry-run" in sys.argv
BREAKING_ONLY = "--breaking-only" in sys.argv   # used by the instant "post now" workflow
PAGES = os.environ.get("PAGES_BASE", "").rstrip("/")


def wait_public(url, tries=30):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200: return True
        except Exception:
            pass
        time.sleep(10)
    raise RuntimeError(f"not reachable yet: {url}")


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
MAX_BREAKING_PER_DAY = 2


def breaking_days():
    """How many breaking Reels went out on each IST day (from posted/*/post.json + result.json)."""
    days = {}
    pd = os.path.join(ROOT, "posted")
    for v in os.listdir(pd) if os.path.isdir(pd) else []:
        try:
            post = json.load(open(os.path.join(pd, v, "post.json"))); res = json.load(open(os.path.join(pd, v, "result.json")))
        except Exception:
            continue
        if post.get("breaking") and res.get("posted_at"):
            d = dt.datetime.fromisoformat(res["posted_at"]).astimezone(IST).date(); days[d] = days.get(d, 0) + 1
    return days


def veto(d, vid, reason):
    print(f"{vid}: cancelled ({reason})"); open(os.path.join(d, "SKIP"), "w").write(reason + "\n")


def main():
    now = dt.datetime.now(dt.timezone.utc)
    if not PAGES and not DRY: raise SystemExit("PAGES_BASE is not set")
    qdir = os.path.join(ROOT, "queue"); failures = 0; changed = False
    os.makedirs(os.path.join(ROOT, "posted"), exist_ok=True)
    for vid in sorted(os.listdir(qdir)) if os.path.isdir(qdir) else []:
        d = os.path.join(qdir, vid); pj = os.path.join(d, "post.json")
        if not os.path.exists(pj): continue
        post = json.load(open(pj))
        if os.path.exists(os.path.join(d, "SKIP")):
            print(f"{vid}: skipped (veto)"); os.makedirs(os.path.join(ROOT, "posted"), exist_ok=True); shutil.move(d, os.path.join(ROOT, "posted", vid + "__skipped")); changed = True; continue
        when = dt.datetime.fromisoformat(post["post_at"])
        if BREAKING_ONLY and not post.get("breaking"): continue
        if when <= now and not DRY and not os.path.exists(os.path.join(d, "result.json")):
            bd = breaking_days().get(when.astimezone(IST).date(), 0)
            # a breaking Reel replaces that day's news Reel, and there are at most 2 breaking Reels a day
            if post.get("slot") == "news" and bd:
                veto(d, vid, "a breaking Reel already replaced today's news Reel")
                shutil.move(d, os.path.join(ROOT, "posted", vid + "__skipped")); changed = True; continue
            if post.get("breaking") and bd >= MAX_BREAKING_PER_DAY:
                veto(d, vid, f"already {bd} breaking Reels today")
                shutil.move(d, os.path.join(ROOT, "posted", vid + "__skipped")); changed = True; continue
        # breaking posts belong to the instant workflow; the scheduled one only picks them up as a fallback
        if not BREAKING_ONLY and post.get("breaking") and (now - when).total_seconds() < 1800: continue
        if when > now:
            print(f"{vid}: not due until {when.isoformat()}"); continue
        rp = os.path.join(d, "result.json")
        res = json.load(open(rp)) if os.path.exists(rp) else {}
        video_url, cover_url = f"{PAGES}/{vid}/video.mp4", f"{PAGES}/{vid}/cover.png"
        print(f"{vid}: due, posting. video {video_url}")
        if DRY: continue
        try:
            wait_public(video_url)
            if "yt_video_id" not in res:
                import youtube
                local = os.path.join(d, "video.mp4")
                urllib.request.urlretrieve(video_url, local)
                res.update(youtube.upload_short(local, post["youtube_title"], post["youtube_description"],
                                                post.get("youtube_tags")))
                os.remove(local)
                json.dump(res, open(rp, "w"), indent=1); print("  YouTube:", res["yt_url"], res.get("yt_privacy"))
            if "ig_media_id" not in res:
                import instagram
                res.update(instagram.publish_reel(video_url, post["instagram_caption"], cover_url))
                json.dump(res, open(rp, "w"), indent=1); print("  Instagram:", res.get("ig_permalink"))
            res["posted_at"] = now.isoformat(); json.dump(res, open(rp, "w"), indent=1)
            os.makedirs(os.path.join(ROOT, "posted"), exist_ok=True)
            shutil.move(d, os.path.join(ROOT, "posted", vid)); changed = True
        except Exception as e:                      # record and keep going; the run is marked failed at the end
            failures += 1; res["last_error"] = f"{now.isoformat()} {e}"
            json.dump(res, open(rp, "w"), indent=1); changed = True
            print(f"  FAILED: {e}")
    open(os.path.join(ROOT, ".changed"), "w").write("1" if changed else "0")
    if failures: sys.exit(1)


if __name__ == "__main__":
    main()
