"""The Unhyped engine v5, "Stick" style: a stickman explainer on the black keynote stage.

The stickman ("Unhyped", white lines, orange glasses) stays on screen the whole Reel and moves between poses,
his mouth moves with the voice, and "Bit" (a small orange robot) pops in with speech bubbles. Each beat swaps
the headline and the prop on the right; the stickman never cuts, so it feels like one little story.
Same stage, captions, music and sound effects as engine 4.

Spec: "engine": 5 and "beats": [{"k": "scene", "at": -1 | i | [i, frac], "head": "line\\nline", "hl": "words",
  "sub": "...", "pose": idle|point|shrug|swipe|sign|wave|facepalm, "sign": "NO AND NO.",
  "prop": {"kind": phone|battery|drains|settings|big, ...}, "bit": "bubble text" (optional)}]
Props: phone {state: swipe|standby}, battery {label}, drains {items: [[icon, label], ...]} (icons: sun, pin, note,
       wifi, bolt), settings {path, rows: [label, ...]}, big {text, hl} (one big word or number).
Safe area: headline y 400 to 640, stickman x 140 to 460, props x 560 to 1010, everything above y 1260.
"""
import math, os, subprocess
import numpy as np
import skia
import render as v1
import render4 as R
from render3 import Env

W, H, FPS = R.W, R.H, R.FPS
C, paint, text, font, mono, ease, tw, fit, rich_line = R.C, R.paint, R.text, R.font, R.mono, R.ease, R.tw, R.fit, R.rich_line
WHITE = "#F4F4F5"; HIP = (300, 1035)

# pose = points relative to the hip: left elbow, left hand, right elbow, right hand, left knee, left foot, right knee, right foot
LEGS = [(-24, 88), (-42, 178), (24, 88), (42, 178)]
POSES = {
    "idle":     [(-42, -118), (-52, -32), (42, -118), (52, -32)],
    "point":    [(-42, -118), (-52, -32), (82, -178), (168, -214)],
    "shrug":    [(-82, -150), (-112, -218), (82, -150), (112, -218)],
    "swipe":    [(22, -108), (74, -150), (64, -152), (122, -186)],
    "sign":     [(-42, -118), (-52, -32), (76, -196), (122, -292)],
    "wave":     [(-42, -118), (-52, -32), (78, -258), (88, -342)],
    "facepalm": [(-42, -118), (-52, -32), (58, -170), (22, -262)],
}
NECK = (0, -205); HEAD_R = 58


def lerp(a, b, q): return (a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q)


def pose_points(prev, cur, q, t):
    pts = [lerp(a, b, q) for a, b in zip(POSES[prev], POSES[cur])]
    if cur == "swipe" and q >= 1: pts[3] = (122 + 46 * math.sin(t * 13), -186 + 10 * math.cos(t * 13))
    if cur == "wave" and q >= 1: pts[3] = (88 + 26 * math.sin(t * 9), -342)
    return pts


def line(cv, a, b, col=WHITE, w=12):
    p = paint(col, 1, stroke=w); p.setStrokeCap(skia.Paint.kRound_Cap); cv.drawLine(a[0], a[1], b[0], b[1], p)


def draw_stick(cv, t, prev, cur, q, mouth, sign=None):
    bob = 5 * math.sin(t * 2.1); hx, hy = HIP[0], HIP[1] + bob
    P = lambda p: (hx + p[0], hy + p[1])
    neck = P(NECK); arms = pose_points(prev, cur, q, t)
    for kn, ft in ((LEGS[0], LEGS[1]), (LEGS[2], LEGS[3])):
        line(cv, (hx, hy), P(kn)); line(cv, P(kn), P(ft))
    line(cv, (hx, hy), neck)
    if cur == "swipe" and q > 0.5:            # phone in the left hand
        x, y = P(arms[1]); cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x - 6, y - 70, x + 34, y + 4), 8, 8), paint("accent2", ease((q - 0.5) * 2)))
    for el, ha in ((arms[0], arms[1]), (arms[2], arms[3])):
        line(cv, neck, P(el)); line(cv, P(el), P(ha))
    if cur == "sign" and sign:
        x, y = P(arms[3]); f = font(900, 50); w = tw(sign, f) + 56; a = ease((q - 0.4) / 0.6) if q < 1 else 1
        r = skia.Rect(x - 10, y - 130, x - 10 + w, y - 10)
        line(cv, (x, y), (x, y - 12), "#8A6A48", 10)
        cv.drawRRect(skia.RRect.MakeRectXY(r, 14, 14), paint("#FFF6E8", a))
        text(cv, sign, r.left() + 28, r.bottom() - 42, f, "#111114", a)
    cx, cy = neck[0] + 4, neck[1] - HEAD_R - 4
    cv.drawCircle(cx, cy, HEAD_R, paint(C["bg"])); cv.drawCircle(cx, cy, HEAD_R, paint(WHITE, 1, stroke=10))
    blink = (t % 3.4) < 0.12
    for ex in (cx + 4, cx + 34):              # glasses (orange) + eyes, looking right
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(ex - 15, cy - 22, ex + 15, cy + 2), 7, 7), paint("accent", 1, stroke=5))
        if blink: cv.drawRect(skia.Rect(ex - 7, cy - 11, ex + 7, cy - 8), paint(WHITE))
        else: cv.drawCircle(ex + 3, cy - 10, 5, paint(WHITE))
    cv.drawLine(cx + 19, cy - 10, cx + 19, cy - 10, paint("accent", 1, stroke=5))
    mh = 4 + 20 * mouth
    cv.drawOval(skia.Rect(cx + 6, cy + 22 - mh / 2, cx + 34, cy + 22 + mh / 2), paint(WHITE))


