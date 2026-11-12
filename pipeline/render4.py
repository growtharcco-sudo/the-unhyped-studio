"""The Unhyped engine v4, "Keynote" style.

Black stage, one huge idea per screen, a hard cut every 1.5 to 3 seconds, a slow push-in so the frame
never sits still, captions synced word by word, and a sound bed (soft music + whoosh / tick / pop / boom).
No particles, glows or gimmicks: just big type, numbers and simple cards.

Spec: "engine": 4 and a "beats" list (instead of "scenes"). Each beat runs from its "at" until the next one.
  at: -1 (frame 1), phrase index i, or [i, fraction]
  k:  title {pill, lines, hl, sub}         huge headline (first frame)
      big   {text, hl, sub, size}         one statement ("\n" for line breaks, hl = words in orange)
      step  {n, label}                    "01 / FASTER" chapter card
      num   {to, prefix, suffix, sub, dec}   number that counts up
      swap  {old, new, sub, new_at}       old value struck out, new value lands
      dots  {n, sub}                      a row of numbered circles, the last one in orange
      pair  {left: {title, lines}, right: {...}, mid, right_at}   two cards side by side
      photo {image, lines, hl, pill, sub, ring}   a real photo (rounded, 540x540) with a 1 to 2 line headline under it
      end   {text, sub}                   follow card
  optional on any beat: sub_at (when the sub line appears), step_no (header 03/05 counter)
"""
import math, os, subprocess
import numpy as np
import skia
import render as v1

W, H, FPS, CX, CY = 1080, 1920, 30, 540, 840
FD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
C = {"bg": "#060607", "bg2": "#141418", "text": "#FFFFFF", "soft": "#A1A1AA", "dim": "#4A4A52",
     "line": "#26262C", "card": "#111114", "card_edge": "#2A2A31", "accent": "#FF7A1A", "accent2": "#4C8DFF"}
_tf = {}


def font(w, size):
    if w not in _tf: _tf[w] = skia.Typeface.MakeFromFile(os.path.join(FD, f"inter-{w}.ttf"))
    f = skia.Font(_tf[w], size); f.setSubpixel(True); f.setEdging(skia.Font.Edging.kAntiAlias); return f


def mono(size):
    if "mono" not in _tf: _tf["mono"] = skia.Typeface.MakeFromFile(os.path.join(FD, "plex-mono-semibold.ttf"))
    f = skia.Font(_tf["mono"], size); f.setSubpixel(True); return f


def rgb(h, a=255): h = h.lstrip("#"); return skia.Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)
def paint(col, a=1.0, stroke=0):
    p = skia.Paint(AntiAlias=True, Color=rgb(C.get(col, col), int(255 * max(0, min(1, a)))))
    if stroke: p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(stroke)
    return p
def tw(s, f, track=0): return f.measureText(s) + track * max(0, len(s) - 1)
def ease(p): p = max(0., min(1., p)); return 1 - (1 - p) ** 3
def text(cv, s, x, y, f, col, a=1.0, track=0, anchor="l"):
    w = tw(s, f, track); x = x - w / 2 if anchor == "c" else (x - w if anchor == "r" else x); p = paint(col, a)
    if not track: cv.drawString(s, x, y, f, p); return w
    for ch in s: cv.drawString(ch, x, y, f, p); x += f.measureText(ch) + track
    return w


def rich_line(cv, line, x, y, f, hl, a=1.0, anchor="c", track=0):
    """draw a line word by word, words found in hl are orange"""
    words = line.split(" "); sp = tw(" ", f); total = sum(tw(w, f, track) for w in words) + sp * (len(words) - 1)
    x = x - total / 2 if anchor == "c" else x
    for w in words:
        col = "accent" if w.strip(".,!?:") in hl or w in hl else "text"
        text(cv, w, x, y, f, col, a, track); x += tw(w, f, track) + sp
    return total


def fit(lines, weight, size, maxw, track=0):
    while size > 40 and any(tw(l, font(weight, size), track * size) > maxw for l in lines): size -= 4
    return size


_img = {}


def photo_image(path, side):
    """square crop (faces sit high, so keep the top), scaled to side x side, as a skia image"""
    key = (path, side)
    if key not in _img:
        from PIL import Image
        im = Image.open(path if os.path.isabs(path) else os.path.join(os.path.dirname(FD), "..", path)).convert("RGB")
        w, h = im.size; m = min(w, h); top = 0 if h > w else 0; left = (w - m) // 2
        im = im.crop((left, top, left + m, top + m)).resize((side, side), Image.LANCZOS)
        _img[key] = skia.Image.fromarray(np.dstack([np.asarray(im), np.full((side, side), 255, np.uint8)]),
                                         colorType=skia.kRGBA_8888_ColorType)
    return _img[key]


