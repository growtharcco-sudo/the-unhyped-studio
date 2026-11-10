"""The Unhyped engine v3 ("live" look): everything moves, and the picture reacts to the voice.

Built on render2 (same spec format, same hook / slots / punch / badge / card / bar elements), plus:
  - a living background (slow aurora + drifting particles) instead of a still grid
  - a waveform under the captions that moves with the narrator's voice
  - scenes slide in, and a scan line sweeps the screen every time a countdown step unlocks
  step   {n, title, y}                      compact "01 + title" header for one countdown step
  count  {to, prefix, suffix, y, size, dur} big number that counts up
  race   {y, rows:[[label, value, rate, "hl"]], dur}   bars racing at their real relative speeds
  swap   {old, new, y, new_at}              old value gets struck out, new value punches in
  agents {y, cols, rows, pitch}             a grid of dots lighting up in a wave (cols x rows agents)
  twins  {y, left, right, split_at, tags_at, left_tag, right_tag, mid}   one orb splits into two
  eye    {y, look_at}                       an eye that scans, then looks straight at the viewer
  type   {text, y, size, cps, color}        typewriter line with a cursor
Set "engine": 3 in the spec to use it. Visual safe area: y 400 to 1080.
"""
import math, random, subprocess
import numpy as np
import skia
import render as v1
import render2 as r2

W, H, FPS, CX = r2.W, r2.H, r2.FPS, 540
font, ease, spring, text_w = r2.font, r2.ease, r2.spring, r2.text_w
paint, draw_text, rgb, C, wrap, El = r2.paint, r2.draw_text, r2.rgb, r2.C, r2.wrap, r2.El
C.update({"cyan": "#5CE1FF", "bg0": "#05060D", "bg1": "#0A0F24"})


def glow_paint(col, a, blur):
    return skia.Paint(AntiAlias=True, Color=rgb(C.get(col, col), int(255 * max(0, min(1, a)))),
                      MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))


# ---------- living background ----------
_rng = random.Random(7)
PARTS = [(_rng.uniform(0, W), _rng.uniform(0, H), _rng.uniform(6, 26), _rng.uniform(1.2, 3.4), _rng.uniform(0, 6.28),
          _rng.random() < 0.25) for _ in range(90)]
_base = None


def draw_bg(cv, t):
    global _base
    if _base is None:
        s = skia.Surface(W, H); c = s.getCanvas()
        c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=skia.GradientShader.MakeLinear(
            [(0, 0), (0, H)], [rgb(C["bg0"]), rgb(C["bg1"]), rgb(C["bg0"])], [0, 0.45, 1])))
        _base = s.makeImageSnapshot()
    cv.drawImage(_base, 0, 0)
    for (bx, by, rad, col, sp, ph) in ((300, 620, 620, (76, 141, 255), 0.21, 0.0), (800, 900, 520, (255, 122, 26), 0.17, 2.1)):
        x = bx + 170 * math.sin(t * sp + ph); y = by + 130 * math.cos(t * sp * 1.3 + ph)
        cv.drawCircle(x, y, rad, skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeRadial(
            (x, y), rad, [skia.Color(*col, 34), skia.Color(*col, 0)])))
    for (x, y, v, r, ph, warm) in PARTS:
        yy = (y - v * t) % H; tw = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 1.7 + ph))
        cv.drawCircle(x + 14 * math.sin(t * 0.5 + ph), yy, r, paint("orange" if warm else "#8FB4FF", 0.38 * tw))


def make_paper():
    s = skia.Surface(W, H); draw_bg(s.getCanvas(), 3.0); return s.makeImageSnapshot()


