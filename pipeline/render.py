"""The Unhyped video engine: light engineering sheet, IBM Plex type, white data cards, 3D blocks.

A reel is described by a spec (see specs/*.json). Times are given in phrases, not seconds:
  "at": 3            -> when phrase 3 starts
  "at": [3, 0.5]     -> halfway through phrase 3
  "at": -1           -> visible from the very first frame (the hook)
  "delay": 0.3       -> extra seconds after that point
A scene ends when phrase "until" starts (or at the end of the video when "until" is "end").
Element types: kicker, head, number, card, badge, bar, strike, block, steps, ref, follow, text.
Everything visual sits between y 420 and 1060; captions sit at about y 1170; the bottom ~600 px stays
clear for the Instagram / YouTube buttons.
"""
import math, os, subprocess
import numpy as np
import skia

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, "fonts")


def rgb(h, a=255):
    h = h.lstrip("#"); return skia.Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


C = {"navy": "#13234A", "blue": "#3466D6", "blue_dark": "#2348A0", "orange": "#EF792B", "orange_pale": "#F4BE98",
     "orange_dark": "#C85A1E", "muted": "#5A6A8A", "faint": "#A9B0C2", "line": "#A3B0CC", "white": "#FFFFFF",
     "card_border": "#D3DAE8", "card_shadow": "#D7DDEA", "row_line": "#E3E8F1", "green": "#1F8A5B"}
CX = 540
_tf = {}


def font(kind, size):
    name = {"sans": "plex-sans-bold", "sans6": "plex-sans-semibold", "sans5": "plex-sans-medium",
            "mono": "plex-mono-medium", "mono6": "plex-mono-semibold"}[kind]
    if name not in _tf: _tf[name] = skia.Typeface.MakeFromFile(os.path.join(FD, name + ".ttf"))
    f = skia.Font(_tf[name], size); f.setSubpixel(True); f.setEdging(skia.Font.Edging.kAntiAlias)
    return f


def ease(p): p = max(0., min(1., p)); return 1 - (1 - p) ** 3


def spring(p):
    """Small overshoot pop, 0..1 (used for badges and blocks)."""
    p = max(0., min(1., p)); return 1 - math.exp(-6 * p) * math.cos(9 * p) if p < 1 else 1.0


def paint(col, a=1.0, stroke=0, aa=True):
    pt = skia.Paint(AntiAlias=aa, Color=rgb(C.get(col, col), int(255 * max(0, min(1, a)))))
    if stroke: pt.setStyle(skia.Paint.kStroke_Style); pt.setStrokeWidth(stroke)
    return pt


def text_w(s, f, track=0): return f.measureText(s) + track * max(0, len(s) - 1)


def draw_text(cv, s, x, y, f, col, a=1.0, track=0, anchor="l"):
    """y is the baseline. track = extra letter spacing in px (mono labels use it)."""
    w = text_w(s, f, track)
    if anchor == "c": x -= w / 2
    elif anchor == "r": x -= w
    p = paint(col, a)
    if not track: cv.drawString(s, x, y, f, p); return w
    for ch in s:
        cv.drawString(ch, x, y, f, p); x += f.measureText(ch) + track
    return w


def wrap(s, f, maxw, track=0):
    lines, cur = [], ""
    for wd in s.split():
        t = (cur + " " + wd).strip()
        if cur and text_w(t, f, track) > maxw: lines.append(cur); cur = wd
        else: cur = t
    if cur: lines.append(cur)
    return lines