def draw_photo(cv, b, age, side=540, top=430):
    q = ease(age / 0.3); x = CX - side / 2; y = top + 24 * (1 - q)
    r = skia.RRect.MakeRectXY(skia.Rect(x, y, x + side, y + side), 44, 44)
    cv.save(); cv.clipRRect(r, doAntiAlias=True)
    p = skia.Paint(AntiAlias=True); p.setAlphaf(q)
    cv.drawImageRect(photo_image(b["image"], side), skia.Rect(x, y, x + side, y + side), skia.SamplingOptions(skia.FilterMode.kLinear), p)
    cv.drawRect(skia.Rect(x, y + side * 0.62, x + side, y + side), skia.Paint(Shader=skia.GradientShader.MakeLinear(
        [(0, y + side * 0.62), (0, y + side)], [rgb(C["bg"], 0), rgb(C["bg"], 200)])))
    cv.restore()
    cv.drawRRect(r, paint("accent" if b.get("ring") else "card_edge", q, stroke=5 if b.get("ring") else 2))
    if b.get("pill"):
        pf = mono(30); pw = tw(b["pill"], pf, 5) + 44; py = y + 40
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(x + 30, py - 4, x + 30 + pw, py + 48), 26, 26), paint("accent", q))
        text(cv, b["pill"], x + 30 + pw / 2, py + 32, pf, "bg", q, track=5, anchor="c")
    hl = set((b.get("hl") or "").split()); lines = b["lines"]
    size = fit(lines, 900, b.get("size", 100), 940, -0.03); f = font(900, size); yy = y + side + 40 + size * 0.8
    for ln in lines:
        rich_line(cv, ln, CX, yy, f, hl, q, track=-0.03 * size); yy += size * 1.02
    if b.get("sub"): text(cv, b["sub"], CX, yy + 6, font(600, 42), "soft", ease((age - 0.2) / 0.25), anchor="c")
    return yy