# ---------- voice envelope ----------
class Env:
    def __init__(s, wav):
        s.sr = 60
        try:
            import soundfile as sf
            y, sr = sf.read(wav); y = y if y.ndim == 1 else y.mean(1); n = sr // s.sr
            e = np.sqrt((y[:len(y) // n * n].reshape(-1, n) ** 2).mean(1)); s.e = np.clip(e / (np.percentile(e, 96) + 1e-9), 0, 1)
        except Exception:
            s.e = np.zeros(1)
    def at(s, t):
        i = int(t * s.sr); return float(s.e[i]) if 0 <= i < len(s.e) else 0.0


def draw_wave(cv, env, t, y=1278):
    n, bw, gap = 41, 7, 9; x0 = CX - (n * bw + (n - 1) * gap) / 2
    for j in range(n):
        k = abs(j - n // 2); v = env.at(t - k * 0.028) * (1 - k / (n / 2 + 4)); h = 5 + 46 * v
        col = "orange" if k < 4 else ("#8FB4FF" if k < 12 else "dim")
        x = x0 + j * (bw + gap)
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, y - h / 2, x + bw, y + h / 2), 3.5, 3.5), paint(col, 0.9 if k < 12 else 0.6))


# ---------- elements ----------
class Step(El):
    def draw(s, cv, t):
        e = s.e; a = s.out(t)
        if t < s.t0 or a <= 0: return
        p = ease(s.p(t, 0.35)); y = e.get("y", 520); fn = font("sans", 170); num = f"{e['n']:02d}"
        w = text_w(num, fn)
        if e.get("glow"):
            cv.drawString(num, 90, y, fn, glow_paint("orange", a * p * (0.5 + 0.3 * math.sin(t * 5)), 26))
        cv.save(); r2.punch(cv, p, 90 + w / 2, y - 60); draw_text(cv, num, 90, y, fn, "orange", a * p); cv.restore()
        tp = ease(s.p(t - 0.12, 0.35)); size = e.get("size", 66); ft = font("sans", size); x = 90 + w + 34
        lines = wrap(e["title"], ft, 990 - x); ty = y - 60 + size * 0.36 - (len(lines) - 1) * size * 0.55
        for ln in lines:
            draw_text(cv, ln, x + 40 * (1 - tp), ty, ft, "text", a * tp); ty += size * 1.1
        lp = ease(s.p(t - 0.2, 0.5))
        cv.drawRect(skia.Rect(90, y + 34, 90 + 900 * lp, y + 37), paint("card_edge", a))
        cv.drawRect(skia.Rect(90, y + 34, 90 + 150 * lp, y + 37), paint("orange", a))


class Count(El):
    def draw(s, cv, t):
        e = s.e; a = s.out(t)
        if t < s.t0 or a <= 0: return
        q = ease(s.p(t, e.get("dur", 0.9))); v = e.get("from", 0) + (e["to"] - e.get("from", 0)) * q
        txt = f"{e.get('prefix', '')}{int(round(v)):,}{e.get('suffix', '')}"; size = e.get("size", 200); f = font("sans", size)
        pop = 1 + 0.06 * math.sin(min(1, s.p(t, e.get("dur", 0.9) + 0.25)) * math.pi) if q >= 0.999 else 1
        cv.save(); cv.translate(CX, e["y"] - size * 0.35); cv.scale(pop, pop); cv.translate(-CX, -(e["y"] - size * 0.35))
        cv.drawString(txt, CX - text_w(txt, f) / 2, e["y"], f, glow_paint(e.get("color", "orange"), a * 0.45, 30))
        draw_text(cv, txt, CX, e["y"], f, e.get("color", "orange"), a * min(1, s.p(t, 0.15) * 3), anchor="c"); cv.restore()
        if e.get("label"):
            draw_text(cv, e["label"].upper(), CX, e["y"] - size * 0.82, font("mono6", 30), "soft", a * min(1, s.p(t, 0.3)), track=6, anchor="c")


class Race(El):
    def draw(s, cv, t):
        e = s.e; a = s.out(t) * min(1, s.p(t, 0.25))
        if t < s.t0 or a <= 0: return
        rows = e["rows"]; top = max(r[2] for r in rows); prog = max(0, (t - s.t0 - 0.25) / e.get("dur", 1.6)); x, w = 90, 900
        for i, r in enumerate(rows):
            y = e["y"] + i * e.get("gap", 110); hl = len(r) > 3 and r[3] == "hl"; col = "orange" if hl else "#8FB4FF"
            fill = min(1.0, r[2] / top * min(prog, 1.0)) if prog < 1 or r[2] == top else r[2] / top
            done = hl and prog >= 1
            draw_text(cv, r[0].upper(), x, y, font("mono6", 26), "text" if hl else "soft", a, track=3)
            if r[1] and (prog >= 1):
                va = min(1, (prog - 1) * e.get("dur", 1.6) / 0.25)
                draw_text(cv, r[1].upper(), x + w, y, font("mono6", 26), col, a * va, track=2, anchor="r")
            by = y + 18
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, by, x + w, by + 30), 15, 15), paint("card", a))
            if fill > 0.02:
                cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x, by, x + w * fill, by + 30), 15, 15), paint(col, a * (1 if hl else 0.75)))
                hx = x + w * fill - 15
                cv.drawCircle(hx, by + 15, 26, glow_paint(col, a * (0.9 if not done else 0.5), 14))
                cv.drawCircle(hx, by + 15, 11, paint("white", a))