# ---------------- background, frame, header ----------------
def make_paper():
    s = skia.Surface(W, H); cv = s.getCanvas()
    g = skia.Paint(Shader=skia.GradientShader.MakeLinear(
        [(0, 0), (0, H)], [rgb("#F5F6FC"), rgb("#EEF1F9"), rgb("#E2E6F0")], [0, 0.55, 1]))
    cv.drawRect(skia.Rect(0, 0, W, H), g)
    for step, a, wdt in ((30, 15, 1.2), (150, 31, 1.6)):
        p = skia.Paint(AntiAlias=True, Color=skia.Color(52, 102, 214, a), StrokeWidth=wdt, Style=skia.Paint.kStroke_Style)
        for x in range(0, W, step): cv.drawLine(x, 0, x, H, p)
        for y in range(0, H, step): cv.drawLine(0, y, W, y, p)
    cv.drawRect(skia.Rect(40, 40, 1040, 1880), paint("line", stroke=2))
    for x, y in ((40, 40), (1040, 40), (40, 1880), (1040, 1880)):
        cv.drawCircle(x, y, 8, paint("#F2F4FB")); cv.drawCircle(x, y, 8, paint("blue", stroke=2))
    return s.makeImageSnapshot()


def draw_header(cv, series, dwg, sheet, sub, progress):
    cv.drawRect(skia.Rect(91, 306, 105, 320), paint("orange"))
    draw_text(cv, series.upper(), 125, 322, font("mono6", 26), "muted", track=4)
    lab = f"DWG {dwg} · SHEET {sheet}"; f = font("mono", 24)
    w = text_w(lab, f, 3); x1 = 900; x0 = x1 - w - 28
    cv.drawRect(skia.Rect(x0, 288, x1, 332), paint("muted", stroke=2))
    draw_text(cv, lab, x0 + 14, 319, f, "muted", track=3)
    cv.drawRect(skia.Rect(90, 344, 900, 346), paint("line"))
    cv.drawRect(skia.Rect(90, 343, 90 + 810 * max(0, min(1, progress)), 347), paint("blue"))
    if sub: draw_text(cv, sub.upper(), 90, 383, font("mono", 22), "muted", track=2)


# ---------------- elements ----------------
class El:
    dur = 0.4
    def __init__(s, e, t0, t1): s.e, s.t0, s.t1 = e, t0, t1
    def p(s, t, d=None): return 0. if t < s.t0 else min(1., (t - s.t0) / max(d or s.dur, 1e-3))
    def out(s, t): return max(0., min(1., (s.t1 - t) / 0.2))
    def rise(s, t):
        p = ease(s.p(t)); return p * s.out(t), 18 * (1 - p)


class Kicker(El):
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        x = s.e.get("x", "c"); f = font("mono", s.e.get("size", 28))
        draw_text(cv, s.e["text"].upper(), CX if x == "c" else x, s.e["y"] + dy, f, s.e.get("color", "faint"), a,
                  track=5, anchor="c" if x == "c" else "l")


class Head(El):
    """Big headline. "hl": a word or phrase drawn in orange; "underline": true draws an orange line under it."""
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        e = s.e; f = font("sans", e.get("size", 78)); lh = e.get("size", 78) * 1.14
        lines = e["text"].split("\n") if "\n" in e["text"] else wrap(e["text"], f, e.get("maxw", 900))
        for i, ln in enumerate(lines):
            y = e["y"] + dy + i * lh; w = text_w(ln, f); x = CX - w / 2 if e.get("x", "c") == "c" else e["x"]
            hl = e.get("hl")
            col = e.get("color", "navy")
            if hl and hl in ln:
                pre, post = ln.split(hl, 1)
                x2 = x + draw_text(cv, pre, x, y, f, col, a)
                hw = draw_text(cv, hl, x2, y, f, e.get("hl_color", "orange"), a)
                if e.get("underline"):
                    u = ease(s.p(t - e.get("underline_delay", 0.35), 0.5))
                    cv.drawRect(skia.Rect(x2, y + 12, x2 + hw * u, y + 18), paint(e.get("hl_color", "orange"), a))
                draw_text(cv, post, x2 + hw, y, f, col, a)
            else:
                draw_text(cv, ln, x, y, f, col, a)


