"""Motion graphics as ffmpeg filters + animated PNG overlays. Everything is time-windowed and lands in ONE graph.

Camera/colour fx (filters):  punch, shake, flash, glitch, grade, vignette, grain
Overlay fx (animated PNGs):  title (spring pop), lower_third (slides in, your face), stat (big number), watermark (your face bug)
Each plan item: {"fx": "punch", "start": 3.2, "end": 3.9, ...options}
"""
import os, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .util import FONTS
from . import brand as B

GRADES = {
    'cinematic': 'curves=all=0/0 0.25/0.21 0.75/0.8 1/1,colorbalance=rs=.05:bs=-.04:rh=-.02:bh=.05,eq=saturation=1.08:contrast=1.06',
    'warm': 'colorbalance=rs=.06:gs=.01:bs=-.06:rh=.04:bh=-.04,eq=saturation=1.1',
    'cool': 'colorbalance=rs=-.05:bs=.07:rh=-.03:bh=.05,eq=saturation=1.05',
    'pop': 'eq=contrast=1.12:saturation=1.35:gamma=0.97',
    'bw': 'hue=s=0,eq=contrast=1.15',
    'moody': 'curves=all=0/0 0.3/0.22 0.7/0.72 1/0.96,eq=saturation=0.85:contrast=1.1,colorbalance=bs=.06:rs=-.03',
}


def _font(name, size):
    for f in os.listdir(FONTS):
        if f.lower().startswith(name.lower().split()[0]) and f.endswith('.ttf') and 'LICENSE' not in f:
            return ImageFont.truetype(os.path.join(FONTS, f), size)
    return ImageFont.load_default()


def _rrect(d, box, r, fill):
    d.rounded_rectangle(box, r, fill=fill)