# ---------------- beats ----------------
def draw_beat(cv, b, t, t0, t1, at):
    k = b["k"]; age = t - t0
    sub_t = at(b["sub_at"]) if b.get("sub_at") is not None else t0 + 0.35
    hl = set((b.get("hl") or "").split())

    def sub(y, s=None, size=46, col="soft"):
        s = s or b.get("sub")
        if not s or t < sub_t: return
        q = ease((t - sub_t) / 0.25)
        for i, ln in enumerate(s.split("\n")):
            text(cv, ln, CX, y + 16 * (1 - q) + i * size * 1.25, font(600, size), col, q, anchor="c")

    if k in ("title", "big"):
        lines = (b["lines"] if k == "title" else b["text"].split("\n"))
        size = fit(lines, 900, b.get("size", 150 if k == "title" else 112), 920, -0.03)
        f = font(900, size); lh = size * 1.02; y = CY - (len(lines) - 1) * lh / 2 + size * 0.36
        if b.get("pill"):
            pf = mono(30); pw = tw(b["pill"], pf, 5) + 44; py = y - size - 70
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(CX - pw / 2, py - 40, CX + pw / 2, py + 12), 26, 26), paint("accent"))
            text(cv, b["pill"], CX, py - 4, pf, "bg", track=5, anchor="c")
        for ln in lines:
            rich_line(cv, ln, CX, y, f, hl, track=-0.03 * size); y += lh
        sub(y + 30 - lh + 40)
    elif k == "step":
        q = ease(age / 0.2)
        n = f"{b['n']:02d}"; f = font(900, 330)
        text(cv, n, CX, CY + 40, f, "accent", q, track=-12, anchor="c")
        text(cv, b["label"].upper(), CX, CY + 190, font(800, 84), "text", ease((age - 0.08) / 0.2), track=-1, anchor="c")
    elif k == "num":
        d = b.get("dur", 0.7); q = ease(age / d); v = b["to"] * q; dec = b.get("dec", 0)
        s = f"{b.get('prefix', '')}{v:,.{dec}f}{b.get('suffix', '')}"
        size = fit([f"{b.get('prefix', '')}{b['to']:,.{dec}f}{b.get('suffix', '')}"], 900, b.get("size", 330), 940)
        if b.get("label"): text(cv, b["label"].upper(), CX, CY - size * 0.78, mono(32), "soft", track=6, anchor="c")
        text(cv, s, CX, CY + size * 0.36, font(900, size), "accent" if q >= 1 else "text", track=-0.04 * size, anchor="c")
        sub(CY + size * 0.36 + 100)
    elif k == "swap":
        tn = at(b["new_at"]) if b.get("new_at") is not None else t0 + 0.6
        fo = font(800, 150); y0 = CY - 130; ow = tw(b["old"], fo)
        old_a = 0.35 if t >= tn else 1.0
        text(cv, b["old"], CX, y0, fo, "text" if t < tn else "soft", old_a, anchor="c")
        sp = ease((t - (tn - 0.25)) / 0.22)
        if sp > 0: cv.drawRect(skia.Rect(CX - ow / 2 - 14, y0 - 58, CX - ow / 2 - 14 + (ow + 28) * sp, y0 - 46), paint("accent"))
        if t >= tn:
            q = (t - tn) / 0.22; sc = 1 + 0.25 * (1 - ease(q))
            cv.save(); cv.translate(CX, y0 + 230); cv.scale(sc, sc); cv.translate(-CX, -(y0 + 230))
            ns = fit([b["new"]], 900, 300, 940, -0.04)
            text(cv, b["new"], CX, y0 + 330, font(900, ns), "accent", min(1, q * 3), track=-0.04 * ns, anchor="c"); cv.restore()
        sub(y0 + 460)
    elif k == "dots":
        n = b.get("n", 5); r = 70; gap = 34; x0 = CX - (n * 2 * r + (n - 1) * gap) / 2 + r
        for i in range(n):
            q = ease((age - i * 0.07) / 0.2); last = i == n - 1; x = x0 + i * (2 * r + gap)
            cv.save(); cv.translate(x, CY); cv.scale(0.6 + 0.4 * q, 0.6 + 0.4 * q)
            cv.drawCircle(0, 0, r, paint("accent" if last else "card", q))
            if not last: cv.drawCircle(0, 0, r, paint("card_edge", q, stroke=3))
            text(cv, str(i + 1), 0, 26, font(900, 74), "bg" if last else "soft", q, anchor="c"); cv.restore()
        sub(CY + 200, size=58, col="text")
    elif k == "pair":
        tr = at(b["right_at"]) if b.get("right_at") is not None else t0 + 0.5
        cw, ch, y = 440, 420, CY - 200
        for side, x, tt in ((b["left"], 70, t0), (b["right"], 570, tr)):
            if t < tt: continue
            q = ease((t - tt) / 0.25); hi = side.get("hl", False)
            cv.save(); cv.translate(0, 30 * (1 - q))
            r = skia.RRect.MakeRectXY(skia.Rect(x, y, x + cw, y + ch), 36, 36)
            cv.drawRRect(r, paint("card", q)); cv.drawRRect(r, paint("accent" if hi else "card_edge", q, stroke=4 if hi else 2))
            text(cv, side["title"], x + 40, y + 110, font(900, 64), "accent" if hi else "text", q, track=-2)
            yy = y + 200
            for ln in side["lines"]:
                text(cv, ln, x + 40, yy, font(600, 40), "soft", q); yy += 64
            cv.restore()
        if b.get("mid"): text(cv, b["mid"].upper(), CX, y + ch + 110, mono(34), "soft", ease(age / 0.3), track=6, anchor="c")
    elif k == "photo":
        draw_photo(cv, b, age if t0 > 0 else 9.0)   # the hook is fully visible on frame 0
    elif k == "end":
        q = ease(age / 0.25)
        text(cv, b.get("text", "@theunhyped.ai"), CX, CY + 30, font(900, 110), "text", q, track=-3, anchor="c")
        sub(CY + 130, size=48)


# ---------------- frame chrome ----------------
def draw_bg(cv):
    cv.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=skia.GradientShader.MakeRadial(
        (CX, CY), 1100, [rgb(C["bg2"]), rgb(C["bg"])], [0, 1])))


def draw_header(cv, t, total, step_no, steps):
    text(cv, "THE UNHYPED", 72, 300, mono(28), "soft", track=6)
    if step_no:
        s = f"{step_no:02d}/{steps:02d}"; f = mono(28); w = tw(s, f, 4) + 36
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect(1008 - w, 266, 1008, 314), 24, 24), paint("card_edge"))
        text(cv, s, 1008 - w / 2, 300, f, "text", track=4, anchor="c")
    cv.drawRect(skia.Rect(72, 340, 1008, 343), paint("line"))
    cv.drawRect(skia.Rect(72, 340, 72 + 936 * min(1, t / total), 343), paint("accent"))


