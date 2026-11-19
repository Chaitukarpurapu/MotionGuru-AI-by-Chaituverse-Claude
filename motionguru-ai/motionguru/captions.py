"""Pro captions as ASS subtitles, burned by libass in the same single encode as everything else.
Fast (no per-frame Python), crisp at any resolution, and editable: open the .ass file in Aegisub or CapCut.
Styles: hormozi | karaoke | pill | minimal | neon.   Indic scripts: drop a Noto Sans Telugu/Devanagari font in fonts/.
"""
import os, re, subprocess
from .util import FONTS, ROOT
from . import brand as B

SCRIPT_FONTS = [  # (unicode range, font family to look for)
    ((0x0C00, 0x0C7F), 'Noto Sans Telugu'), ((0x0900, 0x097F), 'Noto Sans Devanagari'), ((0x0B80, 0x0BFF), 'Noto Sans Tamil'),
    ((0x0C80, 0x0CFF), 'Noto Sans Kannada'), ((0x0600, 0x06FF), 'Noto Sans Arabic')]

STYLES = {  # font, size (fraction of height), per-chunk words, upper-case, outline, active colour, shape
    'hormozi':  dict(font='Anton', size=0.058, words=2, upper=True, outline=0.006, pop=118),
    'karaoke':  dict(font='Poppins', bold=1, size=0.036, words=5, upper=False, outline=0.004, pop=108),
    'pill':     dict(font='Poppins', bold=1, size=0.038, words=4, upper=False, outline=0.0, pop=100, pill=True),
    'minimal':  dict(font='Poppins', bold=1, size=0.032, words=6, upper=False, outline=0.003, pop=100, static=True),
    'neon':     dict(font='Archivo Black', size=0.05, words=2, upper=True, outline=0.0, pop=112, glow=True),
}


def _bgr(hexcol, alpha=0):
    h = hexcol.lstrip('#'); r, g, b = h[0:2], h[2:4], h[4:6]
    return f'&H{alpha:02X}{b}{g}{r}'.upper()


def _t(sec):
    cs = int(round(sec * 100)); h, r = divmod(cs, 360000); m, r = divmod(r, 6000); s, c = divmod(r, 100)
    return f'{h}:{m:02d}:{s:02d}.{c:02d}'


def _font_for(text, default):
    for (lo, hi), fam in SCRIPT_FONTS:
        if any(lo <= ord(ch) <= hi for ch in text):
            if fam.lower() in subprocess.run(['fc-list'], capture_output=True, text=True).stdout.lower() or os.path.isdir(os.path.join(ROOT, 'fonts')):
                return fam
            print(f'  note: captions contain {fam.split()[-1]} script. Install "{fam}" (or put it in fonts/) so letters do not show as boxes.')
    return default


def chunk(words, n, gap=0.55):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= n or w['s'] - cur[-1]['e'] > gap or re.search(r'[.!?]$', cur[-1]['w'])):
            out.append(cur); cur = []
        cur.append(w)
    return out + ([cur] if cur else [])


def make_ass(words, W, H, style='hormozi', keywords=(), y=0.70, accent=None, path='captions.ass', font=None):
    b = B.load(); st = STYLES[style]; accent = accent or b['accent']
    kw = {k.lower() for k in keywords}
    fs = int(H * st['size']); ol = max(0, int(H * st['outline']))
    fam = font or _font_for(' '.join(w['w'] for w in words), st['font'])
    white, dark = _bgr('#FFFFFF'), _bgr('#000000')
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{fam},{fs},{white},{white},{dark},{_bgr('#000000', 110)},{st.get('bold', 0) and -1},0,0,0,100,100,0,0,1,{ol},{max(1, ol // 2)},5,{int(W * .08)},{int(W * .08)},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    pos = f'\\an5\\pos({W // 2},{int(H * y)})'
    for ch in chunk(words, st['words']):
        for i, w in enumerate(ch):
            a = w['s']; e = ch[i + 1]['s'] if i + 1 < len(ch) else max(w['e'], w['s'] + 0.25) + 0.08
            if st.get('static'): a, e = ch[0]['s'], ch[-1]['e'] + 0.12
            if st.get('static') and i: continue
            parts = []
            for j, x in enumerate(ch):
                txt = x['w'].upper() if st['upper'] else x['w']
                txt = txt.replace('{', '(').replace('}', ')')
                hot = re.sub(r'\W', '', x['w']).lower() in kw or bool(re.search(r'\d', x['w']))
                if j == i and not st.get('static'):
                    if st.get('pill'):
                        parts.append(f"{{\\bord{int(fs * .32)}\\3c{_bgr(accent)}\\1c{_bgr('#111111')}\\shad0\\fscx{st['pop'] - 12}\\fscy{st['pop'] - 12}"
                                     f"\\t(0,90,\\fscx100\\fscy100)}}{txt}{{\\r}}")
                    elif st.get('glow'):
                        parts.append(f"{{\\1c{_bgr('#FFFFFF')}\\3c{_bgr(accent)}\\bord{int(fs * .1)}\\blur{int(fs * .12)}\\fscx{st['pop'] - 14}\\fscy{st['pop'] - 14}"
                                     f"\\t(0,100,\\fscx100\\fscy100)}}{txt}{{\\r}}")
                    else:
                        parts.append(f"{{\\1c{_bgr(accent)}\\fscx{st['pop'] - 18}\\fscy{st['pop'] - 18}\\t(0,90,\\fscx{st['pop']}\\fscy{st['pop']})}}{txt}{{\\r}}")
                elif hot:
                    parts.append(f"{{\\1c{_bgr(b['accent2'])}}}{txt}{{\\r}}")
                else:
                    parts.append(txt)
            ev.append(f"Dialogue: 0,{_t(a)},{_t(e)},Cap,,0,0,0,,{{{pos}}}{' '.join(parts)}")
    open(path, 'w', encoding='utf-8').write(hdr + '\n'.join(ev) + '\n')
    return path


def filter_for(ass_path):
    p = ass_path.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
    fd = FONTS.replace('\\', '/').replace(':', '\\:')
    extra = os.path.join(ROOT, 'fonts')
    fdir = f"fontsdir='{fd}'"
    return f"ass='{p}':{fdir}"
