"""Free voiceover with Kokoro v1.0 (Apache-2.0, commercial use allowed). Channel voice: am_liam.

Each phrase is generated separately, so we know exactly when every phrase starts and ends.
Then every phrase is force-aligned word by word (pocketsphinx, offline), so captions light up on the
exact spoken word. If a phrase can't be aligned (an unusual word), its words are spread by length.
"""
import difflib, os, re, subprocess, urllib.request
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.environ.get("KOKORO_DIR", os.path.join(HERE, "models"))
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ["kokoro-v1.0.onnx", "voices-v1.0.bin"]
VOICE = "am_liam"


def ensure_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    for f in FILES:
        p = os.path.join(MODEL_DIR, f)
        if not os.path.exists(p) or os.path.getsize(p) < 1_000_000:
            print("downloading", f)
            try:
                urllib.request.urlretrieve(BASE + f, p)
            except Exception:  # some sandboxes only allow curl through their proxy
                subprocess.run(["curl", "-sSL", "-o", p, BASE + f], check=True)
    return [os.path.join(MODEL_DIR, f) for f in FILES]


def _norm(w): return re.sub(r"[^a-z0-9']", "", w.lower())


_dec = None


def _align(audio24k, text):
    """Word timings (seconds from phrase start) for one phrase, or None if it can't be aligned."""
    global _dec
    try:
        from pocketsphinx import Decoder
    except ImportError:
        return None
    words = [_norm(w) for w in re.sub(r"[-/]", " ", text).split()]
    words = [w for w in words if w]
    if not words: return None
    try:
        if _dec is None: _dec = Decoder(bestpath=False)
        a16 = np.interp(np.arange(0, len(audio24k), 1.5), np.arange(len(audio24k)), audio24k)
        pcm = (np.clip(a16 / (np.abs(a16).max() + 1e-9) * 0.9, -1, 1) * 32767).astype(np.int16).tobytes()
        _dec.set_align_text(" ".join(words))
        _dec.start_utt(); _dec.process_raw(pcm, full_utt=True); _dec.end_utt()
        segs = [(s.word.split("(")[0], s.start_frame / 100, (s.end_frame + 1) / 100) for s in _dec.seg()
                if s.word not in ("<s>", "</s>", "<sil>", "(NULL)", "[NOISE]")]
    except Exception:
        return None
    return segs if len(segs) == len(words) else None


def map_caption_words(cap, say_segs, s, e):
    """Give every caption word a (start, end). Caption words that match spoken words take their exact time;
    the rest (like "$750 billion" for "seven hundred and fifty billion dollars") share the time of the
    spoken words they replace."""
    cw = cap.split()
    if not say_segs:
        return None
    cn = [_norm(w) for w in cw]; sn = [w for w, _, _ in say_segs]
    out = [None] * len(cw)
    sm = difflib.SequenceMatcher(None, cn, sn, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1): out[i1 + k] = (cw[i1 + k], say_segs[j1 + k][1] + s, say_segs[j1 + k][2] + s)
        else:
            if i2 == i1: continue
            if j2 > j1: t0, t1 = say_segs[j1][1] + s, say_segs[j2 - 1][2] + s
            else:   # no spoken words to borrow: squeeze between neighbours
                t0 = out[i1 - 1][2] if i1 and out[i1 - 1] else s
                t1 = say_segs[j1][1] + s if j1 < len(say_segs) else e
            wts = [len(w) + 2 for w in cw[i1:i2]]; tot = sum(wts); acc = t0
            for k, wt in enumerate(wts):
                d = (t1 - t0) * wt / tot; out[i1 + k] = (cw[i1 + k], acc, acc + d); acc += d
    return out if all(out) else None


def synth(phrases, out_wav, voice=VOICE, speed=1.05, lead=0.15, tail=0.25):
    """phrases: list of dicts with 'say', optional 'cap' and 'pause' (seconds of silence BEFORE the phrase).
    Returns (wav path, phrase times [(start, end)], total seconds, caption word times per phrase or None)."""
    from kokoro_onnx import Kokoro
    k = Kokoro(*ensure_model())
    lang = "en-gb" if voice.startswith("b") else "en-us"
    chunks, times, words, t, sr = [], [], [], lead, 24000
    chunks.append(np.zeros(int(lead * sr), np.float32))
    aligned = 0
    for i, ph in enumerate(phrases):
        if i:
            gap = float(ph.get("pause", 0.4))
            chunks.append(np.zeros(int(gap * sr), np.float32)); t += gap
        a, sr = k.create(ph["say"], voice=voice, speed=float(ph.get("speed", speed)), lang=lang)
        a = np.asarray(a, np.float32)
        nz = np.where(np.abs(a) > 0.01 * np.abs(a).max())[0]
        a = a[max(0, nz[0] - 240):min(len(a), nz[-1] + 480)]           # trim silence, keep soft edges
        s, e = round(t, 3), round(t + len(a) / sr, 3)
        segs = _align(a, ph["say"])
        cw = map_caption_words(ph.get("cap", ph["say"]), segs, s, e) if segs else None
        aligned += cw is not None
        words.append(cw)
        chunks.append(a); times.append((s, e)); t += len(a) / sr
    chunks.append(np.zeros(int(tail * sr), np.float32))
    y = np.concatenate(chunks)
    raw = out_wav + ".raw.wav"
    sf.write(raw, y / np.abs(y).max() * 0.9, sr)
    # two-pass loudness for Reels/Shorts (-14 LUFS, true peak -1.5 dB) at 48 kHz
    import json as _j
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = _j.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", raw, "-af", af, "-ar", "48000", out_wav], check=True)
    os.remove(raw)
    print(f"voice: {len(phrases)} phrases, {aligned} aligned word by word, {len(y) / sr:.1f}s")
    return out_wav, times, len(y) / sr, words
