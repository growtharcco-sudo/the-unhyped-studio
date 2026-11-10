"""The Unhyped engine v2: dark, high-contrast, built for retention.

Same spec format and timing rules as render.py ("at" in phrases, -1 = frame 1), plus:
  "steps": 5                      -> the header shows 5 segments that unlock as the countdown runs
  hook   {lines:[..], hl, kicker, teaser}         big scroll-stopping opener, always "at": -1
  slots  {n, open_at:[..], y}     a row of locked boxes that open one by one; the last one glows
  item   {n, of, title, line, at} giant step number + title (one per countdown step)
  reveal {n, title, line, at}     the final step: burst + "THE BIG ONE" stamp
  punch  {text, hl, size, y, at}  a big line that punches in (story beats, twists)
  card / bar / badge / strike / block / kicker   as in v1, recoloured for dark
Visual safe area: y 380 to 1060. Captions at about y 1190. Bottom ~600 px stays clear for app buttons.
"""
import math, os, subprocess
import numpy as np
import skia
import render as v1                     # fonts, timing helpers, captions timing, 3D blocks

W, H, FPS = v1.W, v1.H, v1.FPS
font, ease, spring, text_w = v1.font, v1.ease, v1.spring, v1.text_w


def wrap(s, f, maxw, track=0):
    """Like v1.wrap, but never leaves one word alone on the last line."""
    lines = v1.wrap(s, f, maxw, track)
    if len(lines) > 1 and len(lines[-1].split()) == 1 and len(lines[-2].split()) > 2:
        a = lines[-2].split(); lines[-2] = " ".join(a[:-1]); lines[-1] = a[-1] + " " + lines[-1]
    return lines
CX = 540

C = {"bg0": "#070B18", "bg1": "#0D1430", "text": "#F4F6FF", "soft": "#AEB8D8", "dim": "#5F6B92",
     "orange": "#FF7A1A", "orange_dark": "#B84D08", "orange_pale": "#6B3A1A", "blue": "#4C8DFF", "blue_dark": "#2A55B8",
     "card": "#121A38", "card_edge": "#26315E", "line": "#1E2850", "white": "#FFFFFF", "green": "#2BD38A"}


def rgb(h, a=255):
    h = h.lstrip("#"); return skia.Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def paint(col, a=1.0, stroke=0):
    pt = skia.Paint(AntiAlias=True, Color=rgb(C.get(col, col), int(255 * max(0, min(1, a)))))
    if stroke: pt.setStyle(skia.Paint.kStroke_Style); pt.setStrokeWidth(stroke)
    return pt


def draw_text(cv, s, x, y, f, col, a=1.0, track=0, anchor="l"):
    w = text_w(s, f, track)
    if anchor == "c": x -= w / 2
    elif anchor == "r": x -= w
    p = paint(col, a)
    if not track: cv.drawString(s, x, y, f, p); return w
    for ch in s: cv.drawString(ch, x, y, f, p); x += f.measureText(ch) + track
    return w


def punch(cv, p, cx, cy):
    """Scale-in from 1.25 to 1.0 around (cx, cy): the 'punch' on every reveal."""
    s = 1 + 0.25 * (1 - ease(p))
    cv.translate(cx, cy); cv.scale(s, s); cv.translate(-cx, -cy)


def make_paper():
    s = skia.Surface(W, H); cv = s.getCanvas()
    cv.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=skia.GradientShader.MakeLinear(
        [(0, 0), (0, H)], [rgb(C["bg0"]), rgb(C["bg1"]), rgb(C["bg0"])], [0, 0.5, 1])))
    glow = skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeRadial(
        (540, 720), 620, [skia.Color(76, 141, 255, 38), skia.Color(76, 141, 255, 0)]))
    cv.drawCircle(540, 720, 620, glow)
    p = skia.Paint(AntiAlias=True, Color=skia.Color(76, 141, 255, 16), StrokeWidth=1.2, Style=skia.Paint.kStroke_Style)
    for x in range(0, W, 60): cv.drawLine(x, 0, x, H, p)
    for y in range(0, H, 60): cv.drawLine(0, y, W, y, p)
    return s.makeImageSnapshot()


