"""End-to-end smoke test on a synthetic clip: propose -> apply -> one-pass edit. Needs ffmpeg."""
import json, os, subprocess, sys, wave
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from motionguru import cuts as C, render as R, transcribe as T, sfx_pro as S
from motionguru.util import probe

pytestmark = pytest.mark.skipif(subprocess.call(['which', 'ffmpeg'], stdout=subprocess.DEVNULL) != 0, reason='ffmpeg missing')


@pytest.fixture(scope='module')
def clip(tmp_path_factory):
    d = tmp_path_factory.mktemp('clip'); sr, dur = 48000, 12; t = np.arange(sr * dur) / sr
    on = (t < 3) | ((t > 4.6) & (t < 9)) | (t > 10)
    y = (np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3.5 * t)) * 0.4 * on)
    w = wave.open(str(d / 'a.wav'), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((y * 32767).astype(np.int16).tobytes()); w.close()
    v = str(d / 'v.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=270x480:rate=30:duration=12', '-i', str(d / 'a.wav'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', v], check=True)
    words = [dict(w=x, s=s, e=s + .3) for x, s in [('hey', .2), ('um', 1.0), ('watch', 1.6), ('this', 2.1), ('now', 5.0), ('AI', 5.6), ('works', 6.2)]]
    json.dump(words, open(str(d / 'v.words.json'), 'w'))
    return v, str(d / 'v.words.json')


def test_propose_finds_silences_and_fillers(clip):
    v, wj = clip
    c = C.propose(v, json.load(open(wj)))
    kinds = {x['kind'] for x in c}
    assert 'silence' in kinds and 'filler' in kinds
    assert all(x['end'] > x['start'] for x in c)


def test_apply_removes_only_approved(clip):
    v, wj = clip; c = C.propose(v, json.load(open(wj))); out = v.replace('.mp4', '_cut.mp4')
    kept, d0, d1 = C.apply(v, out, c, {c[0]['id']}, 'cpu')
    assert d1 < d0 and abs(probe(out)['dur'] - d1) < 0.4


def test_words_remap_drops_cut_words():
    w = [dict(w='a', s=1, e=1.2), dict(w='b', s=5, e=5.2)]
    assert [x['w'] for x in T.remap(w, [(0, 2), (4, 6)])] == ['a', 'b'] and T.remap(w, [(0, 2), (4, 6)])[1]['s'] == 3.0
    assert [x['w'] for x in T.remap(w, [(0, 2)])] == ['a']


def test_full_edit_renders(clip, tmp_path):
    v, wj = clip; c = C.propose(v, json.load(open(wj))); C.save(v, c)
    plan = dict(captions=dict(style='karaoke'), sfx=True, effects=[
        dict(fx='grade', name='cinematic'), dict(fx='lower_third', start=0.3, end=2.5), dict(fx='punch', start=3, end=3.5),
        dict(fx='title', start=4, end=5.5, text='hello'), dict(fx='glitch', start=6, end=6.3), dict(fx='stat', start=7, end=8.5, value='3X', label='faster')])
    out = str(tmp_path / 'o.mp4'); R.render(v, out, plan, 'cpu', 270, wj, None, 'safe')
    assert probe(out)['dur'] > 5


def test_every_synth_sound_is_audible():
    for n in S.SYNTH: assert np.abs(S.sound(n)).max() > 0.1, n


def test_engine_effect_in_same_plan(clip, tmp_path):
    """Needs opencv + mediapipe (optional extras). Uses the person cut-out, so skip when they are missing."""
    pytest.importorskip('mediapipe'); pytest.importorskip('cv2')
    v, wj = clip
    plan = dict(sfx=True, effects=[dict(fx='backdrop-word', start=0.5, end=2.0, text='HI'), dict(fx='punch', start=2.5, end=3.0)])
    out = str(tmp_path / 'e.mp4'); R.render(v, out, plan, 'cpu', 270, wj, None, None)
    assert probe(out)['dur'] > 5


def test_styles_place_effects_sensibly():
    from motionguru import styles as ST
    words = [dict(w=x, s=i * 0.6, e=i * 0.6 + 0.4) for i, x in enumerate('hey this AI tool edits videos in 10 minutes and it is free for everyone today really'.split())]
    for name in ST.list_styles():
        p = ST.build_plan(name, words, 9.0, ['AI', 'free', 'videos'], engine=False)
        timed = [e for e in p['effects'] if 'start' in e]
        assert timed and all(0 <= e['start'] < e['end'] <= 9.0 + 1e-6 for e in timed), name
        emph = sorted(e['start'] for e in timed if e['fx'] in ('punch', 'shake'))
        assert all(b - a >= 3.0 for a, b in zip(emph, emph[1:])), name
        assert not any(e['fx'] in ('backdrop-word', 'spotlight') for e in p['effects']), name   # engine=False must not use the engine
