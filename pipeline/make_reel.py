"""spec.json -> check -> voice -> video -> cover -> queue/<id>/

Usage:
  python pipeline/make_reel.py specs/<id>.json            # full build into queue/<id>/
  python pipeline/make_reel.py specs/<id>.json --stills   # quick check frames only (queue/<id>/check.still_*.png)
  python pipeline/make_reel.py specs/<id>.json --check    # rules check only, no voice, no video
"""
import datetime as dt, json, math, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
BRAND_TAG = "#theunhyped"
SLOTS = {"morning": (18, 38), "news": (35, 58), "evening": (40, 62), "breaking": (35, 58)}


def check_spec(spec, allow_old_sources=False):
    """Hard rules from the channel playbook. Fails loudly instead of posting something wrong."""
    errs = []
    post = spec.get("post", {})
    for k in ("post_at", "slot", "instagram_caption", "youtube_title", "youtube_description"):
        if not post.get(k): errs.append(f"post.{k} is missing")
    if post.get("slot") not in SLOTS: errs.append(f"post.slot must be one of {list(SLOTS)}")
    if post.get("breaking") != (post.get("slot") == "breaking"): errs.append("post.breaking must be true exactly when slot is 'breaking'")
    try:
        when = dt.datetime.fromisoformat(post.get("post_at", ""))
        if when.tzinfo is None: errs.append("post.post_at needs a timezone, like 2026-11-04T22:00:00+05:30")
    except ValueError:
        errs.append("post.post_at is not an ISO time")
    every = json.dumps(spec, ensure_ascii=False)
    if "—" in every: errs.append("em dash found (channel rule: no em dashes)")
    if "–" in every: errs.append("en dash found (use a comma, colon, 'to' or a hyphen)")
    # Instagram caption: ends with a real question, then exactly 5 hashtags including the brand tag
    ig = post.get("instagram_caption", "")
    paras = [p.strip() for p in ig.strip().split("\n\n") if p.strip()]
    tags = re.findall(r"#\w+", ig)
    if len(tags) != 5: errs.append(f"Instagram caption needs exactly 5 hashtags, has {len(tags)}")
    if BRAND_TAG not in [t.lower() for t in tags]: errs.append(f"Instagram caption must include {BRAND_TAG}")
    if paras and not all(w.startswith("#") for w in paras[-1].split()): errs.append("Instagram caption must end with the hashtag line")
    if len(paras) < 2 or not paras[-2].rstrip().endswith("?"): errs.append("Instagram caption: the line just before the hashtags must be a real question")
    if len(ig) > 2200: errs.append("Instagram caption over 2,200 characters")
    yt = post.get("youtube_description", "")
    if len(post.get("youtube_title", "")) > 100: errs.append("YouTube title over 100 characters")
    if "#shorts" in post.get("youtube_title", "").lower(): errs.append("no #Shorts in the YouTube title")
    if "Sources:" not in yt: errs.append("YouTube description needs a 'Sources:' list")
    if "#Shorts" not in yt: errs.append("YouTube description must end with 3 hashtags including #Shorts")
    if len(re.findall(r"#\w+", yt)) != 3: errs.append("YouTube description needs exactly 3 hashtags")
    # sources: fetched today, every number backed by a Python-checked calculation
    src = spec.get("sources", [])
    if not src: errs.append("spec.sources is empty: every fact needs a source")
    today = dt.datetime.now(IST).date().isoformat()
    for i, s in enumerate(src):
        if not s.get("url", "").startswith("http"): errs.append(f"sources[{i}] has no url")
        if not allow_old_sources and s.get("fetched") != today: errs.append(f"sources[{i}] must be fetched today ({today}), has {s.get('fetched')}")
    for i, m in enumerate(spec.get("math", [])):
        try:
            v = eval(m["expr"], {"__builtins__": {}}, {"round": round, "abs": abs, "min": min, "max": max, "int": int, "float": float, "sum": sum, "math": math})
            if abs(v - float(m["expect"])) > float(m.get("tol", 0.005)) * max(1, abs(float(m["expect"]))):
                errs.append(f"math[{i}] {m['expr']} = {v}, but the script says {m['expect']}")
        except Exception as e:
            errs.append(f"math[{i}] could not run: {e}")
    nums = re.findall(r"\d", " ".join(p.get("cap", p.get("say", "")) for p in spec.get("phrases", [])))
    if nums and not spec.get("math"): errs.append("the script has numbers but spec.math is empty: compute every derived number in Python")
    # hook on the very first frame
    first = spec.get("scenes", [{}])[0].get("els", [])
    if not any(e.get("at") == -1 for e in first): errs.append("scene 1 needs at least one element with \"at\": -1 (the hook on frame 1)")
    for e in (x for sc in spec.get("scenes", []) for x in sc.get("els", [])):
        y = e.get("y", 600)
        if e.get("type") != "block" and not (400 <= y <= 1080): errs.append(f"{e.get('type')} at y {y}: keep visuals between y 400 and 1080")
    if not spec.get("cover", {}).get("lines"): errs.append("cover.lines is missing")
    for bad in ("guaranteed", "you should buy", "buy now", "100% sure", "will 10x"):
        if bad in every.lower(): errs.append(f"forbidden phrase: {bad!r}")
    if errs: raise SystemExit("SPEC CHECK FAILED:\n- " + "\n- ".join(errs))


def main():
    path = sys.argv[1]
    spec = json.load(open(path))
    check_spec(spec, allow_old_sources="--allow-old-sources" in sys.argv)
    if "--check" in sys.argv: print("spec OK"); return
    import voice, importlib
    render = importlib.import_module({1: "render", 2: "render2", 3: "render3"}[spec.get("engine", 1)])
    out = os.path.join(ROOT, "queue", spec["id"])
    os.makedirs(out, exist_ok=True)
    wav = os.path.join(out, "voice.wav")
    _, times, total, words = voice.synth(spec["phrases"], wav, spec.get("voice", voice.VOICE), spec.get("speed", 1.05))
    json.dump({"phrase_times": times, "total": total, "words": words}, open(os.path.join(out, "timing.json"), "w"), indent=1)
    lo, hi = SLOTS[spec["post"]["slot"]]
    if not lo <= total <= hi:
        raise SystemExit(f"LENGTH CHECK FAILED: {total:.1f}s, a {spec['post']['slot']} Reel must be {lo} to {hi} seconds")
    if "--stills" in sys.argv:
        ts = [0.0] + [round(s + (e - s) * 0.8, 2) for s, e in times]
        render.render(spec, times, total, wav, os.path.join(out, "check"), stills=ts, words=words)
        render.cover(spec, os.path.join(out, "check.cover.png"))
        print("stills written to", out); return
    mp4 = os.path.join(out, "video.mp4")
    render.render(spec, times, total, wav, mp4, words=words)
    render.cover(spec, os.path.join(out, "cover.png"))
    os.remove(wav)
    for f in os.listdir(out):
        if f.startswith("check."): os.remove(os.path.join(out, f))
    shutil.copy(path, os.path.join(out, "spec.json"))
    json.dump(spec["post"], open(os.path.join(out, "post.json"), "w"), indent=1, ensure_ascii=False)
    print(f"ready: {mp4} ({total:.1f}s), post_at {spec['post']['post_at']}")


if __name__ == "__main__":
    main()