class Number(El):
    """Counts up while pale orange, turns full orange when it lands (like the $6.3B in the Binance reel)."""
    def draw(s, cv, t):
        e = s.e; a = s.out(t) * ease(s.p(t, 0.25))
        if a <= 0: return
        d = e.get("dur", 1.0); p = ease(s.p(t, d)) if s.t0 > -0.5 else 1.0
        v = e["value"] * p; dec = e.get("decimals", 0)
        txt = f"{e.get('prefix', '')}{v:,.{dec}f}{e.get('suffix', '')}"
        if p >= 1 and "final" in e: txt = e["final"]
        col = e.get("color", "orange")
        if p < 1 and col == "orange": col = "orange_pale"
        dy = 18 * (1 - ease(s.p(t, 0.3)))
        draw_text(cv, txt, CX, e["y"] + dy, font("sans", e.get("size", 180)), col, a, anchor="c")


def card_box(cv, x, y, w, h, a):
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y + 6, x + w, y + h + 6), 6, 6), paint("card_shadow", a))
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y, x + w, y + h), 6, 6), paint("white", a))
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y, x + w, y + h), 6, 6), paint("card_border", a, stroke=2))


class Card(El):
    """Data card. rows: [[LABEL, value, (optional) "hl"]], each row can appear at its own time via "row_at"."""
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1)
        s.row_t = [at(r, 0.0) for r in e.get("row_at", [])]
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        e = s.e; x, w = e.get("x", 130), e.get("w", 820); y = e["y"] + dy
        rows = e.get("rows", []); title = e.get("title")
        big = e.get("big")                                  # optional big line: [name, number]
        h = 20 + (90 if big else 0) + (36 if e.get("note") else 0) + 66 * len(rows) + 12
        card_box(cv, x, y, w, h, a)
        cy = y + 20
        if big:
            fN, fB = font("sans", 52), font("sans", 92)
            nw = draw_text(cv, big[0], x + 26, cy + 72, fN, "navy", a)
            draw_text(cv, big[1], x + 26 + nw + 26, cy + 76, fB, "orange", a)
            cy += 90
            if e.get("note"):
                draw_text(cv, e["note"].upper(), x + 26, cy + 26, font("mono", 22), "muted", a * ease(s.p(t - 0.4)), track=2); cy += 36
        for i, r in enumerate(rows):
            rt = s.row_t[i] if i < len(s.row_t) else s.t0
            rp = ease(0 if t < rt else min(1, (t - rt) / 0.3))
            draw_text(cv, r[0].upper(), x + 26, cy + 42, font("mono", 20), "muted", a, track=2)
            draw_text(cv, r[1], x + 256 + 14 * (1 - rp), cy + 44, font("sans6", 32),
                      "orange" if len(r) > 2 and r[2] == "hl" else "navy", a * rp)
            if i < len(rows) - 1: cv.drawRect(skia.Rect(x + 26, cy + 65, x + w - 26, cy + 66.5), paint("row_line", a))
            cy += 66
        if title:
            draw_text(cv, title.upper(), x, y - 22, font("mono", 26), "faint", a, track=5)


class Badge(El):
    def draw(s, cv, t):
        p = spring(s.p(t, 0.45)); a = s.out(t) * min(1, s.p(t, 0.15) * 3)
        if a <= 0: return
        e = s.e; f = font("mono6", e.get("size", 24)); col = e.get("color", "blue")
        tw = text_w(e["text"], f, 3); bw, bh = tw + 32, e.get("size", 24) + 22
        x = e.get("x", "c"); x0 = CX - bw / 2 if x == "c" else x; y0 = e["y"]
        sc = 0.85 + 0.15 * p
        cv.save(); cv.translate(x0 + bw / 2, y0 + bh / 2); cv.scale(sc, sc); cv.translate(-(x0 + bw / 2), -(y0 + bh / 2))
        dark = "orange_dark" if col == "orange" else "blue_dark"
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0 + 4, x0 + bw, y0 + bh + 4), 4, 4), paint(dark, a))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x0, y0, x0 + bw, y0 + bh), 4, 4), paint(col, a))
        draw_text(cv, e["text"], x0 + 16, y0 + bh / 2 + e.get("size", 24) * 0.36, f, "white", a, track=3)
        cv.restore()