def draw_header(cv, spec, t, total, opened):
    """Brand + a progress bar. With "steps": N it is N segments that unlock as the countdown runs."""
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(90, 262, 106, 278), 3, 3), paint("orange"))
    draw_text(cv, "THE UNHYPED", 120, 279, font("mono6", 24), "soft", track=4)
    lab = spec.get("series", "").upper(); f = font("mono", 22)
    if lab: draw_text(cv, lab, 990, 279, f, "dim", track=3, anchor="r")
    n = spec.get("steps")
    if n:
        gap, x0, x1 = 12, 90, 990; w = (x1 - x0 - gap * (n - 1)) / n
        for i in range(n):
            x = x0 + i * (w + gap); on = i < opened
            last = i == n - 1
            col = "orange" if on else ("#3A2A22" if last else C["line"])
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, 302, x + w, 312), 5, 5), paint(col))
    else:
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(90, 302, 990, 310), 4, 4), paint("line"))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(90, 302, 90 + 900 * min(1, t / total), 310), 4, 4), paint("orange"))


def lock_icon(cv, cx, cy, s, col, a=1.0):
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(cx - s * 0.5, cy - s * 0.1, cx + s * 0.5, cy + s * 0.55), s * 0.12, s * 0.12), paint(col, a))
    arc = skia.Path(); arc.addArc(skia.Rect(cx - s * 0.3, cy - s * 0.55, cx + s * 0.3, cy + s * 0.05), 180, 180)
    cv.drawPath(arc, paint(col, a, stroke=s * 0.11))
    cv.drawLine(cx - s * 0.3, cy - s * 0.25, cx - s * 0.3, cy - s * 0.08, paint(col, a, stroke=s * 0.11))
    cv.drawLine(cx + s * 0.3, cy - s * 0.25, cx + s * 0.3, cy - s * 0.08, paint(col, a, stroke=s * 0.11))


class El(v1.El):
    pass


class Hook(El):
    def draw(s, cv, t):
        e = s.e; a = s.out(t)
        if a <= 0: return
        p = 1.0 if s.t0 < -0.5 else ease(s.p(t, 0.35))
        cv.save(); punch(cv, p, CX, 640)
        if e.get("kicker"):
            draw_text(cv, e["kicker"].upper(), CX, 430, font("mono6", 30), "orange", a, track=6, anchor="c")
        size = e.get("size", 118); f = font("sans", size); y = 430 + size * 1.15
        for ln in e["lines"]:
            hl = e.get("hl")
            if hl and hl in ln:
                pre, post = ln.split(hl, 1); w = text_w(ln, f); x = CX - w / 2
                x += draw_text(cv, pre, x, y, f, "text", a); x += draw_text(cv, hl, x, y, f, "orange", a)
                draw_text(cv, post, x, y, f, "text", a)
            else:
                draw_text(cv, ln, CX, y, f, "text", a, anchor="c")
            y += size * 1.08
        cv.restore()
        if e.get("teaser"):
            tp = 1.0 if s.t0 < -0.5 else ease(s.p(t - 0.2, 0.4))
            ft = font("mono6", 28); tw = text_w(e["teaser"].upper(), ft, 2) + 90; ty = y + 10
            x0 = CX - tw / 2
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, ty, x0 + tw, ty + 64), 32, 32), paint("#2A1606", a * tp))
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, ty, x0 + tw, ty + 64), 32, 32), paint("orange", a * tp, stroke=2.5))
            lock_icon(cv, x0 + 38, ty + 32, 26, "orange", a * tp)
            draw_text(cv, e["teaser"].upper(), x0 + 64, ty + 42, ft, "orange", a * tp, track=2)