def draw_bit(cv, t, age, say):
    """Bit: small orange robot in the prop area (right side), with a speech bubble above it. Use it on scenes without a prop."""
    q = ease(age / 0.3); x, y = 790, 1010 + 10 * math.sin(t * 2.6) + 60 * (1 - q)
    cv.save(); cv.translate(x, y); cv.scale(0.7 + 0.3 * q, 0.7 + 0.3 * q)
    line(cv, (0, -58), (0, -86), "accent", 6); cv.drawCircle(0, -92, 9, paint("accent2" if int(t * 3) % 2 else "accent"))
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(-52, -58, 52, 40), 24, 24), paint("accent"))
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(-38, -40, 38, 14), 14, 14), paint("#111114"))
    for ex in (-15, 15): cv.drawCircle(ex, -14, 7, paint("accent2"))
    cv.restore()
    if say:
        bq = ease((age - 0.15) / 0.25); f = font(900, 44); w = tw(say, f) + 52; bx, by = x - w / 2, y - 250
        r = skia.Rect(bx, by, bx + w, by + 84)
        cv.drawRRect(skia.RRect.MakeRectXY(r, 30, 30), paint(WHITE, bq))
        tri = skia.Path(); tri.moveTo(x - 14, by + 82); tri.lineTo(x + 14, by + 82); tri.lineTo(x, by + 112); tri.close()
        cv.drawPath(tri, paint(WHITE, bq))
        text(cv, say, bx + w / 2, by + 58, f, "#111114", bq, anchor="c")


# ---------------- props (right side) ----------------
def icon(cv, kind, x, y, s, a, col="accent"):
    p = paint(col, a); st = paint(col, a, stroke=7); st.setStrokeCap(skia.Paint.kRound_Cap)
    if kind == "sun":
        cv.drawCircle(x, y, s * 0.32, p)
        for i in range(8):
            g = i * math.pi / 4; cv.drawLine(x + s * 0.45 * math.cos(g), y + s * 0.45 * math.sin(g), x + s * 0.6 * math.cos(g), y + s * 0.6 * math.sin(g), st)
    elif kind == "pin":
        path = skia.Path(); path.moveTo(x, y + s * 0.55); path.cubicTo(x - s * 0.7, y - s * 0.1, x - s * 0.35, y - s * 0.62, x, y - s * 0.62)
        path.cubicTo(x + s * 0.35, y - s * 0.62, x + s * 0.7, y - s * 0.1, x, y + s * 0.55); cv.drawPath(path, p)
        cv.drawCircle(x, y - s * 0.2, s * 0.17, paint(C["bg"], a))
    elif kind == "note":
        cv.drawCircle(x - s * 0.22, y + s * 0.32, s * 0.2, p); cv.drawLine(x - s * 0.04, y + s * 0.32, x - s * 0.04, y - s * 0.5, st)
        cv.drawLine(x - s * 0.04, y - s * 0.5, x + s * 0.36, y - s * 0.32, st)
    elif kind == "bolt":
        path = skia.Path(); pts = [(0.1, -0.6), (-0.35, 0.08), (-0.02, 0.08), (-0.12, 0.6), (0.35, -0.1), (0.02, -0.1)]
        path.moveTo(x + pts[0][0] * s, y + pts[0][1] * s)
        for px, py in pts[1:]: path.lineTo(x + px * s, y + py * s)
        path.close(); cv.drawPath(path, p)
    elif kind == "wifi":
        for i, r in enumerate((0.55, 0.36)):
            arc = skia.Path(); arc.addArc(skia.Rect(x - r * s, y - r * s, x + r * s, y + r * s), 225, 90); cv.drawPath(arc, st)
        cv.drawCircle(x, y, s * 0.08, p)