class Bar(El):
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        e = s.e; x, w, y = e.get("x", 130), e.get("w", 820), e["y"] + dy; col = e.get("color", "orange")
        f = font("mono", 22)
        draw_text(cv, e["label"].upper(), x, y, f, col, a, track=2)
        draw_text(cv, e.get("value", ""), x + w, y, f, col, a, track=2, anchor="r")
        by = y + 14; fill = e.get("fill", 1.0) * ease(s.p(t - 0.1, e.get("dur", 0.9)))
        cv.drawRect(skia.Rect(x, by, x + w, by + 34), paint("white", a))
        if e.get("dashed"):
            pt = paint(col, a, stroke=2); pt.setPathEffect(skia.DashPathEffect.Make([10, 8], 0))
            cv.drawRect(skia.Rect(x + 1, by + 1, x + w - 1, by + 33), pt)
        else:
            cv.drawRect(skia.Rect(x + 1, by + 1, x + w - 1, by + 33), paint("#DCE2EE", a, stroke=2))
        if fill > 0: cv.drawRect(skia.Rect(x + 2, by + 2, x + 2 + (w - 4) * fill, by + 32), paint(col, a))


class Strike(El):
    """A claim that gets crossed out at "strike_at" (the "My take" move)."""
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1); s.ts = at(e.get("strike_at", -1), e.get("strike_delay", 0.0))
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        e = s.e; f = font("sans", e.get("size", 52)); sp = ease(0 if t < s.ts else min(1, (t - s.ts) / 0.4))
        col = "muted" if sp > 0 else "navy"; y = e["y"] + dy
        w = draw_text(cv, e["text"], CX, y, f, col, a, anchor="c")
        if sp > 0:
            x0 = CX - w / 2; cv.drawRect(skia.Rect(x0, y - e.get("size", 52) * 0.3, x0 + w * sp, y - e.get("size", 52) * 0.3 + 5), paint("muted", a))


# 3D isometric block
THEMES = {"blue": ("#86A9F2", "#4079E2", "#2C58C0", "white"), "orange": ("#FFB98A", "#F28A3C", "#D9692A", "white"),
          "white": ("#FFFFFF", "#EAF0FA", "#D3DEF0", "navy")}
K = 0.866


def draw_block(cv, x, y, a, h, theme, alpha=1.0, label=None, label_size=None, wire_only=False, b=None):
    b = b or a
    def P(X, Y, Z):
        return (x + (X - Y) * K - (a - b) / 2 * K, y + (X + Y) * 0.5 - Z - (a + b) / 4)
    def poly(pts, pt):
        path = skia.Path(); path.moveTo(*P(*pts[0]))
        for q in pts[1:]: path.lineTo(*P(*q))
        path.close(); cv.drawPath(path, pt)
    top, left, right, ink = THEMES[theme]
    if not wire_only:
        sh = skia.Paint(AntiAlias=True, Color=skia.Color(60, 80, 130, int(34 * alpha)),
                        MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 10))
        cv.save(); cv.translate(10, 12); poly([(0, 0, 0), (a, 0, 0), (a, b, 0), (0, b, 0)], sh); cv.restore()
        poly([(a, 0, 0), (a, b, 0), (a, b, h), (a, 0, h)], paint(right, alpha))
        poly([(0, b, 0), (a, b, 0), (a, b, h), (0, b, h)], paint(left, alpha))
        poly([(0, 0, h), (a, 0, h), (a, b, h), (0, b, h)], paint(top, alpha))
        if theme == "white":
            for pts in ([(0, b, 0), (a, b, 0), (a, 0, 0), (a, 0, h), (0, 0, h), (0, b, h), (0, b, 0)],):
                pth = skia.Path(); pth.moveTo(*P(*pts[0]))
                for q in pts[1:]: pth.lineTo(*P(*q))
                cv.drawPath(pth, paint("blue", alpha, stroke=3))
    else:
        pt = paint("blue", alpha * 0.8, stroke=3); pt.setPathEffect(skia.DashPathEffect.Make([12, 9], 0))
        for e0, e1 in [((0, 0, 0), (a, 0, 0)), ((a, 0, 0), (a, b, 0)), ((a, b, 0), (0, b, 0)), ((0, b, 0), (0, 0, 0)),
                       ((0, 0, h), (a, 0, h)), ((a, 0, h), (a, b, h)), ((a, b, h), (0, b, h)), ((0, b, h), (0, 0, h)),
                       ((0, 0, 0), (0, 0, h)), ((a, 0, 0), (a, 0, h)), ((a, b, 0), (a, b, h)), ((0, b, 0), (0, b, h))]:
            cv.drawLine(*P(*e0), *P(*e1), pt)
    if label and not wire_only:
        fs = label_size or min(h * 0.45, a * 0.4); f = font("sans", fs)
        lx, ly = P(a / 2, b, h / 2)
        cv.save(); cv.concat(skia.Matrix.MakeAll(K, 0, lx, 0.5, 1, ly, 0, 0, 1))
        draw_text(cv, label, 0, fs * 0.36, f, ink, alpha, anchor="c"); cv.restore()