class Slots(El):
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1); s.opens = [at(v, 0.0) for v in e.get("open_at", [])]
    def draw(s, cv, t):
        e = s.e; a = s.out(t) * (1.0 if s.t0 < -0.5 else ease(s.p(t)))
        if a <= 0: return
        n = e["n"]; sz = e.get("size", 120); gap = 22; total = n * sz + (n - 1) * gap; x0 = CX - total / 2; y = e["y"]
        for i in range(n):
            x = x0 + i * (sz + gap); ot = s.opens[i] if i < len(s.opens) else 1e9
            op = 0 if t < ot else ease(min(1, (t - ot) / 0.3)); last = i == n - 1
            r = skia.Rect(x, y, x + sz, y + sz)
            if last and op == 0:
                pulse = 0.5 + 0.5 * math.sin(t * 5)
                glow = skia.Paint(AntiAlias=True, Color=rgb(C["orange"], int(90 * pulse * a)),
                                  MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 18))
                cv.drawRRect(skia.RRect.MakeRectXY(r, 18, 18), glow)
            cv.drawRRect(skia.RRect.MakeRectXY(r, 18, 18), paint("card", a))
            cv.drawRRect(skia.RRect.MakeRectXY(r, 18, 18), paint("orange" if (last or op) else "card_edge", a, stroke=3))
            if op > 0:
                cv.drawRRect(skia.RRect.MakeRectXY(r, 18, 18), paint("orange", a * op))
                draw_text(cv, str(i + 1), x + sz / 2, y + sz * 0.68, font("sans", sz * 0.55), "white", a * op, anchor="c")
            else:
                lock_icon(cv, x + sz / 2, y + sz * 0.52, sz * 0.34, "orange" if last else "dim", a)


class Item(El):
    def draw(s, cv, t):
        e = s.e; a = s.out(t)
        if t < s.t0 or a <= 0: return
        p = ease(s.p(t, 0.35))
        cv.save(); punch(cv, p, 300, 640)
        f = font("sans", e.get("num_size", 330))
        draw_text(cv, str(e["n"]), 90, 800, f, "orange", a * p)
        draw_text(cv, f"/{e.get('of', '')}" if e.get("of") else "", 90 + text_w(str(e["n"]), f) + 12, 800, font("sans", 90), "dim", a * p)
        cv.restore()
        tp = ease(s.p(t - 0.15, 0.4)); ft = font("sans", e.get("size", 76)); y = 905 + 30 * (1 - tp)
        for ln in wrap(e["title"], ft, 900):
            draw_text(cv, ln, 90, y, ft, "text", a * tp); y += e.get("size", 76) * 1.1
        if e.get("line"):
            lp = ease(s.p(t - 0.45, 0.4))
            for ln in wrap(e["line"], font("sans5", 40), 900):
                draw_text(cv, ln, 90, y + 10, font("sans5", 40), "soft", a * lp); y += 50


class Reveal(El):
    def draw(s, cv, t):
        e = s.e; a = s.out(t)
        if t < s.t0 or a <= 0: return
        p = ease(s.p(t, 0.45)); burst = min(1, (t - s.t0) / 0.6)
        cv.save(); cv.translate(540, 640)
        for i in range(16):
            ang = i * math.pi / 8 + t * 0.4
            r0, r1 = 160 + 60 * burst, 300 + 200 * burst
            cv.drawLine(r0 * math.cos(ang), r0 * math.sin(ang), r1 * math.cos(ang), r1 * math.sin(ang),
                        paint("orange", a * (1 - burst * 0.6) * 0.5, stroke=6))
        cv.restore()
        cv.save(); punch(cv, p, 540, 640)
        draw_text(cv, f"#{e['n']}", 540, 735, font("sans", 300), "orange", a * p, anchor="c")
        cv.restore()
        sp = spring(s.p(t - 0.25, 0.5))
        if sp > 0:
            fs = font("mono6", 34); txt = e.get("stamp", "THE BIG ONE"); sw = text_w(txt, fs, 6) + 50
            cv.save(); cv.translate(800, 470); cv.rotate(-8); sc = 1.6 - 0.6 * sp; cv.scale(sc, sc)
            cv.drawRect(skia.Rect(-sw / 2, -32, sw / 2, 32), paint("orange", a, stroke=5))
            draw_text(cv, txt, 0, 12, fs, "orange", a, track=6, anchor="c"); cv.restore()
        tp = ease(s.p(t - 0.3, 0.4)); ft = font("sans", e.get("size", 74)); y = 870 + 30 * (1 - tp)
        for ln in wrap(e["title"], ft, 920):
            draw_text(cv, ln, 540, y, ft, "text", a * tp, anchor="c"); y += e.get("size", 74) * 1.1
        if e.get("line"):
            lp = ease(s.p(t - 0.6, 0.4))
            for ln in wrap(e["line"], font("sans5", 40), 920):
                draw_text(cv, ln, 540, y + 10, font("sans5", 40), "soft", a * lp, anchor="c"); y += 50