CAP_Y, CAP_SIZE = 1420, 56


def draw_caption(cv, t, chunks):
    f = font(800, CAP_SIZE); sp = tw(" ", f)
    for st, en, words in chunks:
        if not (st <= t < en): continue
        ws = [w[0] for w in words]; total = sum(tw(w, f) for w in ws) + sp * (len(ws) - 1); x = CX - total / 2
        for w, a, b in words:
            on = a - 0.03 <= t; cur = on and t < b + 0.08
            col = "accent" if cur else ("text" if on else "dim")
            text(cv, w, x, CAP_Y, f, col); x += tw(w, f) + sp


# ---------------- sound ----------------
SR = 48000


def _env(n, a, r):
    e = np.ones(n); ai = max(1, int(a * SR)); ri = max(1, int(r * SR))
    e[:ai] = np.linspace(0, 1, ai); e[-ri:] *= np.linspace(1, 0, ri); return e


def sfx_whoosh(d=0.32):
    from scipy.signal import butter, sosfilt
    n = int(d * SR); x = np.random.default_rng(1).standard_normal(n)
    out = np.zeros(n); seg = n // 16
    for i in range(16):
        fc = 500 + 5000 * math.sin(math.pi * (i + 0.5) / 16)
        out[i * seg:(i + 1) * seg] = sosfilt(butter(2, [fc * 0.5, min(fc * 1.6, 20000)], "band", fs=SR, output="sos"), x[i * seg:(i + 1) * seg])
    t = np.linspace(0, 1, n); return out * np.sin(np.pi * t) ** 1.5 * 0.5


def sfx_tick():
    n = int(0.03 * SR); t = np.arange(n) / SR; return np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 180) * 0.35


def sfx_pop():
    n = int(0.18 * SR); t = np.arange(n) / SR; f = 900 * np.exp(-t * 12) + 220
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22) * 0.55


def sfx_boom():
    n = int(0.9 * SR); t = np.arange(n) / SR; f = 70 * np.exp(-t * 2.5) + 38
    return np.tanh(1.6 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 4) * 0.8


