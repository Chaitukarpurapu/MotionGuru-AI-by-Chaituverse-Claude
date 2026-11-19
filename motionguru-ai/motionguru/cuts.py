"""Approval-based cutting. Nothing is removed until a person says yes.

propose -> <video>.cuts.json (every candidate: silence, filler word, retake) + <video>.review.html (play, toggle, export)
apply   -> keeps everything except the candidates you approved (audio micro-fades, no clicks)
"""
import html, json, os, re, subprocess
import numpy as np
from .util import probe, snap, fmt, encoder_args, run

SR, WIN = 16000, 0.02
FILLERS = {'um', 'umm', 'uh', 'uhh', 'er', 'erm', 'hmm', 'mm', 'ah', 'aah'}


def _audio(src):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def _runs(b):
    d = np.diff(np.concatenate([[0], b.astype(np.int8), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def _speech_mask(a, below=30.0):
    w = int(SR * WIN); n = len(a) // w
    lvl = 20 * np.log10(np.sqrt((a[:n * w].reshape(n, w).astype(np.float64) ** 2).mean(1) + 1e-12))
    loud = lvl > max(np.percentile(lvl, 95) - below, -55.0)
    for s, e in _runs(~loud):
        if (e - s) * WIN < 0.08: loud[s:e] = True       # tiny dips inside a word
    for s, e in _runs(loud):
        if (e - s) * WIN < 0.06: loud[s:e] = False      # isolated clicks
    return loud


def _norm(w):
    return re.sub(r'[^\w]+', '', w.lower())


def _context(words, a, b, pad=4):
    ws = [w['w'] for w in words if a - 2.0 <= w['s'] <= b + 2.0]
    return ' '.join(ws[:pad * 3])


def propose(src, words=None, gap=0.45, keep=0.18, fillers=True, retakes=True, extra_fillers=()):
    """Return a list of cut candidates. `keep` = breath left inside every silence cut."""
    info = probe(src); dur, fps = info['dur'], info['fps']
    cands = []
    if info['audio']:
        loud = _speech_mask(_audio(src))
        for s, e in _runs(~loud):
            ts, te = s * WIN, min(dur, e * WIN)
            if s == 0 or e >= len(loud) - 1:
                a, b = (0.0, max(0.0, te - keep * 0.5)) if s == 0 else (min(dur, ts + keep * 0.5), dur)
                if b - a >= 0.25: cands.append(dict(kind='silence', start=a, end=b, why='dead air at the edge', conf=0.95))
            elif te - ts >= gap:
                a, b = ts + keep * 0.45, te - keep * 0.55
                if b - a >= 0.12:
                    cands.append(dict(kind='silence', start=a, end=b, why=f'{te - ts:.1f}s pause', conf=min(0.99, 0.5 + (te - ts) / 2)))
    if words:
        fl = FILLERS | {x.lower() for x in extra_fillers}
        if fillers:
            for w in words:
                if _norm(w['w']) in fl:
                    cands.append(dict(kind='filler', start=w['s'] - 0.02, end=w['e'] + 0.04, why=f'filler "{w["w"]}"', conf=0.8))
        if retakes:   # same opening words said again within 10 s -> the first attempt is probably a flub
            n, i, used = len(words), 0, -1
            while i < n - 3:
                key = [_norm(x['w']) for x in words[i:i + 3]]
                hit = None
                if all(key) and words[i]['s'] > used:
                    for j in range(i + 3, n - 2):
                        if words[j]['s'] - words[i]['s'] > 10: break
                        if [_norm(x['w']) for x in words[j:j + 3]] == key: hit = j; break
                if hit:
                    cands.append(dict(kind='retake', start=words[i]['s'] - 0.03, end=words[hit]['s'] - 0.03,
                                      why='line said twice: the first take is cut', conf=0.6))
                    used = words[hit]['s']; i = hit
                else:
                    i += 1
    cands.sort(key=lambda c: (c['start'], c['end']))
    merged = []
    for c in cands:                                  # overlapping candidates collapse into one
        if merged and c['start'] < merged[-1]['end'] and c['kind'] != 'retake' and merged[-1]['kind'] != 'retake':
            merged[-1]['end'] = max(merged[-1]['end'], c['end']); merged[-1]['why'] += ' + ' + c['why']
            continue
        merged.append(c)
    out = []
    for k, c in enumerate(merged, 1):
        a, b = max(0.0, snap(c['start'], fps)), min(dur, snap(c['end'], fps))
        if b - a < 1 / fps: continue
        out.append(dict(id=k, kind=c['kind'], start=round(a, 3), end=round(b, 3), len=round(b - a, 2), why=c['why'],
                        conf=round(c['conf'], 2), context=_context(words or [], a, b), decision='cut' if c['conf'] >= 0.75 else 'ask'))
    return out


def save(src, cands):
    p = os.path.splitext(src)[0] + '.cuts.json'
    json.dump(dict(source=os.path.basename(src), candidates=cands), open(p, 'w'), indent=1, ensure_ascii=False)
    return p


def kept_segments(dur, cands, approve):
    """approve: 'all' | 'safe' (decision==cut) | set of ids. Returns the parts to KEEP."""
    if approve == 'all': ids = {c['id'] for c in cands}
    elif approve == 'safe': ids = {c['id'] for c in cands if c['decision'] == 'cut'}
    else: ids = set(approve)
    cuts = sorted((c['start'], c['end']) for c in cands if c['id'] in ids)
    parts, t = [], 0.0
    for a, b in cuts:
        if a > t + 0.04: parts.append((t, a))
        t = max(t, b)
    if dur > t + 0.04: parts.append((t, dur))
    return parts or [(0.0, dur)]


def parse_approve(txt):
    if txt in ('all', 'safe'): return txt
    ids = set()
    for p in txt.split(','):
        if '-' in p: a, b = p.split('-'); ids |= set(range(int(a), int(b) + 1))
        elif p.strip(): ids.add(int(p))
    return ids


def graph(kept, has_audio=True, fade=0.012):
    """filter_complex pieces that cut `kept` out of input 0 and join it: [vcut] [acut]. Micro-fades hide the joins."""
    v, a, n = [], [], len(kept)
    for i, (s, e) in enumerate(kept):
        v.append(f'[0:v]trim=start={s:.4f}:end={e:.4f},setpts=PTS-STARTPTS[v{i}]')
        if has_audio:
            d = min(fade, (e - s) / 3)
            a.append(f'[0:a]atrim=start={s:.4f}:end={e:.4f},asetpts=PTS-STARTPTS,afade=t=in:d={d:.4f},afade=t=out:st={e - s - d:.4f}:d={d:.4f}[a{i}]')
    parts = v + a
    join = ''.join(f'[v{i}]' + (f'[a{i}]' if has_audio else '') for i in range(n))
    parts.append(f'{join}concat=n={n}:v=1:a={1 if has_audio else 0}[vcut]' + ('[acut]' if has_audio else ''))
    return ';\n'.join(parts)


def apply(src, dst, cands, approve='safe', hw='auto'):
    info = probe(src); kept = kept_segments(info['dur'], cands, approve)
    script = os.path.splitext(dst)[0] + '.graph.txt'
    open(script, 'w').write(graph(kept, info['audio']))
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex_script', script, '-map', '[vcut]'] + (['-map', '[acut]'] if info['audio'] else [])
    run(cmd + encoder_args(hw, 14) + ['-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', dst])
    os.remove(script)
    new = sum(e - s for s, e in kept)
    json.dump(dict(source=os.path.basename(src), kept=kept), open(os.path.splitext(dst)[0] + '.cutmap.json', 'w'))
    return kept, info['dur'], new


REVIEW = """<!doctype html><meta charset=utf-8><title>MotionGuru: review cuts</title>
<meta name=viewport content="width=device-width,initial-scale=1"><style>
:root{--bg:#0e0e12;--card:#17171d;--tx:#f4f4f6;--mu:#9a9aa6;--ac:#FFD400;--ok:#35d07f;--no:#ff5a5f}
@media(prefers-color-scheme:light){:root{--bg:#f6f6f8;--card:#fff;--tx:#15151a;--mu:#6a6a76}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.4 system-ui,sans-serif;display:grid;grid-template-columns:minmax(260px,420px) 1fr;gap:20px;padding:20px;max-width:1100px;margin:auto}
@media(max-width:760px){body{grid-template-columns:1fr}}
video{width:100%;border-radius:14px;background:#000;position:sticky;top:20px;max-height:80vh}
h1{font-size:18px;margin:0 0 4px}small,.mu{color:var(--mu)}
.c{background:var(--card);border-radius:12px;padding:12px 14px;margin:10px 0;border:2px solid transparent}
.c.cut{border-color:var(--no)}.c.keep{border-color:var(--ok)}
.r{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.k{font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:2px 8px;border-radius:99px;background:var(--ac);color:#111;font-weight:700}
button{border:0;border-radius:8px;padding:7px 12px;font-weight:600;cursor:pointer;background:#2a2a33;color:#fff}
button.on-cut{background:var(--no)}button.on-keep{background:var(--ok);color:#06210f}button.p{background:var(--ac);color:#111}
.bar{position:sticky;bottom:0;background:var(--bg);padding:12px 0;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
code{background:var(--card);padding:6px 10px;border-radius:8px;display:block;overflow-x:auto;margin-top:8px}
</style>
<div><video id=v controls playsinline src="__VIDEO__"></video></div>
<div><h1>Cut here or not?</h1><small class=mu>__N__ suggestions. Press <b>Play</b> to hear the moment with 1.5 s around it, then choose.</small>
<div id=list></div>
<div class=bar><button class=p id=exp>Copy command</button><button id=allc>Cut all</button><button id=allk>Keep all</button><span class=mu id=sum></span></div>
<code id=cmd></code></div>
<script>
const C=__DATA__,V=document.getElementById('v'),L=document.getElementById('list');let stop=null;
const f=t=>Math.floor(t/60)+':'+(t%60).toFixed(2).padStart(5,'0');
C.forEach(c=>{c.cut=c.decision==='cut';const d=document.createElement('div');c.el=d;
d.innerHTML=`<div class=r><span class=k>${c.kind}</span><b>#${c.id}</b> ${f(c.start)} to ${f(c.end)} <span class=mu>(${c.len}s)</span></div>
<div class=mu>${c.why}${c.context?' · “'+c.context.replace(/</g,'&lt;')+'”':''}</div>
<div class=r style="margin-top:8px"><button data-a=play>Play</button><button data-a=cut>Cut</button><button data-a=keep>Keep</button></div>`;
d.onclick=e=>{const a=e.target.dataset.a;if(!a)return;if(a==='play'){V.currentTime=Math.max(0,c.start-1.5);stop=c.end+1.5;V.play()}if(a==='cut')c.cut=true;if(a==='keep')c.cut=false;draw()};L.append(d)});
V.ontimeupdate=()=>{if(stop&&V.currentTime>=stop){V.pause();stop=null}};
function draw(){let n=0,s=0;C.forEach(c=>{c.el.className='c '+(c.cut?'cut':'keep');const b=c.el.querySelectorAll('button');b[1].className=c.cut?'on-cut':'';b[2].className=c.cut?'':'on-keep';if(c.cut){n++;s+=c.len}});
const ids=C.filter(c=>c.cut).map(c=>c.id).join(',')||'none';document.getElementById('sum').textContent=n+' cuts, '+s.toFixed(1)+'s saved';
document.getElementById('cmd').textContent='motionguru cuts apply "__SRC__" --approve '+ids}
document.getElementById('allc').onclick=()=>{C.forEach(c=>c.cut=true);draw()};document.getElementById('allk').onclick=()=>{C.forEach(c=>c.cut=false);draw()};
document.getElementById('exp').onclick=()=>{navigator.clipboard.writeText(document.getElementById('cmd').textContent);document.getElementById('exp').textContent='Copied'};draw();
</script>"""


def review_page(src, cands):
    p = os.path.splitext(src)[0] + '.review.html'
    slim = [{k: c[k] for k in ('id', 'kind', 'start', 'end', 'len', 'why', 'context', 'decision')} for c in cands]
    page = (REVIEW.replace('__VIDEO__', html.escape(os.path.basename(src))).replace('__N__', str(len(cands)))
            .replace('__DATA__', json.dumps(slim, ensure_ascii=False).replace('</', '<\\/')).replace('__SRC__', os.path.basename(src).replace('"', '')))
    open(p, 'w', encoding='utf-8').write(page)
    return p


def ask_in_terminal(src, cands):
    """y = cut, n = keep, p = play the moment (needs ffplay), a = cut all the rest, q = keep all the rest."""
    import shutil
    ids = set()
    for i, c in enumerate(cands):
        while True:
            r = input(f'#{c["id"]} {fmt(c["start"])}-{fmt(c["end"])} [{c["kind"]}] {c["why"]}  "{c["context"]}"\n   cut? [y/n/p/a/q] ').strip().lower()
            if r == 'p' and shutil.which('ffplay'):
                subprocess.run(['ffplay', '-v', 'error', '-autoexit', '-ss', str(max(0, c['start'] - 1.5)), '-t', str(c['len'] + 3), src])
                continue
            break
        if r == 'a': ids |= {x['id'] for x in cands[i:]}; break
        if r == 'q': break
        if r in ('y', ''): ids.add(c['id'])
    return ids