def png_title(text, W, H, color, out, sub=None):
    f = _font(B.load()['font_head'], int(H * 0.075)); im = Image.new('RGBA', (W, int(H * 0.2)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    text = text.upper(); tw = d.textlength(text, font=f)
    while tw > W * 0.9 and f.size > 20: f = ImageFont.truetype(f.path, f.size - 4); tw = d.textlength(text, font=f)
    x, y = (W - tw) / 2, int(H * 0.03)
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x + 6, y + 8), text, font=f, fill=(0, 0, 0, 200))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    d.text((x, y), text, font=f, fill=B.hex_rgb(color) + (255,), stroke_width=max(2, H // 300), stroke_fill=(0, 0, 0, 255))
    im.save(out); return im.size


def png_lower_third(name, handle, W, H, out):
    b = B.load(); s = H / 1920; h = int(190 * s); w = int(W * 0.8)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    _rrect(d, (0, 0, w - 1, h - 1), h // 2, (14, 14, 20, 225)); _rrect(d, (0, 0, int(14 * s), h - 1), int(7 * s), B.hex_rgb(b['accent']) + (255,))
    if os.path.exists(b['avatar_path']):
        av = Image.open(b['avatar_path']).convert('RGBA').resize((h - int(30 * s),) * 2, Image.LANCZOS)
        im.alpha_composite(av, (int(26 * s), int(15 * s)))
    tx = h + int(10 * s)
    d.text((tx, int(h * .16)), name, font=_font(b['font_head'], int(h * .34)), fill=(255, 255, 255, 255))
    d.text((tx, int(h * .58)), handle, font=_font(b['font_body'], int(h * .21)), fill=B.hex_rgb(b['accent']) + (255,))
    im.save(out); return im.size


def png_stat(value, label, W, H, out):
    b = B.load(); s = H / 1920; w, h = int(W * 0.7), int(420 * s)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    _rrect(d, (0, 0, w - 1, h - 1), int(46 * s), (255, 255, 255, 40)); _rrect(d, (int(3 * s), int(3 * s), w - 4, h - 4), int(44 * s), (16, 16, 24, 215))
    fv = _font(b['font_head'], int(h * .52)); tw = d.textlength(value, font=fv)
    d.text(((w - tw) / 2, int(h * .08)), value, font=fv, fill=B.hex_rgb(b['accent']) + (255,))
    fl = _font(b['font_body'], int(h * .13)); lw = d.textlength(label.upper(), font=fl)
    d.text(((w - lw) / 2, int(h * .78)), label.upper(), font=fl, fill=(255, 255, 255, 235)); im.save(out); return im.size


def png_watermark(W, H, out):
    b = B.load(); s = H / 1920; n = int(120 * s)
    im = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    if os.path.exists(b['avatar_path']):
        im.alpha_composite(Image.open(b['avatar_path']).convert('RGBA').resize((n, n), Image.LANCZOS))
    im.save(out); return im.size


class Graph:
    """Collects filters + overlay inputs, then emits one filter_complex string."""

    def __init__(self, W, H, fps, dur, tmp=None):
        self.W, self.H, self.fps, self.dur = W, H, fps, dur
        self.tmp = tmp or tempfile.mkdtemp(prefix='mguru_'); self.cam = []; self.ov = []; self.grade = []

    # ---- camera / colour (applied in order to the video) ----
    def punch(self, a, b, amp=0.16, **_):
        d = b - a; z = f"(1+{amp}*sin(PI*min(1,(t-{a})/{d}))^0.7)"
        self.cam.append(f"scale=w='trunc(iw*if(between(t,{a},{b}),{z},1)/2)*2':h='trunc(ih*if(between(t,{a},{b}),{z},1)/2)*2':eval=frame:flags=bicubic,crop={self.W}:{self.H}")

    def shake(self, a, b, amp=0.012, **_):
        px = max(4, int(self.W * amp)); on = f"between(t,{a},{b})"
        self.cam.append(f"scale=iw*1.04:ih*1.04,crop={self.W}:{self.H}:x='(iw-{self.W})/2+if({on},{px}*sin(t*90)*exp(-(t-{a})*3),0)':y='(ih-{self.H})/2+if({on},{px}*cos(t*77)*exp(-(t-{a})*3),0)'")

    def flash(self, a, b, strength=0.7, **_):
        self.cam.append(f"eq=brightness='if(between(t,{a},{b}),{strength}*(1-(t-{a})/{b - a}),0)':eval=frame")

    def glitch(self, a, b, amount=14, **_):
        self.cam.append(f"rgbashift=rh={amount}:bh=-{amount}:gv={amount // 2}:enable='between(t,{a},{b})',noise=alls=40:allf=t:enable='between(t,{a},{b})'")

    def grade_(self, name='cinematic', a=0, b=1e9, **_):
        self.grade.append(GRADES[name])

    def vignette(self, **_): self.grade.append('vignette=PI/5')
    def grain(self, amount=9, **_): self.grade.append(f'noise=alls={amount}:allf=t')

    # ---- overlay fx: PNG looped as an extra input ----
    def title(self, a, b, text='WATCH THIS', color=None, y=0.30, **_):
        p = os.path.join(self.tmp, f't{len(self.ov)}.png'); png_title(text, self.W, self.H, color or B.load()['accent'], p)
        self.ov.append(dict(png=p, a=a, b=b, kind='pop', y=y))

    def lower_third(self, a, b, name=None, handle=None, y=0.80, **_):
        bb = B.load(); p = os.path.join(self.tmp, f'l{len(self.ov)}.png'); png_lower_third(name or bb['name'], handle or bb['handle'], self.W, self.H, p)
        self.ov.append(dict(png=p, a=a, b=b, kind='slide', y=y))

    def stat(self, a, b, value='10X', label='faster', y=0.30, **_):
        p = os.path.join(self.tmp, f's{len(self.ov)}.png'); png_stat(str(value), label, self.W, self.H, p)
        self.ov.append(dict(png=p, a=a, b=b, kind='pop', y=y))

    def watermark(self, a=0, b=None, **_):
        p = os.path.join(self.tmp, f'w{len(self.ov)}.png'); png_watermark(self.W, self.H, p)
        self.ov.append(dict(png=p, a=a, b=b or self.dur, kind='fade', y=0.09, corner=True))

    def add(self, item):
        item = dict(item); f = item.pop('fx'); a = float(item.pop('start', 0)); b = float(item.pop('end', a + 1.0))
        table = dict(punch=self.punch, shake=self.shake, flash=self.flash, glitch=self.glitch, grade=self.grade_, vignette=self.vignette,
                     grain=self.grain, title=self.title, lower_third=self.lower_third, stat=self.stat, watermark=self.watermark)
        if f not in table: raise ValueError(f"unknown motion fx '{f}'. Choices: {', '.join(table)}")
        table[f](a=a, b=b, **item)

    def build(self, src_label='[vcut]', first_extra=1, sub=None, out='[vout]'):
        """Return (filter_complex text, extra ffmpeg input args). Extra inputs start at ffmpeg input index `first_extra`."""
        chain, W, H = [], self.W, self.H
        pre = ','.join(self.cam + self.grade)
        parts = [f"{src_label}{pre if pre else 'null'}[v0]"]; last = 'v0'; extra = []
        for k, o in enumerate(self.ov):
            idx = first_extra + k
            extra += ['-framerate', f'{self.fps:.3f}', '-loop', '1', '-t', f'{self.dur:.3f}', '-i', o['png']]
            a, b = o['a'], o['b']; lab = f'o{k}'
            if o['kind'] == 'pop':
                s = f"max(0.02,1-exp(-14*(t-{a}))*cos(22*(t-{a})))"
                parts.append(f"[{idx}:v]format=rgba,fade=t=out:st={b - 0.15:.3f}:d=0.15:alpha=1,scale=w='max(2,iw*if(gte(t,{a}),{s},0.02))':h=-2:eval=frame[{lab}s]")
                pos = f"x='(W-w)/2':y='H*{o['y']}-h/2'"
            elif o['kind'] == 'slide':
                e = f"(1-exp(-9*(t-{a})))"
                parts.append(f"[{idx}:v]format=rgba,fade=t=out:st={b - 0.25:.3f}:d=0.25:alpha=1[{lab}s]")
                pos = f"x='W*0.1-(1-if(gte(t,{a}),{e},0))*(w+W*0.1)':y='H*{o['y']}-h/2'"
            else:
                parts.append(f"[{idx}:v]format=rgba,fade=t=in:st={a:.3f}:d=0.4:alpha=1,colorchannelmixer=aa=0.85[{lab}s]")
                pos = f"x='W-w-W*0.05':y='H*0.06'"
            parts.append(f"[{last}][{lab}s]overlay={pos}:enable='between(t,{a},{b})':eof_action=pass[{lab}]"); last = lab
        if sub: parts.append(f"[{last}]{sub}[{last}c]"); last = last + 'c'
        parts.append(f"[{last}]format=yuv420p{out}")
        return ';\n'.join(parts), extra