def draw_prop(cv, pr, t, age):
    k = pr["kind"]; q = ease(age / 0.3); cx = 790
    if k == "phone":
        x0, y0, x1, y1 = 650, 740, 930, 1250
        cv.save(); cv.clipRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x1, y1 + 30), 46, 46), doAntiAlias=True)
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0 + 30 * (1 - q), x1, y1 + 30 * (1 - q)), 46, 46), paint("card", q))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0 + 30 * (1 - q), x1, y1 + 30 * (1 - q)), 46, 46), paint(WHITE, q * 0.8, stroke=6))
        cols = ["accent2", "accent", "#3FB37F"]
        for i in range(3):
            yy = 820 + i * 130
            if pr.get("state") == "swipe" and i == 0:
                ph = ((t * 1.6) % 1.0); yy -= 220 * ease(ph); al = q * (1 - ph)
            else: al = q
            r = skia.Rect(690, yy, 890, yy + 110)
            cv.drawRRect(skia.RRect.MakeRectXY(r, 22, 22), paint(cols[i], al * (0.45 if pr.get("state") == "standby" else 1)))
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(712, yy + 22, 760, yy + 70), 12, 12), paint(WHITE, al * 0.85))
        cv.restore()
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0 + 30 * (1 - q), x1, y1 + 30 * (1 - q)), 46, 46), paint(WHITE, q * 0.8, stroke=6))
        if pr.get("state") == "standby":
            for i, (zx, zy, zs) in enumerate(((830, 1210, 40), (866, 1170, 52), (904, 1124, 66))):
                za = q * (0.5 + 0.5 * math.sin(t * 3 - i))
                text(cv, "z", zx, zy - 8 * math.sin(t * 2 + i), font(900, zs), "accent", za, anchor="c")
            R.text(cv, "STANDBY", cx, 1300, mono(30), "accent", ease((age - 0.3) / 0.3), track=6, anchor="c")
    elif k == "battery":
        x0, y0 = 660, 790; bw, bh = 260, 400; lvl = 0.78 - 0.2 * ease((age - 0.6) / 0.5)
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0 + 85, y0 - 34, x0 + 175, y0 + 6), 12, 12), paint(WHITE, q))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x0 + bw, y0 + bh), 34, 34), paint(WHITE, q, stroke=10))
        top = y0 + 16 + (bh - 32) * (1 - lvl)
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0 + 18, top, x0 + bw - 18, y0 + bh - 16), 20, 20), paint("#3FB37F" if lvl > 0.65 else "accent", q))
        if age > 0.5:
            fl = 0.5 + 0.5 * math.sin(t * 18); icon(cv, "bolt", x0 + bw / 2, y0 + bh / 2, 150, min(1, (age - 0.5) * 3) * (0.6 + 0.4 * fl), WHITE)
        if pr.get("label"): text(cv, pr["label"].upper(), x0 + bw / 2, y0 + bh + 74, mono(30), "accent", ease((age - 0.5) / 0.3), track=6, anchor="c")
    elif k == "drains":
        items = pr["items"]
        for i, (ic, lab) in enumerate(items):
            a = ease((age - i * 0.45) / 0.25)
            if a <= 0: continue
            y = 810 + i * 170; r = skia.Rect(570, y - 70, 1010, y + 70)
            cv.drawRRect(skia.RRect.MakeRectXY(r, 30, 30), paint("card", a)); cv.drawRRect(skia.RRect.MakeRectXY(r, 30, 30), paint("card_edge", a, stroke=2))
            icon(cv, ic, 640, y, 80, a)
            text(cv, lab, 700, y + 16, font(800, 44), "text", a)
    elif k == "settings":
        x0, y0, x1, y1 = 600, 740, 1000, 1250
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x1, y1), 40, 40), paint("card", q))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x1, y1), 40, 40), paint(WHITE, q * 0.8, stroke=6))
        text(cv, pr.get("path", "Settings > Battery"), x0 + 40, y0 + 80, font(800, 38), "text", q)
        for i, lab in enumerate(pr.get("rows", [])):
            a = ease((age - 0.3 - i * 0.3) / 0.25); y = y0 + 160 + i * 110; fill = [0.9, 0.62, 0.38, 0.2][i % 4]
            text(cv, lab, x0 + 40, y, font(600, 34), "soft", a)
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0 + 40, y + 22, x1 - 40, y + 40), 9, 9), paint("card_edge", a))
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0 + 40, y + 22, x0 + 40 + (x1 - x0 - 80) * fill * a, y + 40), 9, 9), paint("accent" if i == 0 else "accent2", a))
    elif k == "big":
        s = fit([pr["text"]], 900, pr.get("size", 190), 440)
        sc = 1 + 0.3 * (1 - ease(age / 0.2))
        cv.save(); cv.translate(cx, 1000); cv.scale(sc, sc); cv.translate(-cx, -1000)
        rich_line(cv, pr["text"], cx, 1000 + s * 0.36, font(900, s), set((pr.get("hl") or pr["text"]).split()), min(1, age * 5))
        cv.restore()


