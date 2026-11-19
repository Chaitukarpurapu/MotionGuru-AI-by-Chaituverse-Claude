"""motionguru: cuts propose|apply | captions | edit | sfx-list | brand | engine"""
import argparse, json, os, subprocess, sys
from . import __version__, brand as B, cuts as C, captions as CAP, render as R, transcribe as T, sfx_pro as S
from .util import probe, ROOT, need, fmt


def cmd_cuts(a):
    need('ffmpeg')
    if a.action == 'propose':
        words = None
        if not a.no_words:
            try: words = T.get_words(a.video, a.lang, a.words)
            except SystemExit as e: print('  (no transcript, silence-only suggestions)\n ', e)
        cands = C.propose(a.video, words, gap=a.gap, extra_fillers=a.filler or ())
        p = C.save(a.video, cands); html = C.review_page(a.video, cands)
        tot = sum(c['len'] for c in cands)
        print(f'{len(cands)} suggestions ({tot:.1f}s). Nothing has been cut.\n')
        for c in cands: print(f"  #{c['id']:<3} {fmt(c['start'])}-{fmt(c['end'])} {c['len']:>5.2f}s  [{c['kind']:<7}] {c['decision']:<4} {c['why']}  {c['context']}")
        print(f'\nReview in your browser: {html}\nThen: motionguru cuts apply "{a.video}" --approve 1,2,5   (or all | safe)'); return
    cands = json.load(open(os.path.splitext(a.video)[0] + '.cuts.json'))['candidates']
    ap = C.ask_in_terminal(a.video, cands) if a.approve == 'ask' else C.parse_approve(a.approve)
    dst = a.out or os.path.splitext(a.video)[0] + '_cut.mp4'
    kept, d0, d1 = C.apply(a.video, dst, cands, ap, a.hw)
    print(f'{d0:.1f}s -> {d1:.1f}s ({d0 - d1:.1f}s removed, {len(kept)} parts). Saved {dst}')


def cmd_edit(a):
    need('ffmpeg')
    plan = json.load(open(a.plan))
    ap = C.parse_approve(a.approve) if a.approve else None
    dst = a.out or os.path.splitext(a.video)[0] + '_motionguru.mp4'
    if a.still is not None: dst = a.out or os.path.splitext(a.video)[0] + f'_check_{a.still}.png'
    R.render(a.video, dst, plan, a.hw, a.width, a.words, a.lang, ap, a.still); print('Done:', dst)


def cmd_captions(a):
    need('ffmpeg'); info = probe(a.video)
    plan = dict(captions=dict(style=a.style, keywords=a.keywords or '', y=a.y), effects=[], sfx=False)
    dst = a.out or os.path.splitext(a.video)[0] + f'_{a.style}.mp4'
    R.render(a.video, dst, plan, a.hw, a.width, a.words, a.lang); print('Done:', dst)


def cmd_brand(a):
    b = B.save(name=a.name, handle=a.handle, accent=a.accent, avatar=a.avatar)
    print(json.dumps({k: v for k, v in b.items() if k != 'avatar_path'}, indent=1))


def cmd_engine(a):
    """Run the vendored 55-effect face-tracking engine (upstream) for things like orbit, spotlight, logo-link."""
    fx = os.path.join(ROOT, 'engine', 'scripts', 'fx.py')
    sys.exit(subprocess.call([sys.executable, fx] + a.rest))


def cmd_sfx(a):
    for n in S.SYNTH: print(f'{n:12s} {len(S.sound(n)) / S.SR:.2f}s')
    print('\nPremium packs: put licensed files in sfx_pack/ named like whoosh_01.wav, riser_02.mp3, impact.wav')


def main(argv=None):
    p = argparse.ArgumentParser(prog='motionguru', description=__doc__); p.add_argument('--version', action='version', version=__version__)
    sp = p.add_subparsers(dest='cmd', required=True)
    c = sp.add_parser('cuts', help='suggest cuts, review them, apply only the approved ones'); c.add_argument('action', choices=['propose', 'apply']); c.add_argument('video')
    c.add_argument('--approve', default='safe', help='ids like 1,3-5 | all | safe | ask (answer in the terminal)'); c.add_argument('--gap', type=float, default=0.45)
    c.add_argument('--filler', action='append', help='extra filler word to flag (repeatable)'); c.add_argument('--no-words', action='store_true')
    c.set_defaults(f=cmd_cuts)
    e = sp.add_parser('edit', help='render a plan: cuts + motion graphics + captions + sound in one pass'); e.add_argument('video'); e.add_argument('--plan', required=True)
    e.add_argument('--approve', help='apply approved cuts first (ids | all | safe)'); e.add_argument('--still', type=float, help='save one check frame at this second'); e.set_defaults(f=cmd_edit)
    k = sp.add_parser('captions', help='captions only'); k.add_argument('video'); k.add_argument('--style', default='hormozi', choices=list(CAP.STYLES))
    k.add_argument('--keywords'); k.add_argument('--y', type=float, default=0.70); k.set_defaults(f=cmd_captions)
    b = sp.add_parser('brand', help='set your name, handle, colour and face avatar'); b.add_argument('--name'); b.add_argument('--handle'); b.add_argument('--accent'); b.add_argument('--avatar'); b.set_defaults(f=cmd_brand)
    s = sp.add_parser('sfx', help='list sound effects'); s.set_defaults(f=cmd_sfx)
    g = sp.add_parser('engine', help='55 face-tracking effects (upstream engine)'); g.add_argument('rest', nargs=argparse.REMAINDER); g.set_defaults(f=cmd_engine)
    for x in (c, e, k):
        x.add_argument('--out'); x.add_argument('--words'); x.add_argument('--lang', help='en, hi, te, ta ...'); x.add_argument('--hw', default='auto', choices=['auto', 'cpu', 'nvenc', 'videotoolbox'])
    for x in (e, k): x.add_argument('--width', type=int, default=1080, help='short side: 1080 (default) or 2160')
    a = p.parse_args(argv); a.f(a)


if __name__ == '__main__':
    main()
