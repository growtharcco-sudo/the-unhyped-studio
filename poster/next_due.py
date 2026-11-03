"""Print seconds until the earliest queued post that is not skipped (0 if one is already due, -1 if none)."""
import datetime as dt, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
q = os.path.join(ROOT, "queue"); now = dt.datetime.now(dt.timezone.utc); best = None
for v in os.listdir(q) if os.path.isdir(q) else []:
    p = os.path.join(q, v, "post.json")
    if not os.path.exists(p) or os.path.exists(os.path.join(q, v, "SKIP")): continue
    post = json.load(open(p))
    s = (dt.datetime.fromisoformat(post["post_at"]) - now).total_seconds()
    if post.get("breaking"): s = max(s, 1800 - (now - dt.datetime.fromisoformat(post["post_at"])).total_seconds())
    best = s if best is None else min(best, s)
print(-1 if best is None else max(0, int(best)))
