"""Word timings (faster-whisper). Any language Whisper knows: en, hi, te, ta, kn ... Cached next to the video."""
import json, os, subprocess
import numpy as np


def words_path(src):
    return os.path.splitext(src)[0] + '.words.json'


def _audio(src, sr=16000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def transcribe(src, lang=None, model=None):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit('Word timing needs faster-whisper: pip install faster-whisper  (or pass --words your.words.json)')
    model = model or os.environ.get('WHISPER_MODEL', 'small')   # use "medium" or "large-v3" for Telugu/Hindi
    m = WhisperModel(model, device='cpu', compute_type='int8')
    segs, info = m.transcribe(_audio(src), language=lang, word_timestamps=True, vad_filter=True)
    return [dict(w=w.word.strip(), s=round(w.start, 2), e=round(w.end, 2)) for s in segs for w in (s.words or [])]


def get_words(src, lang=None, words_file=None, force=False):
    """Reuse <video>.words.json when it is newer than the video, so hand-fixed spellings stick."""
    if words_file:
        return json.load(open(words_file))
    p = words_path(src)
    if not force and os.path.exists(p) and os.path.getmtime(p) >= os.path.getmtime(src):
        return json.load(open(p))
    w = transcribe(src, lang)
    json.dump(w, open(p, 'w'), indent=0, ensure_ascii=False)
    return w


def remap(words, kept):
    """Move word times onto the trimmed timeline. kept = [(start, end)] in source seconds. Words in cut parts vanish."""
    out, off = [], 0.0
    for a, b in kept:
        for w in words:
            if w['s'] >= a - 0.02 and w['s'] < b:
                out.append(dict(w=w['w'], s=round(w['s'] - a + off, 3), e=round(min(w['e'], b) - a + off, 3)))
        off += b - a
    return out