class Swap(El):
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1); s.tn = at(e.get("new_at"), 0.0) if e.get("new_at") is not None else t0 + 0.7
    def draw(s, cv, t):
        e = s.e; a = s.out(t)
        if t < s.t0 or a <= 0: return
        y = e["y"]; p = ease(s.p(t, 0.3)); fo = font("sans", 150); ow = text_w(e["old"], fo); ox = 280 - ow / 2
        sp = ease(0 if t < s.tn - 0.25 else min(1, (t - s.tn + 0.25) / 0.3))
        cv.save(); r2.punch(cv, p, 280, y - 50)
        draw_text(cv, e["old"], ox, y, fo, "dim" if sp > 0.5 else "text", a * p); cv.restore()
        if sp > 0: cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(ox - 16, y - 62, ox - 16 + (ow + 32) * sp, y - 50), 6, 6), paint("orange", a))
        if t >= s.tn:
            q = min(1, (t - s.tn) / 0.35); qe = ease(q)
            ax = 440 + 20 * (1 - qe); pth = skia.Path(); pth.moveTo(ax, y - 56); pth.lineTo(ax + 90, y - 56)
            cv.drawPath(pth, paint("soft", a * qe, stroke=10))
            hd = skia.Path(); hd.moveTo(ax + 70, y - 86); hd.lineTo(ax + 104, y - 56); hd.lineTo(ax + 70, y - 26)
            st = paint("soft", a * qe, stroke=10); st.setStrokeCap(skia.Paint.kRound_Cap); st.setStrokeJoin(skia.Paint.kRound_Join); cv.drawPath(hd, st)
            fn = font("sans", 290); nw = text_w(e["new"], fn); nx = 780 - nw / 2; sc = 1 + 0.5 * (1 - spring(q))
            cv.save(); cv.translate(780, y - 90); cv.scale(sc, sc); cv.translate(-780, -(y - 90))
            cv.drawString(e["new"], nx, y + 20, fn, glow_paint("orange", a * 0.5, 34))
            draw_text(cv, e["new"], nx, y + 20, fn, "orange", a * min(1, q * 4)); cv.restore()
            ring = min(1, (t - s.tn) / 0.6)
            cv.drawCircle(780, y - 80, 150 + 190 * ring, paint("orange", a * 0.5 * (1 - ring), stroke=5))


class Agents(El):
    def __init__(s, e, t0, t1):
        super().__init__(e, t0, t1); r = random.Random(11); s.cols, s.rows = e.get("cols", 50), e.get("rows", 20)
        cx, cy = (s.cols - 1) / 2, (s.rows - 1) / 2; md = math.hypot(cx, cy)
        s.d = [[math.hypot(i - cx, (j - cy) * 1.6) / md * e.get("wave", 1.5) + r.uniform(0, 0.25), r.uniform(0, 6.28), r.random() < 0.18]
               for j in range(s.rows) for i in range(s.cols)]
    def draw(s, cv, t):
        e = s.e; a = s.out(t) * min(1, s.p(t, 0.3))
        if t < s.t0 or a <= 0: return
        pitch = e.get("pitch", 17); x0 = CX - (s.cols - 1) * pitch / 2; y0 = e["y"]; k = 0; tt = t - s.t0 - 0.15
        for j in range(s.rows):
            for i in range(s.cols):
                d, ph, blue = s.d[k]; k += 1; x, y = x0 + i * pitch, y0 + j * pitch
                if tt < d: cv.drawCircle(x, y, 2.2, paint("card_edge", a)); continue
                q = min(1, (tt - d) / 0.25); tw = 0.62 + 0.38 * math.sin(t * 4 + ph)
                if q < 1: cv.drawCircle(x, y, 4 + 9 * (1 - q), paint("white", a * (1 - q) * 0.8))
                cv.drawCircle(x, y, 4.6, paint("cyan" if blue else "orange", a * tw))


