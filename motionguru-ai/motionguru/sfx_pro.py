"""Sound design: synthesised SFX (no licences) plus a drop-in slot for premium packs you own.

Put licensed .wav/.mp3 files in sfx_pack/ named by role (whoosh_01.wav, riser_02.mp3, impact.wav, glitch.wav ...).
When a file for a role exists it is used instead of the synth version.
"""
import glob, os, random, subprocess, tempfile, wave
import numpy as np
from .util import ROOT

SR = 48000
_rng = np.random.default_rng(7)


def _env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-t / d)


def _sweep_noise(dur, f0, f1, q=0.35, curve=1.0):
    """Band-passed noise whose centre frequency glides f0 -> f1 (STFT mask, vectorised)."""
    n = int(dur * SR); N, hop = 2048, 512
    x = np.concatenate([_rng.standard_normal(n), np.zeros(N)])
    win = np.hanning(N); frames = 1 + (len(x) - N) // hop
    freqs = np.fft.rfftfreq(N, 1 / SR); y = np.zeros(len(x))
    for i in range(frames):
        u = (i * hop / max(1, n)) ** curve; fc = f0 * (f1 / f0) ** min(1, u)
        mask = np.exp(-0.5 * (np.log2((freqs + 1) / fc) / q) ** 2)
        y[i * hop:i * hop + N] += np.fft.irfft(np.fft.rfft(x[i * hop:i * hop + N] * win) * mask) * win
    y = y[:n]; return y / (np.abs(y).max() + 1e-9)


def whoosh(dur=0.5, up=True):
    y = _sweep_noise(dur, 300, 5200, 0.55) if up else _sweep_noise(dur, 5200, 300, 0.55)
    return y * np.sin(np.pi * np.linspace(0, 1, len(y))) ** 1.4 * 0.7


def riser(dur=1.6):
    n = int(dur * SR); t = np.arange(n) / SR; u = t / dur
    nz = _sweep_noise(dur, 200, 8000, 0.7, 1.6) * u ** 1.8
    tone = np.sin(2 * np.pi * np.cumsum(120 * (8 ** u)) / SR) * u ** 2 * 0.35
    return (nz * 0.8 + tone) * 0.8


def impact():
    n = int(1.1 * SR); t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(38 + 90 * np.exp(-t / 0.07)) / SR) * _env(n, 0.002, 0.28)
    crack = _sweep_noise(1.1, 4000, 500, 0.9) * _env(n, 0.0008, 0.05)
    return (sub * 0.9 + crack * 0.5) * 0.9


def sub_drop():
    n = int(1.4 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(90 * np.exp(-t / 0.55) + 28) / SR) * _env(n, 0.004, 0.6) * 0.9


def glitch():
    n = int(0.28 * SR); t = np.arange(n) / SR
    y = np.zeros(n)
    for k in range(7):
        a = int(_rng.uniform(0, 0.22) * SR); l = int(_rng.uniform(0.01, 0.04) * SR)
        f = _rng.choice([220, 440, 880, 1760, 3520])
        seg = np.sign(np.sin(2 * np.pi * f * t[:l])) * 0.5 + _rng.standard_normal(l) * 0.2
        y[a:a + l] += seg[:max(0, n - a)][:l] * np.hanning(l)
    return np.round(y * 6) / 6 * 0.55


def pop():
    n = int(0.09 * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(240 + 820 * np.exp(-t / 0.012)) / SR) * _env(n, 0.0015, 0.028) * 0.5


def tick():
    n = int(0.035 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 2400 * t) * _env(n, 0.0004, 0.006) + 0.35 * np.sin(2 * np.pi * 4800 * t) * _env(n, 0.0003, 0.003)) * 0.32


def shutter():
    a = tick() * 1.6; gap = np.zeros(int(0.06 * SR)); b = _sweep_noise(0.05, 3000, 6000) * _env(int(0.05 * SR), 0.001, 0.015) * 0.5
    return np.concatenate([a, gap, b])


def notify():
    n = int(0.5 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * 988 * t) * _env(n, 0.002, 0.12) + np.sin(2 * np.pi * 1319 * np.maximum(0, t - 0.09)) * (t > 0.09) * _env(n, 0.002, 0.2)) * 0.28


def typing(n_keys=6):
    return np.concatenate([np.pad(tick() * _rng.uniform(.6, 1), (0, int(_rng.uniform(.04, .09) * SR))) for _ in range(n_keys)])


SYNTH = dict(whoosh=whoosh, whoosh_down=lambda: whoosh(0.5, False), riser=riser, impact=impact, sub_drop=sub_drop, glitch=glitch,
             pop=pop, tick=tick, shutter=shutter, notify=notify, typing=typing)
_cache = {}


def _load_file(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32).astype(np.float64)
    return y / (np.abs(y).max() + 1e-9) * 0.8


def sound(name):
    """Premium pack file if present (random pick), else the synth sound."""
    files = sorted(glob.glob(os.path.join(ROOT, 'sfx_pack', name + '*')))
    if files:
        return _load_file(random.choice(files))
    if name not in _cache: _cache[name] = SYNTH[name]()
    return _cache[name]


def mix(events, dur, gain_db=0.0):
    """events: [(time, name, loudness)] -> stereo int16"""
    out = np.zeros(int(dur * SR) + 2 * SR); g0 = 10 ** (gain_db / 20)
    for t, name, g in events:
        s = sound(name); i = int(max(0, t) * SR)
        if i >= len(out): continue
        j = min(len(out), i + len(s)); out[i:j] += s[:j - i] * g * g0
    out = np.tanh(out[:int(dur * SR)] * 0.9)
    return (np.repeat(out[:, None], 2, 1) * 32767).astype(np.int16)


def write(path, pcm):
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


# what each motion effect sounds like: (offset s, sound, loudness). Riser-style sounds land BEFORE the hit.
AUTO = {
    'punch': [(0.0, 'impact', 0.55)], 'shake': [(0.0, 'impact', 0.5)], 'flash': [(0.0, 'shutter', 0.7)], 'glitch': [(0.0, 'glitch', 0.8)],
    'title': [(0.0, 'whoosh', 0.55), (0.12, 'pop', 0.7)], 'lower_third': [(0.0, 'whoosh', 0.4), (0.3, 'pop', 0.45)],
    'stat': [(0.0, 'riser', 0.5), (1.1, 'impact', 0.55)], 'transition': [(-0.15, 'whoosh', 0.7)], 'hook': [(-1.3, 'riser', 0.5), (0.0, 'impact', 0.7)],
}


def events_for(fx_list):
    ev = []
    for f in fx_list:
        if f.get('sfx') is False: continue
        for off, name, g in AUTO.get(f['fx'], []):
            ev.append((f['start'] + off, f.get('sfx') or name if isinstance(f.get('sfx'), str) else name, g))
    return ev