class Block(El):
    def draw(s, cv, t):
        e = s.e; p = spring(s.p(t, 0.5)) if s.t0 > -0.5 else 1.0; a = s.out(t) * min(1, s.p(t, 0.12) * 3 if s.t0 > -0.5 else 1)
        if a <= 0: return
        draw_block(cv, e["x"], e["y"] - 30 * (1 - p), e.get("a", 120), e.get("h", 100), e.get("theme", "orange"), a,
                   e.get("label"), e.get("label_size"), e.get("wire", False), e.get("b"))


class Steps(El):
    """A vertical chain of small cards joined by arrows (like the Binance attack path). Each step appears at its own time."""
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1); s.ts = [at(v, 0.0) for v in e.get("step_at", [])]
    def draw(s, cv, t):
        e = s.e; x, w = e.get("x", 130), e.get("w", 620); y = e["y"]; gap = 120
        if e.get("title") and t >= s.t0:
            draw_text(cv, e["title"].upper(), x, y - 22, font("mono", 22), "muted", s.out(t) * ease(s.p(t)), track=3)
        for i, st in enumerate(e["steps"]):
            ti = s.ts[i] if i < len(s.ts) else s.t0
            p = ease(0 if t < ti else min(1, (t - ti) / 0.35)); a = p * s.out(t)
            yy = y + i * gap + 18 * (1 - p)
            if a <= 0: continue
            hl = i in e.get("hl", [0, len(e["steps"]) - 1])
            bg = "#FDF1E8" if hl else "white"; bc = "orange" if hl else "card_border"
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, yy + 5, x + w, yy + 85), 6, 6), paint("orange_pale" if hl else "card_shadow", a))
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, yy, x + w, yy + 80), 6, 6), paint(bg, a))
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, yy, x + w, yy + 80), 6, 6), paint(bc, a, stroke=2))
            draw_text(cv, f"{i + 1:02d}", x + 18, yy + 48, font("mono", 20), "orange" if hl else "blue", a)
            draw_text(cv, st[0], x + 70, yy + 40, font("sans6", 32), "navy", a)
            if len(st) > 1: draw_text(cv, st[1].upper(), x + 70, yy + 66, font("mono", 16), "muted", a, track=2)
            if i:
                ax = x + w / 2; cv.drawLine(ax, yy - 36, ax, yy - 10, paint("orange", a, stroke=3))
                pth = skia.Path(); pth.moveTo(ax - 8, yy - 16); pth.lineTo(ax + 8, yy - 16); pth.lineTo(ax, yy - 6); pth.close()
                cv.drawPath(pth, paint("orange", a))


