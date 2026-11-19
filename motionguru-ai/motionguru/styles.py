"""Styles = named recipes. A style + your words -> a plan, with effects placed on the moments that matter.

Placement rules (so it never looks like confetti): one hook in the first seconds, emphasis effects only on keywords/numbers,
at least `gap` seconds apart, never more than `max`, never during the hook.
"""
import json, os, re
from .util import ROOT

DIR = os.path.join(ROOT, 'styles')
STOP = set('the a an and or but so to of in on at for with is are was were be been it this that these those you your i we they he she as by from not do does did have has had will would can could just very really about into than then there here what when which who how also more most some any all out up'.split())


def list_styles():
    return {f[:-5]: json.load(open(os.path.join(DIR, f))) for f in sorted(os.listdir(DIR)) if f.endswith('.json')}


def pick_keywords(words, n=6):
    """Fallback when nobody gave keywords: numbers first, then the longest content words that are not stop words."""
    seen, scored = set(), []
    for w in words:
        t = re.sub(r'[^\w]', '', w['w']).lower()
        if not t or t in STOP or t in seen: continue
        seen.add(t); scored.append((bool(re.search(r'\d', t)) * 10 + len(t), t))
    return [t for _, t in sorted(scored, reverse=True)[:n]]


def build_plan(name, words, dur, keywords=None, engine=True, brand_text=None):
    st = list_styles()
    if name not in st: raise SystemExit(f"Unknown style '{name}'. Choices: {', '.join(st)}")
    s = st[name]; kws = [k.lower() for k in (keywords or pick_keywords(words))]
    fx, sfx_events = [], []
    if s.get('grade'): fx.append(dict(fx='grade', name=s['grade']))
    if s.get('vignette'): fx.append(dict(fx='vignette'))
    if s.get('grain'): fx.append(dict(fx='grain', amount=s['grain']))
    if s.get('watermark'): fx.append(dict(fx='watermark', start=0.5, end=dur))
    hook = s.get('hook'); t0 = 0.35; hook_end = 0.0
    hit = [w for w in words if re.sub(r'[^\w]', '', w['w']).lower() in kws]
    if hook:
        text = (brand_text or (hit[0]['w'] if hit else (words[0]['w'] if words else 'WATCH'))).upper().strip('.,!?')
        use_engine = hook['fx'] == 'backdrop-word' and engine and s.get('engine')
        d = min(hook['dur'], max(1.0, dur - 1))
        if hook['fx'] == 'backdrop-word' and not use_engine: fx.append(dict(fx='title', start=t0, end=t0 + d, text=text))
        elif use_engine: fx.append(dict(fx='backdrop-word', start=t0, end=t0 + d, text=text, font='bold'))
        else: fx.append(dict(fx='title', start=t0, end=t0 + d, text=text))
        if hook.get('flash'): fx.append(dict(fx='flash', start=t0, end=t0 + 0.18))
        if hook.get('glitch'): fx.append(dict(fx='glitch', start=t0, end=t0 + 0.3))
        if hook.get('sfx'): sfx_events.append((t0, hook['sfx'], 0.8))
        hook_end = t0 + d
    if s.get('lower_third') and dur > 6: fx.append(dict(fx='lower_third', start=hook_end + 0.3, end=hook_end + 3.3))
    em = s.get('emphasis', {}); last = hook_end; n = 0; cycle = em.get('fx', ['punch']); spot = em.get('spotlight_once') and engine and s.get('engine')
    for w in sorted(hit, key=lambda x: x['s']):
        if n >= em.get('max', 6) or w['s'] < hook_end + 0.5 or w['s'] - last < em.get('gap', 4.0) or w['s'] > dur - 0.8: continue
        kind = cycle[n % len(cycle)]
        if spot and n == 1:
            fx.append(dict(fx='spotlight', start=w['s'] - 0.1, end=min(dur, w['s'] + 1.8), text=re.sub(r'[^\w]', '', w['w']).upper()))
        elif kind == 'punch': fx.append(dict(fx='punch', start=w['s'] - 0.05, end=w['s'] + 0.55, amp=em.get('amp', 0.12)))
        elif kind == 'shake': fx.append(dict(fx='shake', start=w['s'], end=w['s'] + 0.6))
        elif kind == 'glitch': fx.append(dict(fx='glitch', start=w['s'], end=w['s'] + 0.28))
        last = w['s']; n += 1
        if s.get('stat_on_numbers') and re.search(r'\d', w['w']) and w['s'] > hook_end + 1:
            fx.append(dict(fx='stat', start=w['s'] + 0.2, end=min(dur, w['s'] + 2.4), value=re.sub(r'[^\w%.+]', '', w['w']).upper(), label='key number'))
    plan = dict(lang=None, sfx=True, captions=dict(style=s['captions']['style'], y=s['captions']['y'], keywords='|'.join(kws)) if s.get('captions') else None,
                effects=fx, sfx_events=sfx_events, style=name)
    return plan