def orb(cv, x, y, r, col, a, t, ph=0.0):
    c = rgb(C.get(col, col)); cr, cg, cb = skia.ColorGetR(c), skia.ColorGetG(c), skia.ColorGetB(c)
    cv.drawCircle(x, y, r * 1.25, glow_paint(col, a * (0.42 + 0.12 * math.sin(t * 3 + ph)), r * 0.35))
    cv.drawCircle(x, y, r, skia.Paint(AntiAlias=True, Alphaf=a, Shader=skia.GradientShader.MakeRadial(
        (x - r * 0.3, y - r * 0.35), r * 1.5, [skia.Color(255, 255, 255, 255), skia.Color(cr, cg, cb, 255), skia.Color(cr // 4, cg // 4, cb // 4, 255)], [0, 0.42, 1])))


class Twins(El):
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1); s.ts = at(e.get("split_at"), 0.0); s.tg = at(e.get("tags_at"), 0.0)
    def draw(s, cv, t):
        e = s.e; a = s.out(t) * min(1, s.p(t, 0.25))
        if t < s.t0 or a <= 0: return
        y = e["y"]; q = spring(0 if t < s.ts else min(1, (t - s.ts) / 0.7)); dx = 245 * q; r = 104 - 14 * min(1, q)
        bob = 8 * math.sin(t * 2.2)
        if q > 0.05:
            cv.drawLine(CX - dx + r, y, CX + dx - r, y, paint("card_edge", a * min(1, q), stroke=4))
            la = max(0, min(1, (t - s.ts - 0.5) / 0.3))
            if e.get("mid") and la > 0:
                f = font("mono6", 22); tw = text_w(e["mid"].upper(), f, 3)
                cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(CX - tw / 2 - 16, y - 24, CX + tw / 2 + 16, y + 24), 24, 24), paint("bg0", a * la))
                cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(CX - tw / 2 - 16, y - 24, CX + tw / 2 + 16, y + 24), 24, 24), paint("card_edge", a * la, stroke=2))
                draw_text(cv, e["mid"].upper(), CX, y + 8, f, "soft", a * la, track=3, anchor="c")
        orb(cv, CX + dx, y - bob * q, r, "orange", a * (min(1, q * 3) if q < 0.34 else 1), t, 1.3)
        orb(cv, CX - dx, y + bob * q, r, "blue", a, t)
        ga = max(0, min(1, (t - s.tg) / 0.4))
        if ga > 0:     # safeguards ring on the left one
            st = paint("cyan", a * ga, stroke=6); st.setPathEffect(skia.DashPathEffect.Make([26, 16], -t * 40)); st.setStrokeCap(skia.Paint.kRound_Cap)
            cv.drawCircle(CX - dx, y + bob * q, r + 26 + 20 * (1 - ease(ga)), st)
            r2.lock_icon(cv, CX + dx, y - bob * q + 2, 46, "white", a * ga)
        la = max(0, min(1, (t - s.ts - 0.35) / 0.3))
        for sx, name, tag, col in ((-1, e["left"], e.get("left_tag"), "cyan"), (1, e["right"], e.get("right_tag"), "orange")):
            if la <= 0: break
            x = CX + sx * dx
            draw_text(cv, name.upper(), x, y + 170, font("sans", 46), "text", a * la, anchor="c")
            if tag and ga > 0:
                yy = y + 232
                for ln in tag.upper().split("\n"):
                    draw_text(cv, ln, x, yy, font("mono6", 24), col, a * ga, track=2, anchor="c"); yy += 36


class Eye(El):
    def __init__(s, e, t0, t1, at):
        super().__init__(e, t0, t1); s.tl = at(e.get("look_at"), 0.0) if e.get("look_at") is not None else t0 + 1.4
    def draw(s, cv, t):
        e = s.e; a = s.out(t) * min(1, s.p(t, 0.25))
        if t < s.t0 or a <= 0: return
        y = e["y"]; w, h = 330, 150; op = ease(s.p(t, 0.45))
        bl = (t - s.tl) if t >= s.tl else 9; blink = 1 - math.sin(min(1, bl / 0.22) * math.pi) * 0.92 if 0 <= bl < 0.22 else 1
        hh = h * op * blink
        lid = skia.Path(); lid.moveTo(CX - w, y); lid.quadTo(CX, y - hh * 1.75, CX + w, y); lid.quadTo(CX, y + hh * 1.75, CX - w, y); lid.close()
        cv.drawPath(lid, glow_paint("orange", a * 0.28, 40))
        cv.drawPath(lid, paint("#0B0F22", a))
        look = max(0, min(1, (t - s.tl) / 0.25)); scan = math.sin((t - s.t0) * 4.2) * 150 * (1 - ease(look))
        cv.save(); cv.clipPath(lid, doAntiAlias=True)
        ix = CX + scan; ir = 104 + 10 * ease(look)
        orb(cv, ix, y, ir, "orange", a, t)
        for i in range(28):
            ang = i * math.pi / 14 + t * 0.3
            cv.drawLine(ix + 52 * math.cos(ang), y + 52 * math.sin(ang), ix + (ir - 8) * math.cos(ang), y + (ir - 8) * math.sin(ang), paint("#3A1A04", a * 0.55, stroke=3))
        cv.drawCircle(ix, y, 44 + 14 * ease(look), paint("#04050A", a))
        cv.drawCircle(ix - 20, y - 22, 13, paint("white", a * 0.9))
        cv.restore()
        st = paint("text", a, stroke=9); st.setStrokeJoin(skia.Paint.kRound_Join); cv.drawPath(lid, st)
        # scanning brackets
        bx, by = w + 46, 190; ba = a * (0.55 + 0.45 * math.sin(t * 7)) if look < 1 else a
        bp = paint("cyan" if look < 1 else "orange", ba, stroke=7); bp.setStrokeCap(skia.Paint.kSquare_Cap)
        for sx in (-1, 1):
            for sy in (-1, 1):
                p = skia.Path(); p.moveTo(CX + sx * bx, y + sy * (by - 50)); p.lineTo(CX + sx * bx, y + sy * by); p.lineTo(CX + sx * (bx - 50), y + sy * by)
                cv.drawPath(p, bp)
        if look < 1:
            ly = y - by + ((t - s.t0) * 260) % (2 * by)
            cv.drawRect(skia.Rect(CX - bx + 12, ly, CX + bx - 12, ly + 3), paint("cyan", a * 0.6))


