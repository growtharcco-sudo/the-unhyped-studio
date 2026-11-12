"""Reel kit: a short brief -> a full spec, built from ready-made, pre-tested scene layouts.

Why: writing a long spec with coordinates and opening 15 to 20 stills per Reel is what costs Claude usage.
With the kit a Reel is a short brief: pick a scene kind, fill in words and numbers. Coordinates are fixed here,
and layout_check() catches text that is too wide or too low before anything is rendered.

Usage:  python pipeline/kit.py briefs/<id>.json      -> writes specs/<id>.json, exits 1 on LAYOUT PROBLEMS

Brief (briefs/<id>.json):
{
  "id": "009_slug", "series": "News", "style": "sheet",        # style: "sheet" (default, engine 1) or "keynote" (engine 4)
  "keywords": ["..."],                                          # optional, kept as caption_keywords (current captions
                                                                #   highlight the spoken word, so this changes nothing)
  "beats": [                                                    # one beat = one spoken phrase
    {"say": "...", "cap": "...", "pause": 0.3,                  # cap / pause optional
     "show": {"kind": "hook", ...}},                            # optional: starts a new scene at this beat
    ...],                                                       # beat 0 MUST have a show (the frame-0 hook)
  "cover": {...}, "sources": [...], "post": {...}, "math": [...]   # copied as-is (math is required when numbers are spoken)
}
"@n" below = beat n of THIS scene, counted from 0. Things that "appear in turn" are spread evenly over the scene's beats.

KEYNOTE kinds (black stage, one huge idea per screen, engine 4). In keynote, "show" may also be a LIST of screens:
the first starts with the beat, the others cut in later in the same phrase ("at": 0.5 = halfway; default evenly).
  hook       pill, lines=[1 to 3], hl ("words in orange")                 huge headline, visible at frame 0
  countdown  n (5), sub ("#5 is the strangest")                           row of numbered circles, last one orange
  step       n, label                                                     "03 / THE GROWTH" chapter card; sets the 0n/05 counter
  number     to, prefix, suffix, dec, label, sub, sub_at                  counts up, lands in orange
  swap       old, new, sub, new_at, sub_at (fractions of the phrase)     old value struck out, new one lands
  statement  text ("line\\nline"), hl, sub, size                           one big statement
  compare    left={title, lines=[up to 3]}, right={title, lines, hl: true}, mid   two cards side by side
  ending     text ("@theunhyped.ai"), sub ("Tech news. No hype.")         follow card
  photo      image ("assets/people/<name>.png"), lines=[1 to 2], hl, pill, sub, ring (orange frame)
             a real photo with a headline under it. ONLY photos the owner supplied (never download photos of people)

SHEET kinds (the light engineering-sheet look, engine 1). Every scene may set "sub" (the small header label).
  hook       kicker, number={prefix, value, suffix, decimals, final} (optional), lines=[1 to 2], hl, badge
             (lines and number at frame 0; badge appears @1, or at the end of a one-beat hook)
  myth       kicker ("Myth vs reality"), myth ("the claim"), badge ("MYTH")       claim struck out, badge lands
  number     label, prefix, value, suffix, decimals, final, line, hl, note        big counting number, line @1, note last
  swap       label, old, prefix, value, suffix, decimals, final, badge            old value struck, new number lands
  card       title, rows=[[LABEL, value, "hl"?]] (up to 5), big=[name, number], note   rows appear in turn
  cards      a={title, rows}, b={title, rows}, note                               two cards, b appears @1
  bars       label, bars=[{label, value, fill 0..1, color orange|blue, dashed}] (up to 4), note, badge
  steps      label, title, steps=[[step, small line]] (up to 4), hl=[indexes]   chain of cards with arrows
  statement  kicker, lines=[1 to 3], hl, size                                     big text lines, one per beat
  take       strike ("the claim to cross out", optional), lines=[2], hl            the "MY TAKE" ending
  refs       headline, site, line                                                 reference card + Follow button
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


class Scene:
    """Timing helper for one scene: b = global index of its first beat, nb = number of beats in it."""
    def __init__(s, b, nb, first):
        s.b, s.nb, s.first = b, nb, first
    def at(s, n=0, frac=0.0):
        n = max(0, min(n, s.nb - 1)); g = s.b + n
        if s.first and n == 0 and frac == 0: return -1
        return [g, round(frac, 3)] if frac else g
    def spread(s, i, count):
        """time for item i of count, spread evenly over the scene's beats"""
        if count <= 1: return s.at(0)
        p = i * s.nb / count; n = int(p); return s.at(n, p - n)
    def last(s, frac=0.0): return s.at(s.nb - 1, frac)