class Punch(El):
    def draw(s, cv, t):
        e = s.e; a = s.out(t)
        if a <= 0 or (t < s.t0 and s.t0 > -0.5): return
        p = 1.0 if s.t0 < -0.5 else ease(s.p(t, 0.3)); size = e.get("size", 96); f = font("sans", size)
        lines = e["text"].split("\n"); y = e["y"]
        cv.save(); punch(cv, p, CX, y)
        for ln in lines:
            hl = e.get("hl")
            if hl and hl in ln:
                pre, post = ln.split(hl, 1); w = text_w(ln, f); x = CX - w / 2
                x += draw_text(cv, pre, x, y, f, e.get("color", "text"), a * p); x += draw_text(cv, hl, x, y, f, "orange", a * p)
                draw_text(cv, post, x, y, f, e.get("color", "text"), a * p)
            else:
                draw_text(cv, ln, CX, y, f, e.get("color", "text"), a * p, anchor="c")
            y += size * 1.1
        cv.restore()


class Kicker(El):
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0 and s.t0 > -0.5: return
        a = a if s.t0 > -0.5 else s.out(t)
        draw_text(cv, s.e["text"].upper(), CX, s.e["y"] + dy, font("mono6", s.e.get("size", 30)), s.e.get("color", "orange"),
                  a, track=6, anchor="c")


class Card(El):
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1); s.row_t = [at(r, 0.0) for r in e.get("row_at", [])]
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        e = s.e; x, w = e.get("x", 90), e.get("w", 900); y = e["y"] + dy; rows = e["rows"]; h = 24 + 78 * len(rows)
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y, x + w, y + h), 20, 20), paint("card", a))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y, x + w, y + h), 20, 20), paint("card_edge", a, stroke=2))
        cy = y + 12
        for i, r in enumerate(rows):
            rt = s.row_t[i] if i < len(s.row_t) else s.t0
            rp = ease(0 if t < rt else min(1, (t - rt) / 0.3))
            draw_text(cv, r[0].upper(), x + 30, cy + 48, font("mono", 22), "dim", a, track=2)
            draw_text(cv, r[1], x + 300 + 14 * (1 - rp), cy + 50, font("sans6", 36),
                      "orange" if len(r) > 2 and r[2] == "hl" else "text", a * rp)
            if i < len(rows) - 1: cv.drawRect(skia.Rect(x + 30, cy + 77, x + w - 30, cy + 78.5), paint("line", a))
            cy += 78


class Bar(El):
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        e = s.e; x, w, y = 90, 900, e["y"] + dy; col = e.get("color", "orange")
        draw_text(cv, e["label"].upper(), x, y, font("mono6", 24), "soft", a, track=2)
        draw_text(cv, e.get("value", ""), x + w, y, font("sans", 40), col, a, anchor="r")
        fill = e.get("fill", 1.0) * ease(s.p(t - 0.1, e.get("dur", 0.9))); by = y + 18
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, by, x + w, by + 40), 20, 20), paint("card", a))
        if fill > 0: cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, by, x + w * fill, by + 40), 20, 20), paint(col, a))


