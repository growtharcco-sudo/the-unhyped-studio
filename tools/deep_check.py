"""End-to-end test of both upload paths. Publishes NOTHING publicly.
Instagram: creates a Reel container from the hosted test video and waits until Instagram has processed it
(proves token, permission, hosting and video format). The container is never published and expires in 24h.
YouTube: uploads the test video as PRIVATE (proves token, API and upload). Delete it in YouTube Studio afterwards."""
import os, sys, time, requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "poster"))
import instagram, youtube
PAGES = os.environ["PAGES_BASE"].rstrip("/"); url = f"{PAGES}/_test/video.mp4"; ok = True
r = requests.head(url, timeout=30); print("Hosting:", "OK" if r.ok else "FAILED", r.status_code, url); ok &= r.ok
tok, uid = os.environ["IG_TOKEN"], os.environ["IG_USER_ID"]; B = instagram._base(tok)
c = requests.post(f"{B}/{uid}/media", data={"media_type": "REELS", "video_url": url, "caption": "test",
                  "share_to_feed": "false", "access_token": tok}, timeout=60)
if not c.ok: print("Instagram: FAILED to create container", c.status_code, c.text[:400]); ok = False
else:
    cid = c.json()["id"]; st = {}
    for _ in range(40):
        st = requests.get(f"{B}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
        if st.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"): break
        time.sleep(10)
    print("Instagram: processed the video ->", st.get("status_code"), "(not published)" if st.get("status_code") == "FINISHED" else st)
    ok &= st.get("status_code") == "FINISHED"
if os.environ.get("SKIP_YT") == "1":
    print("YouTube: skipped this run"); print("ALL OK" if ok else "SOMETHING FAILED"); sys.exit(0 if ok else 1)
local = "/tmp/t.mp4"; open(local, "wb").write(requests.get(url, timeout=120).content)
try:
    pv = os.environ.get("TEST_PRIVACY", "private"); pv = pv if pv in ("private", "unlisted") else "private"
    res = youtube.upload_short(local, "Pipeline test (safe to delete)", f"Automated test upload. {pv.title()}.", privacy=pv)
    print("YouTube: upload OK ->", res["yt_url"], "requested:", pv, "API says:", res["yt_privacy"])
    if pv == "unlisted":
        # YouTube locks uploads from unaudited projects to private a little after upload; an unlisted video
        # answers oEmbed, a private one doesn't. Check for ~5 minutes.
        vid = res["yt_video_id"]; verdict = None
        for _ in range(10):
            time.sleep(30)
            r = requests.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"}, timeout=30)
            verdict = r.status_code
            if r.status_code in (401, 403): break
        print("YouTube visibility check:", "STAYED UNLISTED -> public uploads will work" if verdict == 200 else f"LOCKED TO PRIVATE (oEmbed {verdict}) -> needs the API audit")
except Exception as e:
    print("YouTube: FAILED", e); ok = False
print("ALL OK" if ok else "SOMETHING FAILED"); sys.exit(0 if ok else 1)