def music(dur, bpm=96):
    """quiet bed: soft chords (Am F C G) + a gentle pulse on every beat"""
    n = int(dur * SR); t = np.arange(n) / SR; out = np.zeros(n); beat = 60 / bpm; bar = 4 * beat
    chords = [(57, 60, 64), (53, 57, 60), (48, 55, 64), (55, 59, 62)]
    for ci in range(int(dur / bar) + 1):
        s = int(ci * bar * SR); e = min(n, int((ci + 1) * bar * SR) + int(0.4 * SR))
        if s >= n: break
        tt = t[s:e] - t[s]; env = np.minimum(1, tt / 0.5) * np.exp(-tt * 0.25); env[-int(0.4 * SR):] *= np.linspace(1, 0, int(0.4 * SR)) if len(env) > int(0.4 * SR) else 1
        for m in chords[ci % 4]:
            fr = 440 * 2 ** ((m - 69) / 12)
            for h, g in ((1, 1), (2, 0.35), (3, 0.12)):
                out[s:e] += env * g * 0.05 * (np.sin(2 * np.pi * fr * h * tt) + np.sin(2 * np.pi * fr * h * 1.003 * tt))
        bass = 440 * 2 ** ((chords[ci % 4][0] - 12 - 69) / 12)
        out[s:e] += env * 0.09 * np.sin(2 * np.pi * bass * tt)
    for bi in range(int(dur / beat)):     # soft kick pulse
        s = int(bi * beat * SR); m = min(n - s, int(0.25 * SR))
        if m <= 0: break
        tk = np.arange(m) / SR; out[s:s + m] += np.sin(2 * np.pi * (55 + 60 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 14) * 0.22
    fade = np.ones(n); fi = int(0.6 * SR); fade[:fi] = np.linspace(0, 1, fi); fade[-int(1.2 * SR):] = np.linspace(1, 0, int(1.2 * SR))
    return out * fade


def mix(voice_wav, out_wav, beats_t, events, dur):
    import soundfile as sf
    v, sr = sf.read(voice_wav)
    if v.ndim > 1: v = v.mean(1)
    if sr != SR:
        from scipy.signal import resample_poly; v = resample_poly(v, SR, sr)
    n = int(dur * SR) + SR; out = np.zeros(n); out[:len(v)] += v
    m = music(n / SR); out += m * 10 ** (-17 / 20) / (np.sqrt(np.mean(m ** 2)) + 1e-9) * 0.1
    lib = {"whoosh": sfx_whoosh(), "tick": sfx_tick(), "pop": sfx_pop(), "boom": sfx_boom()}
    gains = {"whoosh": 0.22, "tick": 0.25, "pop": 0.3, "boom": 0.45}
    for kind, at in events:
        s = max(0, int(at * SR)); x = lib[kind] * gains[kind]; e = min(n, s + len(x)); out[s:e] += x[:e - s]
    peak = np.max(np.abs(out)); out = out / peak * 0.95 if peak > 0.98 else out
    sf.write(out_wav, out[:int(dur * SR)].astype(np.float32), SR)


# ---------------- render ----------------
def resolver(times):
    def at(a):
        if a is None or a == -1: return 0.0
        if isinstance(a, (int, float)): return times[int(a)][0]
        i, fr = a; s, e = times[i]; return s + (e - s) * fr
    return at


def plan(spec, times, total):
    at = resolver(times); dur = round(total + 0.4, 2); beats = spec["beats"]
    ts = [at(b["at"]) for b in beats]
    out = [(b, ts[i], ts[i + 1] if i + 1 < len(beats) else dur) for i, b in enumerate(beats)]
    ev = [("boom", 0.0)]
    for b, t0, t1 in out[1:]: ev.append(("whoosh", max(0, t0 - 0.12)))
    for b, t0, t1 in out:
        if b["k"] == "num": ev += [("tick", t0 + i * 0.07) for i in range(int(b.get("dur", 0.7) / 0.07))] + [("pop", t0 + b.get("dur", 0.7))]
        if b["k"] == "swap": ev.append(("pop", at(b["new_at"]) if b.get("new_at") is not None else t0 + 0.6))
        if b["k"] == "step": ev.append(("pop", t0 + 0.02))
    return out, ev, dur, at


def render(spec, times, total, wav, out_mp4, stills=None, words=None):
    beats, events, dur, at = plan(spec, times, total)
    chunks = v1.caption_chunks(spec, times, words)
    steps = spec.get("steps", 5)
    surf = skia.Surface(W, H); cv = surf.getCanvas()

    def frame(t, chrome=True):
        draw_bg(cv)
        cur = [x for x in beats if x[1] <= t + 1e-6] or beats[:1]
        b, t0, t1 = cur[-1]
        age = max(0, t - t0); push = 1 + 0.035 * min(1, age / max(0.5, t1 - t0)); pin = 1 + 0.06 * (1 - ease(age / 0.18))
        sc = push * pin
        cv.save(); cv.translate(CX, CY); cv.scale(sc, sc); cv.translate(-CX, -CY)
        a = min(1, age / 0.06) if t0 > 0 else 1
        if a < 1: cv.saveLayerAlpha(None, int(255 * a))
        draw_beat(cv, b, t, t0, t1, at)
        if a < 1: cv.restore()
        cv.restore()
        if chrome:
            sn = max([x[0].get("step_no", 0) for x in cur] or [0]); sn = b.get("step_no", sn)
            draw_header(cv, t, dur, sn, steps); draw_caption(cv, t, chunks)
        return surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)

    if stills:
        from PIL import Image
        for t in stills: Image.fromarray(frame(t)[..., :3]).save(f"{out_mp4}.still_{t:05.1f}.png")
        return
    mixwav = out_mp4 + ".mix.wav"; mix(wav, mixwav, [x[1] for x in beats], events, dur)
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
    """cover: {"pill": "NEW", "lines": [...], "hl": "5.2", "sub": "5 things to know", "image": optional photo path}"""
    c = spec["cover"]; s = skia.Surface(W, H); cv = s.getCanvas(); draw_bg(cv)
    b = {"k": "title", "pill": c.get("pill"), "lines": c["lines"], "hl": c.get("hl"), "sub": c.get("sub"), "size": c.get("size", 170)}
    if c.get("image"): b = {"k": "photo", "image": c["image"], "pill": c.get("pill"), "lines": c["lines"], "hl": c.get("hl"),
                            "sub": c.get("sub"), "size": c.get("size", 120), "ring": True}
    draw_beat(cv, b, 5.0, 0.0, 9.0, lambda a: 0.0)
    text(cv, "THE UNHYPED", CX, 1520, mono(32), "soft", track=8, anchor="c")
    from PIL import Image
    Image.fromarray(s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]).save(out_png)
