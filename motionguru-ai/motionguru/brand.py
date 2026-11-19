"""Creator brand kit: name, handle, colours and your face avatar (assets/avatar.png)."""
import json, os
from .util import ROOT

PATH = os.path.join(ROOT, 'brand.json')
DEFAULT = dict(name='Chaituverse', handle='@chaituverse', tagline='MotionGuru AI',
               avatar=os.path.join('assets', 'avatar.png'), accent='#FFD400', accent2='#7C5CFF', text='#FFFFFF',
               font_head='Anton', font_body='Poppins')


def load():
    b = dict(DEFAULT)
    if os.path.exists(PATH):
        b.update(json.load(open(PATH)))
    b['avatar_path'] = b['avatar'] if os.path.isabs(b['avatar']) else os.path.join(ROOT, b['avatar'])
    return b


def save(**kw):
    b = {k: v for k, v in load().items() if k != 'avatar_path'}
    b.update({k: v for k, v in kw.items() if v})
    json.dump(b, open(PATH, 'w'), indent=1)
    return load()


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