class Ref(El):
    """Reference card for the last scene: source headline, site, date line, and a small orange block."""
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        e = s.e; x, w, y = 110, 860, e["y"] + dy
        f = font("sans", 50); lines = wrap(e["headline"], f, w - 60)
        h = 70 + 58 * len(lines) + 50 + 48 * len(wrap(e.get("line", ""), font("sans5", 30), w - 60)) + 24
        card_box(cv, x, y, w, h, a)
        bt = "REFERENCE"; bf = font("mono6", 22); bw = text_w(bt, bf, 3) + 28
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x + 30, y + 26, x + 30 + bw, y + 64), 4, 4), paint("blue", a))
        draw_text(cv, bt, x + 44, y + 53, bf, "white", a, track=3)
        yy = y + 70
        for ln in lines: yy += 58; draw_text(cv, ln, x + 30, yy, f, "navy", a)
        yy += 46; site = e.get("site", "")
        n = int(len(site) * min(1, max(0, (t - s.t0 - 0.4) * 30 / max(1, len(site)))))
        draw_text(cv, site[:n], x + 30, yy, font("mono", 26), "blue", a)
        for ln in wrap(e.get("line", ""), font("sans5", 30), w - 60):
            yy += 48; draw_text(cv, ln, x + 30, yy, font("sans5", 30), "muted", a)
        draw_block(cv, x + w - 70, y + 30, 90, 50, "orange", a)


class Follow(El):
    def draw(s, cv, t):
        p = spring(s.p(t, 0.5)); a = s.out(t) * min(1, s.p(t, 0.15) * 3)
        if a <= 0: return
        f = font("sans", 52); h = s.e.get("handle", "@theunhyped.ai")
        w1 = text_w("Follow ", f); w2 = text_w(h, f) + 28; x = CX - (w1 + w2) / 2; y = s.e["y"]
        cv.save(); sc = 0.9 + 0.1 * p; cv.translate(CX, y - 18); cv.scale(sc, sc); cv.translate(-CX, -(y - 18))
        draw_text(cv, "Follow ", x, y, f, "navy", a)
        bx = x + w1
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(bx, y - 52 + 6, bx + w2, y + 14 + 6), 10, 10), paint("orange_dark", a))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(bx, y - 52, bx + w2, y + 14), 10, 10), paint("orange", a))
        draw_text(cv, h, bx + 14, y, f, "white", a); cv.restore()


class Text(El):
    def draw(s, cv, t):
        a, dy = s.rise(t)
        if a <= 0: return
        e = s.e; kind = e.get("font", "sans6"); x = e.get("x", "c")
        draw_text(cv, e["text"], CX if x == "c" else x, e["y"] + dy, font(kind, e.get("size", 40)), e.get("color", "navy"), a,
                  track=e.get("track", 0), anchor="c" if x == "c" else e.get("anchor", "l"))


TYPES = {"kicker": Kicker, "head": Head, "number": Number, "card": Card, "badge": Badge, "bar": Bar, "strike": Strike,
         "block": Block, "steps": Steps, "ref": Ref, "follow": Follow, "text": Text}
NEEDS_AT = (Card, Strike, Steps)


def build(spec, times, total):
    def at(v, delay=0.0):
        if v == -1 or v is None: return -1.0
        if isinstance(v, list):
            s, e = times[v[0]]; return s + (e - s) * v[1] + delay
        return times[v][0] + delay
    scenes = []
    for sc in spec["scenes"]:
        u = sc.get("until", "end")
        t1 = total + 5 if u == "end" else times[u][0] - 0.05
        els = []
        for e in sc["els"]:
            cls = TYPES[e["type"]]; t0 = at(e.get("at"), e.get("delay", 0.0))
            els.append(cls(e, t0, t1, at) if cls in NEEDS_AT else cls(e, t0, t1))
        start = min([el.t0 for el in els] + [t1])
        scenes.append({"sub": sc.get("sub", ""), "start": start, "end": t1, "els": els})
    return scenes


# ---------------- word-by-word captions ----------------
CAP_SIZE, CAP_Y = 58, 1190