def draw_head(cv, b, age):
    lines = b["head"].split("\n"); size = fit(lines, 900, b.get("size", 84), 936, -0.03); f = font(900, size)
    q = ease(age / 0.25); y = 470 + size * 0.36
    for ln in lines:
        rich_line(cv, ln, R.CX, y + 20 * (1 - q), f, set((b.get("hl") or "").split()), q, track=-0.03 * size); y += size * 1.04
    if b.get("sub"): text(cv, b["sub"], R.CX, y + 4, font(600, 38), "soft", ease((age - 0.3) / 0.25), anchor="c")


# ---------------- render ----------------
def plan(spec, times, total):
    beats, ev, dur, at = R.plan(spec, times, total)
    for b, t0, t1 in beats:
        if b.get("bit"): ev.append(("pop", t0 + 0.15))
        if b.get("pose") == "sign": ev.append(("pop", t0 + 0.3))
    return beats, ev, dur, at


def render(spec, times, total, wav, out_mp4, stills=None, words=None):
    beats, events, dur, at = plan(spec, times, total)
    chunks = v1.caption_chunks(spec, times, words); env = Env(wav)
    surf = skia.Surface(W, H); cv = surf.getCanvas()

    def frame(t):
        R.draw_bg(cv)
        idx = max([i for i, x in enumerate(beats) if x[1] <= t + 1e-6] or [0]); b, t0, t1 = beats[idx]
        age = (t - t0) if t0 > 0 else 9.0
        prev = beats[idx - 1][0].get("pose", "idle") if idx else b.get("pose", "idle")
        q = ease(age / 0.3)
        fade = min(1, age / 0.08) if t0 > 0 else 1
        if fade < 1: cv.saveLayerAlpha(None, int(255 * fade))
        draw_head(cv, b, age)
        if b.get("prop"): draw_prop(cv, b["prop"], t, age)
        if fade < 1: cv.restore()
        draw_stick(cv, t, prev, b.get("pose", "idle"), q, env.at(t), b.get("sign"))
        if b.get("bit") is not None: draw_bit(cv, t, age, b.get("bit"))
        R.draw_header(cv, t, dur, 0, 0); R.draw_caption(cv, t, chunks)
        return surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)

    if stills:
        from PIL import Image
        for t in stills: Image.fromarray(frame(t)[..., :3]).save(f"{out_mp4}.still_{t:05.1f}.png")
        return
    mixwav = out_mp4 + ".mix.wav"; R.mix(wav, mixwav, [x[1] for x in beats], events, dur)
    tmp = out_mp4 + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", mixwav, "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                          "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                          "-t", str(dur), "-movflags", "+faststart", tmp], stdin=subprocess.PIPE)
    for i in range(int(dur * FPS)): p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait(); os.remove(mixwav)
    if p.returncode: raise RuntimeError("ffmpeg failed")
    os.replace(tmp, out_mp4)


def cover(spec, out_png, dwg=None):
    """cover: {"head": "...", "hl": "...", "pose": "...", "prop": {...}, "bit": "..."} (one scene, fully drawn)"""
    c = spec["cover"]; s = skia.Surface(W, H); cv = s.getCanvas(); R.draw_bg(cv)
    draw_head(cv, c, 9.0)
    if c.get("prop"): draw_prop(cv, c["prop"], 1.0, 9.0)
    draw_stick(cv, 1.0, c.get("pose", "idle"), c.get("pose", "idle"), 1.0, 0.4, c.get("sign"))
    if c.get("bit") is not None: draw_bit(cv, 1.0, 9.0, c.get("bit"))
    text(cv, "THE UNHYPED", R.CX, 1400, mono(32), "soft", track=8, anchor="c")
    from PIL import Image
    Image.fromarray(s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]).save(out_png)