class Badge(El):
    def draw(s, cv, t):
        p = spring(s.p(t, 0.45)) if s.t0 > -0.5 else 1.0; a = s.out(t) * (min(1, s.p(t, 0.15) * 3) if s.t0 > -0.5 else 1)
        if a <= 0: return
        e = s.e; f = font("mono6", e.get("size", 30)); col = e.get("color", "orange")
        tw = text_w(e["text"], f, 4); bw, bh = tw + 48, e.get("size", 30) + 30; x0 = CX - bw / 2; y0 = e["y"]
        cv.save(); sc = 0.85 + 0.15 * p; cv.translate(CX, y0 + bh / 2); cv.scale(sc, sc); cv.translate(-CX, -(y0 + bh / 2))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x0 + bw, y0 + bh), bh / 2, bh / 2), paint(col, a))
        draw_text(cv, e["text"], CX, y0 + bh / 2 + e.get("size", 30) * 0.36, f, "white", a, track=4, anchor="c"); cv.restore()


class Strike(El):
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1); s.ts = at(e.get("strike_at", -1), 0.0)
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0 and s.t0 > -0.5: return
        a = a if s.t0 > -0.5 else s.out(t)
        e = s.e; f = font("sans", e.get("size", 64)); sp = ease(0 if t < s.ts else min(1, (t - s.ts) / 0.35)); y = e["y"] + dy
        w = draw_text(cv, e["text"], CX, y, f, "dim" if sp > 0 else "text", a, anchor="c")
        if sp > 0: cv.drawRect(skia.Rect(CX - w / 2, y - e.get("size", 64) * 0.32, CX - w / 2 + w * sp, y - e.get("size", 64) * 0.32 + 8), paint("orange", a))


class Block(El):
    def draw(s, cv, t):
        e = s.e; p = spring(s.p(t, 0.5)) if s.t0 > -0.5 else 1.0; a = s.out(t) * (min(1, s.p(t, 0.12) * 3) if s.t0 > -0.5 else 1)
        if a <= 0: return
        v1.draw_block(cv, e["x"], e["y"] - 30 * (1 - p), e.get("a", 120), e.get("h", 100), e.get("theme", "orange"), a,
                      e.get("label"), e.get("label_size"), e.get("wire", False), e.get("b"))


TYPES = {"hook": Hook, "slots": Slots, "item": Item, "reveal": Reveal, "punch": Punch, "kicker": Kicker, "card": Card,
         "bar": Bar, "badge": Badge, "strike": Strike, "block": Block}
NEEDS_AT = (Slots, Card, Strike)


def build(spec, times, total):
    def at(v, delay=0.0):
        if v == -1 or v is None: return -1.0
        if isinstance(v, list): s, e = times[v[0]]; return s + (e - s) * v[1] + delay
        return times[v][0] + delay
    scenes = []
    for sc in spec["scenes"]:
        u = sc.get("until", "end"); t1 = total + 5 if u == "end" else times[u][0] - 0.05
        els = []
        for e in sc["els"]:
            cls = TYPES[e["type"]]; t0 = at(e.get("at"), e.get("delay", 0.0))
            els.append(cls(e, t0, t1, at) if cls in NEEDS_AT else cls(e, t0, t1))
        scenes.append({"start": min([el.t0 for el in els] + [t1]), "end": t1, "els": els})
    step_times = sorted(at(v) for v in spec.get("step_at", []))
    return scenes, step_times


CAP_SIZE, CAP_Y = 64, 1190