# ---------------- SHEET style (engine 1) ----------------
def card_h(rows, big=False): return 20 + (90 if big else 0) + 66 * len(rows) + 12


def sheet_block(kind, s, sc):
    at, els = sc.at, []
    def head(text, y, a, size=78, **k): return dict(type="head", text=text, y=y, at=a, size=size, **k)
    if kind == "hook":
        els.append(dict(type="kicker", text=s.get("kicker", ""), y=500, at=at()))
        lines = s["lines"][:2]
        if s.get("number"):
            n = s["number"]; els.append(dict(type="number", prefix=n.get("prefix", ""), value=n["value"], suffix=n.get("suffix", ""),
                                             decimals=n.get("decimals", 0), size=150, y=700, at=at(), **({"final": n["final"]} if n.get("final") else {})))
            ys, size = [820, 930], 76
        else:
            ys, size = [660, 780], 96
        for i, ln in enumerate(lines):
            hl = s.get("hl") if s.get("hl") and s["hl"] in ln else None
            els.append(head(ln, ys[i], at(), size, **({"hl": hl, "underline": True} if hl else {})))
        if s.get("badge"):
            els.append(dict(type="badge", text=s["badge"].upper(), color="orange", y=ys[len(lines) - 1] + 110 if len(lines) else 900,
                            at=at(1) if sc.nb > 1 else at(0, 0.8)))
    elif kind == "myth":
        els += [dict(type="kicker", text=s.get("kicker", "Myth vs reality"), y=500, at=at()),
                dict(type="strike", text=s["myth"], size=62, y=680, at=at(), strike_at=[sc.b, 0.75]),
                dict(type="badge", text=s.get("badge", "MYTH").upper(), color="orange", y=760, at=[sc.b, 0.8])]
    elif kind == "number":
        els.append(dict(type="kicker", text=s.get("label", ""), y=500, at=at()))
        els.append(dict(type="number", prefix=s.get("prefix", ""), value=s["value"], suffix=s.get("suffix", ""), decimals=s.get("decimals", 0),
                        size=s.get("size", 200), y=740, at=at(0, 0.3) if not sc.first else at(), **({"final": s["final"]} if s.get("final") else {})))
        if s.get("line"):
            hl = s.get("hl") if s.get("hl") and s["hl"] in s["line"] else None
            els.append(head(s["line"], 870, at(1) if sc.nb > 1 else at(0, 0.7), 76, **({"hl": hl, "underline": True} if hl else {})))
        if s.get("note"): els.append(dict(type="kicker", text=s["note"], color="muted", size=24, y=960, at=sc.last(0.3)))
    elif kind == "swap":
        els += [dict(type="kicker", text=s.get("label", ""), y=470, at=at()),
                dict(type="strike", text=s["old"], size=130, y=640, at=at(0, 0.2) if not sc.first else at(), strike_at=[sc.b, 0.5]),
                dict(type="number", prefix=s.get("prefix", ""), value=s["value"], suffix=s.get("suffix", ""), decimals=s.get("decimals", 0),
                     size=230, y=890, at=at(0, 0.6), dur=0.5, **({"final": s["final"]} if s.get("final") else {}))]
        if s.get("badge"): els.append(dict(type="badge", text=s["badge"].upper(), color="orange", size=28, y=945, at=sc.last(0.8)))
    elif kind == "card":
        rows = s["rows"][:5]; y = 490
        c = dict(type="card", y=y, at=at(), rows=rows, row_at=[sc.spread(i, len(rows)) for i in range(len(rows))])
        if s.get("title"): c["title"] = s["title"]
        if s.get("big"): c["big"] = s["big"]
        els.append(c)
        if s.get("note"): els.append(dict(type="kicker", text=s["note"], color="muted", size=24, y=y + card_h(rows, s.get("big")) + 70, at=sc.last(0.5)))
    elif kind == "cards":
        a, b2 = s["a"], s["b"]; ya = 480; yb = ya + card_h(a["rows"]) + 90
        n1 = max(1, sc.nb // 2)
        els.append(dict(type="card", title=a.get("title", ""), y=ya, at=at(), rows=a["rows"],
                        row_at=[at(int(i * n1 / max(1, len(a["rows"]))), (i * n1 / max(1, len(a["rows"]))) % 1) for i in range(len(a["rows"]))]))
        bt = at(1) if sc.nb > 1 else at(0, 0.5)
        els.append(dict(type="card", title=b2.get("title", ""), y=yb, at=bt, rows=b2["rows"],
                        row_at=[bt] + [sc.at(min(sc.nb - 1, 1 + i)) for i in range(1, len(b2["rows"]))]))
        if s.get("note"): els.append(dict(type="kicker", text=s["note"], color="muted", size=24, y=yb + card_h(b2["rows"]) + 50, at=sc.last(0.6)))
    elif kind == "bars":
        bars = s["bars"][:4]
        els.append(dict(type="kicker", text=s.get("label", ""), y=480, at=at()))
        for i, br in enumerate(bars):
            e = dict(type="bar", label=br["label"], value=br.get("value", ""), y=570 + 110 * i, at=sc.spread(i, len(bars)))
            for k in ("fill", "color", "dashed"):
                if k in br: e[k] = br[k]
            els.append(e)
        y = 570 + 110 * len(bars)
        if s.get("note"): els.append(dict(type="kicker", text=s["note"], color="muted", size=24, y=y + 10, at=sc.last(0.5))); y += 60
        if s.get("badge"): els.append(dict(type="badge", text=s["badge"].upper(), y=y + 10, at=sc.last(0.7)))
    elif kind == "steps":
        st = s["steps"][:4]
        els += [dict(type="kicker", text=s.get("label", ""), y=470, at=at()),
                dict(type="steps", title=s.get("title", ""), x=230, w=620, y=560, steps=st, at=at(),
                     step_at=[sc.spread(i, len(st)) for i in range(len(st))], **({"hl": s["hl"]} if "hl" in s else {}))]
    elif kind == "statement":
        lines = s["lines"][:3]; size = s.get("size", 84); y0 = 620
        if s.get("kicker"): els.append(dict(type="kicker", text=s["kicker"], y=480, at=at()))
        for i, ln in enumerate(lines):
            hl = s.get("hl") if s.get("hl") and s["hl"] in ln else None
            els.append(head(ln, y0 + i * int(size * 1.25), sc.spread(i, len(lines)), size, **({"hl": hl, "underline": True} if hl else {})))
    elif kind == "take":
        els.append(dict(type="badge", text="MY TAKE", color="orange", y=450, at=at()))
        ys = [740, 840] if s.get("strike") else [650, 750]
        if s.get("strike"): els.append(dict(type="strike", text=s["strike"], y=590, at=at(), delay=0.3, strike_at=[sc.b, 0.4]))
        for i, ln in enumerate(s["lines"][:2]):
            hl = s.get("hl") if s.get("hl") and s["hl"] in ln else None
            els.append(head(ln, ys[i], at(0, 0.5 + 0.2 * i) if sc.nb == 1 else sc.spread(i + 1, 3), 80,
                            **({"hl": hl, "underline": True} if hl else {})))
    elif kind == "refs":
        els += [dict(type="ref", y=440, at=at(), headline=s["headline"], site=s.get("site", ""), line=s.get("line", "")),
                dict(type="follow", y=min(1040, ref_bottom(s) + 120), at=at(), delay=0.2)]
    else:
        raise ValueError("unknown sheet scene kind: " + kind)
    return els


SHEET_SUB = {"myth": "Myth vs reality", "take": "My take", "refs": "References"}


def ref_bottom(s):
    sys.path.insert(0, HERE); import render as R
    f = R.font("sans", 50); lines = R.wrap(s["headline"], f, 800)
    return 440 + 70 + 58 * len(lines) + 50 + 48 * len(R.wrap(s.get("line", ""), R.font("sans5", 30), 800)) + 24


# ---------------- KEYNOTE style (engine 4) ----------------
KEY_MAP = {"hook": "title", "countdown": "dots", "step": "step", "number": "num", "swap": "swap",
           "statement": "big", "compare": "pair", "ending": "end", "photo": "photo"}


def keynote_beat(s, at):
    k = s["kind"]
    if k not in KEY_MAP: raise ValueError("unknown keynote scene kind: " + k)
    b = {"k": KEY_MAP[k], "at": at}
    i = at if isinstance(at, int) else (at[0] if isinstance(at, list) else 0)
    def frac(f): return [max(0, i), f]
    if k == "hook": b.update(pill=s.get("pill"), lines=s["lines"], hl=s.get("hl"), size=s.get("size", 150))
    elif k == "countdown": b.update(n=s.get("n", 5), sub=s.get("sub", f"#{s.get('n', 5)} is the strangest"), sub_at=frac(0.5))
    elif k == "step": b.update(n=s["n"], label=s["label"])
    elif k == "number":
        b.update(to=s["to"], dec=s.get("dec", 0), prefix=s.get("prefix", ""), suffix=s.get("suffix", ""))
        for f in ("label", "sub"):
            if s.get(f): b[f] = s[f]
        if s.get("sub"): b["sub_at"] = frac(s.get("sub_at", 0.4))
    elif k == "swap":
        b.update(old=s["old"], new=s["new"], new_at=frac(s.get("new_at", 0.5)))
        if s.get("sub"): b.update(sub=s["sub"], sub_at=frac(s.get("sub_at", min(0.95, s.get("new_at", 0.5) + 0.2))))
    elif k == "statement":
        b.update(text=s["text"] if isinstance(s.get("text"), str) else "\n".join(s["lines"]))
        for f in ("hl", "sub", "size"):
            if s.get(f): b[f] = s[f]
    elif k == "compare": b.update(left=s["left"], right=s["right"], right_at=frac(0.3), **({"mid": s["mid"]} if s.get("mid") else {}))
    elif k == "ending": b.update(text=s.get("text", "@theunhyped.ai"), sub=s.get("sub", "Tech news. No hype."))
    elif k == "photo": b.update(image=s["image"], lines=s["lines"], hl=s.get("hl"), pill=s.get("pill"), sub=s.get("sub"),
                                size=s.get("size", 100), ring=s.get("ring", False))
    return {x: y for x, y in b.items() if y is not None}


# ---------------- brief -> spec ----------------
def build_spec(brief):
    style = brief.get("style", "sheet")
    beats = brief["beats"]; phrases = []; starts = []
    for i, bt in enumerate(beats):
        ph = {"say": bt["say"]}
        if bt.get("cap"): ph["cap"] = bt["cap"]
        if bt.get("pause") is not None: ph["pause"] = bt["pause"]
        phrases.append(ph)
        if bt.get("show"): starts.append(i)
    if not starts or starts[0] != 0: raise ValueError("beat 0 must have a 'show' (the hook frame at frame 0)")
    spec = {"id": brief["id"], "series": brief["series"], "voice": brief.get("voice", "am_liam"), "speed": brief.get("speed", 1.05)}
    if brief.get("keywords"): spec["caption_keywords"] = brief["keywords"]
    if style == "keynote":
        out = []; step = 0
        for b in starts:
            shows = beats[b]["show"]; shows = shows if isinstance(shows, list) else [shows]
            for j, sh in enumerate(shows):
                f = sh.get("at", j / len(shows)) if j else 0
                at = -1 if (b == 0 and j == 0) else (b if f == 0 else [b, round(f, 3)])
                kb = keynote_beat(sh, at)
                if sh["kind"] == "step": step = sh["n"]
                if step and sh["kind"] != "ending": kb["step_no"] = step
                out.append(kb)
        spec.update(engine=4, steps=brief.get("steps", max([sh.get("n", 0) for b in starts for sh in
                    (beats[b]["show"] if isinstance(beats[b]["show"], list) else [beats[b]["show"]]) if sh["kind"] == "step"] or [5])),
                    phrases=phrases, beats=out)
    elif style == "sheet":
        scenes = []
        for k, b in enumerate(starts):
            nxt = starts[k + 1] if k + 1 < len(starts) else len(beats)
            sh = beats[b]["show"]; sc = Scene(b, nxt - b, b == 0)
            scenes.append({"until": nxt if k + 1 < len(starts) else "end",
                           "sub": sh.get("sub", SHEET_SUB.get(sh["kind"], brief["series"] if b == 0 else "")),
                           "els": sheet_block(sh["kind"], sh, sc)})
        spec.update(engine=1, dwg=brief.get("dwg", brief["id"][:3]), phrases=phrases, scenes=scenes)
    else:
        raise ValueError("style must be 'keynote' or 'sheet'")
    for k in ("cover", "sources", "post", "math"):
        if k in brief: spec[k] = brief[k]
    return spec


# ---------------- layout check ----------------
def layout_check(spec):
    """Text too wide for the frame, or anything reaching into the caption zone. Cheap, no rendering."""
    sys.path.insert(0, HERE); probs = []
    if spec.get("engine") == 4:
        import render4 as R
        cap_top = R.CAP_Y - R.CAP_SIZE - 40
        for i, b in enumerate(spec["beats"]):
            k = b["k"]; tag = f"screen {i} ({k})"
            if k in ("title", "big"):
                lines = b["lines"] if k == "title" else b["text"].split("\n")
                size = R.fit(lines, 900, b.get("size", 150 if k == "title" else 112), 920, -0.03)
                if size < 84: probs.append(f'{tag}: text shrinks to {size}px, too long: "{" / ".join(lines)}"')
                bottom = R.CY + (len(lines) - 1) * size * 1.02 / 2 + size * 0.36 + (90 + 58 * len(b.get("sub", "").split("\n")) if b.get("sub") else 0)
                if len(lines) > 3: probs.append(f"{tag}: more than 3 lines")
                if bottom > cap_top: probs.append(f"{tag}: reaches the caption zone (bottom {int(bottom)} > {cap_top})")
            if k == "step" and R.tw(b["label"].upper(), R.font(800, 84), -1) > 940: probs.append(f'{tag}: label too wide: "{b["label"]}"')
            if k == "num":
                s = f"{b.get('prefix', '')}{b['to']:,.{b.get('dec', 0)}f}{b.get('suffix', '')}"
                if R.fit([s], 900, 330, 940) < 150: probs.append(f'{tag}: number too long: "{s}"')
            if k == "swap":
                if R.tw(b["old"], R.font(800, 150)) > 940: probs.append(f'{tag}: old value too wide: "{b["old"]}"')
                if R.fit([b["new"]], 900, 300, 940, -0.04) < 150: probs.append(f'{tag}: new value too long: "{b["new"]}"')
            if k == "pair":
                for side in ("left", "right"):
                    c = b[side]
                    if R.tw(c["title"], R.font(900, 64), -2) > 360: probs.append(f'{tag}: {side} title too wide: "{c["title"]}"')
                    if len(c.get("lines", [])) > 3: probs.append(f"{tag}: {side} has more than 3 lines")
                    for ln in c.get("lines", []):
                        if R.tw(ln, R.font(600, 40)) > 360: probs.append(f'{tag}: {side} line too wide: "{ln}"')
            if k == "end" and R.tw(b.get("text", ""), R.font(900, 110), -3) > 940: probs.append(f'{tag}: text too wide')
            if k == "photo":
                if not os.path.exists(os.path.join(ROOT, b["image"])): probs.append(f'{tag}: image not found: {b["image"]}')
                if len(b["lines"]) > 2: probs.append(f"{tag}: more than 2 lines under a photo")
                size = R.fit(b["lines"], 900, b.get("size", 100), 940, -0.03)
                if size < 70: probs.append(f'{tag}: headline shrinks to {size}px, too long')
                bottom = 430 + 540 + 40 + size * 0.8 + (len(b["lines"]) - 1) * size * 1.02 + (50 if b.get("sub") else 0)
                if bottom > cap_top: probs.append(f"{tag}: reaches the caption zone (bottom {int(bottom)} > {cap_top})")
            for ln in (b.get("sub") or "").split("\n"):
                size = 58 if k == "dots" else 48 if k == "end" else 46
                if ln and R.tw(ln, R.font(600, size)) > 940: probs.append(f'{tag}: sub line too wide: "{ln}"')
            if b.get("pill") and R.tw(b["pill"], R.mono(30), 5) > 860: probs.append(f"{tag}: pill too wide")
        return probs
    import render as R
    cap_top = R.CAP_Y - R.CAP_SIZE - 30
    for si, sc in enumerate(spec["scenes"]):
        for e in sc["els"]:
            t = e["type"]; tag = f'scene {si} ({sc.get("sub", "")}) {t}'; w = 0; bottom = e.get("y", 0)
            if t == "head":
                f = R.font("sans", e.get("size", 78)); lines = e["text"].split("\n") if "\n" in e["text"] else R.wrap(e["text"], f, 900)
                if len(lines) > 1 and "\n" not in e["text"]: probs.append(f'{tag}: wraps to {len(lines)} lines: "{e["text"]}"')
                w = max(R.text_w(l, f) for l in lines); bottom += (len(lines) - 1) * e.get("size", 78) * 1.14 + 20
            elif t == "kicker": w = R.text_w(e["text"].upper(), R.font("mono", e.get("size", 28)), 5)
            elif t == "strike": w = R.text_w(e["text"], R.font("sans", e.get("size", 52)))
            elif t == "number":
                s = e.get("final") or f"{e.get('prefix', '')}{e['value']:,.{e.get('decimals', 0)}f}{e.get('suffix', '')}"
                w = R.text_w(s, R.font("sans", e.get("size", 180)))
            elif t == "badge": w = R.text_w(e["text"], R.font("mono6", e.get("size", 24)), 3) + 32; bottom += e.get("size", 24) + 26
            elif t == "card":
                bottom += card_h(e.get("rows", []), e.get("big"))
                for r in e.get("rows", []):
                    if R.text_w(r[1], R.font("sans6", 32)) > 820 - 256 - 26: probs.append(f'{tag}: row value too wide: "{r[1]}"')
                    if R.text_w(r[0].upper(), R.font("mono", 20), 2) > 256 - 40: probs.append(f'{tag}: row label too wide: "{r[0]}"')
                if e.get("title"): w = R.text_w(e["title"].upper(), R.font("mono", 26), 5)
            elif t == "bar":
                bottom += 48
                if R.text_w(e["label"].upper(), R.font("mono", 22), 2) + R.text_w(e.get("value", ""), R.font("mono", 22), 2) + 30 > 820:
                    probs.append(f'{tag}: label and value overlap: "{e["label"]}"')
            elif t == "steps":
                bottom += 120 * (len(e["steps"]) - 1) + 85
                for st in e["steps"]:
                    if R.text_w(st[0], R.font("sans6", 32)) > 620 - 90: probs.append(f'{tag}: step too wide: "{st[0]}"')
            elif t == "ref": bottom = ref_bottom({"headline": e["headline"], "line": e.get("line", "")})
            elif t == "follow": w = R.text_w("Follow " + e.get("handle", "@theunhyped.ai"), R.font("sans", 52)) + 28; bottom += 20
            if w > 940: probs.append(f'{tag}: too wide ({int(w)}px): "{e.get("text", e.get("final", ""))}"')
            if bottom > cap_top: probs.append(f"{tag}: reaches the caption zone (bottom {int(bottom)} > {cap_top})")
    return probs


if __name__ == "__main__":
    brief = json.load(open(sys.argv[1])); spec = build_spec(brief)
    out = os.path.join(ROOT, "specs", f'{spec["id"]}.json')
    json.dump(spec, open(out, "w"), indent=1, ensure_ascii=False)
    print("wrote", os.path.relpath(out, ROOT))
    probs = layout_check(spec)
    if probs: print("LAYOUT PROBLEMS:\n  " + "\n  ".join(probs)); sys.exit(1)
    print("layout ok")
