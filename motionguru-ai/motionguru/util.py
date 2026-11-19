import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, 'engine', 'fonts')


def need(tool):
    if not shutil.which(tool):
        sys.exit(f'{tool} is not installed. Mac: brew install ffmpeg | Windows: winget install ffmpeg | Linux: apt install ffmpeg')


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    """-> dict(fps, dur, w, h, audio)"""
    need('ffprobe')
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                   'stream=codec_type,r_frame_rate,width,height:format=duration', '-of', 'json', path],
                   capture_output=True, text=True, check=True).stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video')
    n, d = v['r_frame_rate'].split('/')
    return dict(fps=float(n) / float(d or 1), dur=float(j['format']['duration']), w=int(v['width']), h=int(v['height']),
                audio=any(s['codec_type'] == 'audio' for s in j['streams']))


_hw_ok = {}


def _works(enc):
    """ffmpeg lists encoders even when the GPU/driver is missing, so try a 1-frame encode before trusting one."""
    if enc not in _hw_ok:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1', '-frames:v', '1',
                            '-c:v', enc, '-f', 'null', '-'], capture_output=True)
        _hw_ok[enc] = r.returncode == 0
    return _hw_ok[enc]


def encoder_args(hw='auto', crf=16):
    """Hardware H.264 when it really works (much faster), else libx264."""
    if hw == 'auto':
        hw = next((k for k, enc in (('nvenc', 'h264_nvenc'), ('videotoolbox', 'h264_videotoolbox')) if _works(enc)), 'cpu')
    if hw == 'nvenc':
        return ['-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', str(crf + 3), '-b:v', '0', '-pix_fmt', 'yuv420p']
    if hw == 'videotoolbox':
        return ['-c:v', 'h264_videotoolbox', '-q:v', '65', '-pix_fmt', 'yuv420p']
    return ['-c:v', 'libx264', '-crf', str(crf), '-preset', 'medium', '-pix_fmt', 'yuv420p']


def snap(t, fps):
    return round(t * fps) / fps


def fmt(t):
    m, s = divmod(max(0.0, t), 60)
    return f'{int(m)}:{s:05.2f}'