def caption_chunks(spec, times, words=None):
    """words: optional exact word timings per phrase from the aligner [[(word, s, e), ...], ...].
    Without them, words are spread over the phrase by length (good enough, the aligner is preferred)."""
    import re
    f = font("sans", CAP_SIZE); chunks = []
    for pi, (ph, (s, e)) in enumerate(zip(spec["phrases"], times)):
        cw = ph.get("cap", ph["say"]).split()
        if words and pi < len(words) and len(words[pi]) == len(cw):
            timed = [(w, a, b) for w, (_, a, b) in zip(cw, words[pi])]
        else:
            wts = [len(re.sub(r"[^\w]", "", w)) + 1.6 + (2 if re.search(r"\d", w) else 0) for w in cw]
            tot = sum(wts); acc = s; timed = []
            for w, k in zip(cw, wts):
                d = (e - s) * k / tot; timed.append((w, acc, acc + d)); acc += d
        # split at sentence/clause ends first, then into even groups of at most 4 words that fit one line
        parts, cur = [], []
        for it in timed:
            cur.append(it)
            if it[0][-1] in ".?!:;" or (it[0][-1] == "," and len(cur) >= 3): parts.append(cur); cur = []
        if cur: parts.append(cur)
        for part in parts:
            n = max(1, math.ceil(len(part) / 4))
            while True:
                size = math.ceil(len(part) / n); groups = [part[i:i + size] for i in range(0, len(part), size)]
                if all(text_w(" ".join(x[0] for x in g), f) <= 800 for g in groups) or size == 1: break
                n += 1
            chunks.extend(groups)
    out = []
    for i, c in enumerate(chunks):
        st, en = c[0][1], c[-1][2]
        nxt = chunks[i + 1][0][1] if i + 1 < len(chunks) else en + 1.5
        out.append((st - 0.05, min(nxt - 0.05, en + 0.5), c))
    return out


def draw_caption(cv, t, chunks):
    f = font("sans", CAP_SIZE); sp = 16; pad = 12
    for st, en, words in chunks:
        if not (st <= t < en): continue
        active = None
        for i, (w, ws, we) in enumerate(words):
            if ws - 0.03 <= t: active = i
        if t > words[-1][2] + 0.05: active = None
        widths = [text_w(w[0], f) for w in words]
        total = sum(widths) + sp * (len(words) - 1) + (2 * (pad + 6) if active is not None else 0)
        x = CX - total / 2; y = CAP_Y
        for i, (w, wd) in enumerate(zip(words, widths)):
            if i == active:
                x += 6
                cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y - 52 + 6, x + wd + 2 * pad, y + 16 + 6), 10, 10), paint("orange_dark"))
                cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y - 52, x + wd + 2 * pad, y + 16), 10, 10), paint("orange"))
                draw_text(cv, w[0], x + pad, y, f, "white"); x += wd + 2 * pad + 6 + sp
            else:
                draw_text(cv, w[0], x, y, f, "navy"); x += wd + sp


# ---------------- render ----------------
def render(spec, times, total, wav, out_mp4, stills=None, words=None):
    paper = make_paper()
    scenes = build(spec, times, total)
    chunks = caption_chunks(spec, times, words)
    dur = round(total + 0.4, 2)
    surf = skia.Surface(W, H); cv = surf.getCanvas()

    def frame(t):
        cv.drawImage(paper, 0, 0)
        idx = 0
        for i, sc in enumerate(scenes):
            if t >= (sc["start"] if i else -9): idx = i
        for i, sc in enumerate(scenes):
            if i < len(scenes) - 1:
                fo = max(0., min(1., (sc["end"] - t) / 0.2))
            else:
                fo = 1.0
            if fo <= 0 or (i and t < sc["start"] - 0.01): continue
            if fo < 1: cv.saveLayerAlpha(None, int(255 * fo))
            for el in sc["els"]:
                if el.t0 <= t + 0.01 and t < el.t1: el.draw(cv, t)
            if fo < 1: cv.restore()
        draw_header(cv, spec.get("series", "What It Means"), spec.get("dwg", "000"), idx + 1, scenes[idx]["sub"], t / dur)
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


