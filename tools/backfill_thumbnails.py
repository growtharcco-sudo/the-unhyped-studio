"""Set the cover as the YouTube thumbnail for posted Shorts that don't have one yet (rebuilds the cover from the spec)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "pipeline"), os.path.join(ROOT, "poster")]
import render, youtube

for vid in sorted(os.listdir(os.path.join(ROOT, "posted"))):
    d = os.path.join(ROOT, "posted", vid); rp = os.path.join(d, "result.json"); sp = os.path.join(d, "spec.json")
    if not (os.path.exists(rp) and os.path.exists(sp)): continue
    res = json.load(open(rp))
    if not res.get("yt_video_id") or res.get("yt_thumbnail") == "set": continue
    cov = f"/tmp/{vid}_cover.png"; render.cover(json.load(open(sp)), cov)
    res["yt_thumbnail"] = youtube.set_thumbnail(res["yt_video_id"], cov, tries=1)
    print(vid, res["yt_video_id"], "->", res["yt_thumbnail"])
    json.dump(res, open(rp, "w"), indent=1)