class Type(El):
    def draw(s, cv, t):
        e = s.e; a = s.out(t)
        if a <= 0 or (t < s.t0 and s.t0 > -0.5): return
        txt = e["text"]; size = e.get("size", 40); f = font("mono6", size); n = len(txt) if s.t0 < -0.5 else int((t - s.t0) * e.get("cps", 26))
        full = text_w(txt, f); x = CX - full / 2; shown = txt[:max(0, n)]
        w = draw_text(cv, shown, x, e["y"], f, e.get("color", "soft"), a) if shown else 0
        if n < len(txt) + 14 and int(t * 3.2) % 2 == 0 or n < len(txt):
            cv.drawRect(skia.Rect(x + w + 6, e["y"] - size * 0.8, x + w + 6 + size * 0.52, e["y"] + size * 0.12), paint("orange", a))


TYPES = dict(r2.TYPES, step=Step, count=Count, race=Race, swap=Swap, agents=Agents, twins=Twins, eye=Eye, type=Type)
NEEDS_AT = r2.NEEDS_AT + (Swap, Twins, Eye)


def build(spec, times, total):
    r2.TYPES, r2.NEEDS_AT = TYPES, NEEDS_AT
    return r2.build(spec, times, total)


def render(spec, times, total, wav, out_mp4, stills=None, words=None):
    scenes, step_times = build(spec, times, total)
    chunks = v1.caption_chunks(spec, times, words)
    env = Env(wav); dur = round(total + 0.3, 2)
    surf = skia.Surface(W, H); cv = surf.getCanvas()

    def frame(t):
        draw_bg(cv, t)
        for i, sc in enumerate(scenes):
            fo = 1.0 if i == len(scenes) - 1 else max(0., min(1., (sc["end"] - t) / 0.12))
            if fo <= 0 or (i and t < sc["start"] - 0.01): continue
            q = 1.0 if i == 0 else min(1., (t - sc["start"]) / 0.28); al = fo * min(1., q * 2.2)
            cv.save()
            if q < 1: cv.translate(0, 70 * (1 - ease(q)))
            if al < 1: cv.saveLayerAlpha(None, int(255 * al))
            for el in sc["els"]:
                if (el.t0 <= t + 0.01 or el.t0 < -0.5) and t < el.t1: el.draw(cv, t)
            if al < 1: cv.restore()
            cv.restore()
        for st in step_times:          # scan line each time a step unlocks
            q = (t - st) / 0.45
            if 0 <= q < 1:
                y = 330 + 780 * ease(q); cv.drawRect(skia.Rect(0, y - 30, W, y + 30), glow_paint("orange", 0.35 * (1 - q), 26))
                cv.drawRect(skia.Rect(0, y - 2, W, y + 2), paint("orange", 0.9 * (1 - q)))
        r2.draw_header(cv, spec, t, dur, sum(1 for x in step_times if x <= t))
        draw_wave(cv, env, t)
        r2.draw_caption(cv, t, chunks)
        return surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)

    if stills:
        from PIL import Image
        for t in stills: Image.fromarray(frame(t)[..., :3]).save(f"{out_mp4}.still_{t:05.1f}.png")
        return
    tmp = out_mp4 + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                          "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                          "-af", "apad", "-t", str(dur), "-movflags", "+faststart", tmp], stdin=subprocess.PIPE)
    for i in range(int(dur * FPS)): p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait()
    if p.returncode: raise RuntimeError("ffmpeg failed")
    import os; os.replace(tmp, out_mp4)


def cover(spec, out_png, dwg=None):
    old = r2.make_paper; r2.make_paper = make_paper
    try: r2.cover(spec, out_png)
    finally: r2.make_paper = old