# ---------------- cover (same layout as the Binance cover) ----------------
DEFAULT_BLOCKS = [{"x": 330, "y": 1010, "a": 250, "h": 36, "theme": "orange"},
                  {"x": 640, "y": 1090, "a": 150, "h": 150, "theme": "blue", "label": "$"},
                  {"x": 810, "y": 900, "a": 110, "h": 110, "theme": "blue", "label": "$"}]


def cover(spec, out_png, dwg=None):
    """cover: {"lines": ["$6.3B", "crypto heist."], "box": "One laptop?", "stamp": "RECORD",
               "blocks": [...optional, like the block element...], "footer": "News · What's real"}"""
    c = spec["cover"]; s = skia.Surface(W, H); cv = s.getCanvas()
    cv.drawImage(make_paper(), 0, 0)
    cv.drawRect(skia.Rect(92, 328, 108, 344), paint("orange"))
    draw_text(cv, spec.get("series", "What It Means").upper(), 132, 344, font("mono", 28), "muted", track=6)
    lab = f"DWG {dwg or spec.get('dwg', '000')}"; f = font("mono", 28); w = text_w(lab, f, 5)
    cv.drawRect(skia.Rect(990 - w - 32, 300, 990, 354), paint("#FFFFFF", 0.4))
    cv.drawRect(skia.Rect(990 - w - 32, 300, 990, 354), paint("muted", stroke=2))
    draw_text(cv, lab, 990 - w - 16, 337, f, "muted", track=5)
    cv.drawRect(skia.Rect(90, 352, 990, 354), paint("line"))
    size = c.get("size", 116); fh = font("sans", size); y = 395
    for ln in c["lines"]:
        while text_w(ln, fh, -4) > 900 and size > 70: size -= 4; fh = font("sans", size)
    for ln in c["lines"]:
        y += size * 1.08; draw_text(cv, ln, 88, y - size * 0.2, fh, "navy", track=-4)
    if c.get("box"):
        while text_w(c["box"], fh, -4) > 860 and size > 70: size -= 4; fh = font("sans", size)
        bw = text_w(c["box"], fh, -4) + 44; top = y + 12
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(90, top + 10, 90 + bw, top + size * 1.2 + 10), 16, 16), paint("orange_dark"))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(90, top, 90 + bw, top + size * 1.2), 16, 16), paint("orange"))
        draw_text(cv, c["box"], 112, top + size * 0.95, fh, "white", track=-4)
    for b in c.get("blocks", DEFAULT_BLOCKS):
        sh = skia.Paint(AntiAlias=True, Color=skia.Color(60, 80, 130, 30), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 6))
        r = b.get("a", 120) * 0.95
        cv.drawOval(skia.Rect(b["x"] - r, b["y"] + b.get("a", 120) * 0.1, b["x"] + r, b["y"] + b.get("a", 120) * 0.55), sh)
    for b in c.get("blocks", DEFAULT_BLOCKS):
        draw_block(cv, b["x"], b["y"], b.get("a", 120), b.get("h", 100), b.get("theme", "orange"), 1.0,
                   b.get("label"), b.get("label_size"), b.get("wire", False))
    if c.get("stamp"):
        fs = font("mono6", 58); sw = text_w(c["stamp"], fs, 8) + 68
        cv.save(); cv.translate(820, 1220); cv.rotate(-8)
        cv.drawRect(skia.Rect(-sw / 2, -50, sw / 2, 50), paint("#FBF4EE"))
        cv.drawRect(skia.Rect(-sw / 2, -50, sw / 2, 50), paint("orange", stroke=6))
        draw_text(cv, c["stamp"], 0, 20, fs, "orange_dark", track=8, anchor="c"); cv.restore()
    draw_text(cv, c.get("footer", "News · What's real").upper(), 90, 1475, font("mono6", 34), "blue", track=7)
    draw_text(cv, spec.get("handle", "@theunhyped.ai").upper(), 90, 1590, font("mono", 28), "muted", track=5)
    from PIL import Image
    Image.fromarray(s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]).save(out_png)
