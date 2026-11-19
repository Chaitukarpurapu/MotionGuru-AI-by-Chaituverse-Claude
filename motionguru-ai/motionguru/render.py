"""One-pass renderer: approved cuts -> camera fx -> overlays -> captions -> sound design -> loudness, a single encode."""
import json, os, subprocess, sys, tempfile
from . import cuts as C, captions as CAP, motion as M, sfx_pro as S, transcribe as T
from . import brand as B
from .util import probe, encoder_args, run, ROOT

MOTION_FX = {'punch', 'shake', 'flash', 'glitch', 'grade', 'vignette', 'grain', 'title', 'lower_third', 'stat', 'watermark'}


ENGINE = os.path.join(ROOT, 'engine', 'scripts')


def _engine_events(fx):
    """Sound events for engine effects, taken from the engine's own table so they land the way the author tuned them."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('engine_sfx', os.path.join(ENGINE, 'sfx.py')); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    ev = []
    for f in fx:
        o = {k: v for k, v in f.items() if k not in ('fx', 'start', 'end')}
        ev += m.events(f['fx'], float(f['start']), float(f.get('end', f['start'] + 1)), o)
    return ev


def render_with_engine(src, dst, plan, eng_fx, hw, width, words_file, lang, approve, still):
    """cuts -> engine pass (face tracking, things behind your head) -> our graphics/captions/sound. Engine adds one extra encode."""
    info = probe(src); tmp = tempfile.mkdtemp(prefix='mguru_eng_'); b = B.load()
    cur, kept = src, [(0.0, info['dur'])]
    if approve is not None:
        cands = json.load(open(os.path.splitext(src)[0] + '.cuts.json'))['candidates']
        cur = os.path.join(tmp, 'cut.mp4'); kept, _, _ = C.apply(src, cur, cands, approve, hw)
    wf = None
    if plan.get('captions'):
        w = T.remap(T.get_words(src, lang or plan.get('lang'), words_file), kept) if approve is not None else T.get_words(src, lang or plan.get('lang'), words_file)
        wf = os.path.join(tmp, 'cut.words.json'); json.dump(w, open(wf, 'w'), ensure_ascii=False)
    json.dump(dict(name=b['name'], handle=b['handle']), open(os.path.join(ROOT, 'engine', 'profile.json'), 'w'))
    pj = os.path.join(tmp, 'engine_plan.json'); json.dump(dict(effects=eng_fx, sfx=False), open(pj, 'w'))
    eng = os.path.join(tmp, 'engine.mp4')
    run([sys.executable, os.path.join(ENGINE, 'fx.py'), '--plan', pj, cur, eng, '--no-sfx', '--width', str(width)])
    rest = dict(plan); rest['effects'] = [f for f in plan['effects'] if f not in eng_fx]; rest['_extra_sfx'] = _engine_events(eng_fx)
    return render(eng, dst, rest, hw, width, wf, lang, None, still, _engine_done=True)


def render(src, dst, plan, hw='auto', width=1080, words_file=None, lang=None, approve=None, still=None, _engine_done=False):
    eng_fx = [f for f in plan.get('effects', []) if f['fx'] not in MOTION_FX and f['fx'] != 'captions']
    if eng_fx and not _engine_done:
        return render_with_engine(src, dst, plan, eng_fx, hw, width, words_file, lang, approve, still)
    info = probe(src); out_dir = os.path.dirname(os.path.abspath(dst))
    cands = None; cp = os.path.splitext(src)[0] + '.cuts.json'
    kept = [(0.0, info['dur'])]
    if approve is not None:
        cands = json.load(open(cp))['candidates']; kept = C.kept_segments(info['dur'], cands, approve)
    new_dur = sum(e - s for s, e in kept)
    # output size: short side = width (1080 default), even numbers
    if info['w'] <= info['h']: W = width; H = int(round(width * info['h'] / info['w'] / 2)) * 2
    else: H = width; W = int(round(width * info['w'] / info['h'] / 2)) * 2
    fx = [dict(f) for f in plan.get('effects', [])]
    cap = plan.get('captions')
    words = None
    if cap or any(f.get('fx') == 'captions' for f in fx):
        words = T.get_words(src, lang or plan.get('lang'), words_file)
        words = T.remap(words, kept) if approve is not None else words
    tmp = tempfile.mkdtemp(prefix='mguru_'); g = M.Graph(W, H, min(info['fps'], 60), new_dur, tmp)
    for f in fx:
        if f['fx'] in MOTION_FX: g.add(f)
    sub = None
    if cap:
        ass = CAP.make_ass(words, W, H, cap.get('style', 'hormozi'), [k for k in str(cap.get('keywords', '')).split('|') if k],
                           cap.get('y', 0.70), cap.get('color'), os.path.join(tmp, 'cap.ass'), cap.get('font'))
        sub = CAP.filter_for(ass)
    head = C.graph(kept, info['audio']) if approve is not None else "[0:v]null[vcut]" + (";[0:a]anull[acut]" if info['audio'] else "")
    scale = f"[vcut]scale={W}:{H}:flags=bicubic,setsar=1[vsc]"
    body, extra = g.build('[vsc]', first_extra=1, sub=sub)
    n_in = 1 + len(extra) // 8                         # each PNG input uses 8 args
    ev = (S.events_for([f for f in fx if f['fx'] in MOTION_FX or f['fx'] == 'hook']) + list(plan.get('_extra_sfx', [])) + [tuple(e) for e in plan.get('sfx_events', [])]) if plan.get('sfx', True) else []
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src] + extra
    sfx_in = None
    if ev:
        sfx_in = os.path.join(tmp, 'sfx.wav'); S.write(sfx_in, S.mix(ev, new_dur, plan.get('sfx_db', -3))); cmd += ['-i', sfx_in]
    music = plan.get('music')
    if music: cmd += ['-stream_loop', '-1', '-i', music]
    idx_sfx = n_in if sfx_in else None; idx_mus = n_in + (1 if sfx_in else 0) if music else None
    a = []
    voice = '[acut]' if info['audio'] else None
    if voice and idx_mus is not None:   # duck the music under the voice
        a.append(f"[{idx_mus}:a]volume={plan.get('music_db', -18)}dB,aresample=48000[mus];[mus]{voice}sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[ducked]")
    labels = [x for x in ([voice] if voice else []) + (['[ducked]'] if idx_mus is not None and voice else []) + ([f'[{idx_sfx}:a]'] if idx_sfx else [])]
    if len(labels) > 1: a.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    elif len(labels) == 1: a.append(f"{labels[0]}loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    full = ';\n'.join([head, scale, body] + a)
    script = os.path.join(tmp, 'graph.txt'); open(script, 'w').write(full)
    cmd += ['-filter_complex_script', script, '-map', '[vout]']
    if still is not None:   # one check frame, no audio
        run(cmd + ['-ss', str(still), '-frames:v', '1', dst]); return dst
    cmd += (['-map', '[aout]'] if labels else [])
    run(cmd + encoder_args(hw, 16) + (['-c:a', 'aac', '-b:a', '192k'] if labels else []) + ['-movflags', '+faststart', dst])
    return dst