def draw_caption(cv, t, chunks):
    f = font("sans", CAP_SIZE); sp = 18; pad = 14
    for st, en, words in chunks:
        if not (st <= t < en): continue
        active = None
        for i, (w, ws, we) in enumerate(words):
            if ws - 0.03 <= t: active = i
        if t > words[-1][2] + 0.05: active = None
        widths = [text_w(w[0], f) for w in words]
        total = sum(widths) + sp * (len(words) - 1) + (2 * (pad + 6) if active is not None else 0)
        x = CX - total / 2; y = CAP_Y
        sh = skia.Paint(AntiAlias=True, Color=skia.Color(0, 0, 0, 150), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 8))
        for i, (w, wd) in enumerate(zip(words, widths)):
            if i == active:
                x += 6; pop = 1 + 0.08 * (1 - ease(min(1, (t - w[1]) / 0.12)))
                cv.save(); cx = x + wd / 2 + pad; cv.translate(cx, y - 18); cv.scale(pop, pop); cv.translate(-cx, -(y - 18))
                cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y - 56, x + wd + 2 * pad, y + 18), 14, 14), paint("orange"))
                draw_text(cv, w[0], x + pad, y, f, "white"); cv.restore(); x += wd + 2 * pad + 6 + sp
            else:
                cv.drawString(w[0], x + 2, y + 3, f, sh); draw_text(cv, w[0], x, y, f, "text"); x += wd + sp


def render(spec, times, total, wav, out_mp4, stills=None, words=None):
    paper = make_paper()
    scenes, step_times = build(spec, times, total)
    chunks = v1.caption_chunks(spec, times, words)
    dur = round(total + 0.3, 2)
    surf = skia.Surface(W, H); cv = surf.getCanvas()

    def frame(t):
        cv.drawImage(paper, 0, 0)
        for i, sc in enumerate(scenes):
            fo = 1.0 if i == len(scenes) - 1 else max(0., min(1., (sc["end"] - t) / 0.12))
            if fo <= 0 or (i and t < sc["start"] - 0.01): continue
            if fo < 1: cv.saveLayerAlpha(None, int(255 * fo))
            for el in sc["els"]:
                if (el.t0 <= t + 0.01 or el.t0 < -0.5) and t < el.t1: el.draw(cv, t)
            if fo < 1: cv.restore()
        draw_header(cv, spec, t, dur, sum(1 for x in step_times if x <= t))
        draw_caption(cv, t, chunks)
        return surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)

    if stills:
        from PIL import Image
        for t in stills: Image.fromarray(frame(t)[..., :3]).save(f"{out_mp4}.still_{t:05.1f}.png")
        return
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                          "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                          "-af", "apad", "-t", str(dur), "-movflags", "+faststart", out_mp4], stdin=subprocess.PIPE)
    for i in range(int(dur * FPS)): p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait()
    if p.returncode: raise RuntimeError("ffmpeg failed")


def cover(spec, out_png, dwg=None):
    """Dark cover: big question, orange box, locked slots row."""
    c = spec["cover"]; s = skia.Surface(W, H); cv = s.getCanvas(); cv.drawImage(make_paper(), 0, 0)
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(90, 330, 108, 348), 3, 3), paint("orange"))
    draw_text(cv, "THE UNHYPED", 126, 348, font("mono6", 30), "soft", track=5)
    size = c.get("size", 124); fh = font("sans", size); y = 430
    for ln in c["lines"]:
        while text_w(ln, fh, -4) > 900 and size > 70: size -= 4; fh = font("sans", size)
    for ln in c["lines"]:
        y += size * 1.05; draw_text(cv, ln, 88, y - size * 0.2, fh, "text", track=-4)
    if c.get("box"):
        bw = text_w(c["box"], fh, -4) + 50; top = y + 14
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(90, top, 90 + bw, top + size * 1.2), 22, 22), paint("orange"))
        draw_text(cv, c["box"], 115, top + size * 0.93, fh, "white", track=-4); y = top + size * 1.2
    n = c.get("slots", spec.get("steps", 0))
    if n:
        sl = Slots({"n": n, "y": y + 90, "size": 130}, -1, 1e9, lambda v, d=0: 1e9)
        sl.opens = [1e9] * n; sl.draw(cv, 0)
    if c.get("footer"):
        draw_text(cv, c["footer"].upper(), 90, 1560, font("mono6", 32), "orange", track=6)
    from PIL import Image
    Image.fromarray(s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]).save(out_png)
