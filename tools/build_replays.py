# Cut a short replay video per game from the end of its best trial's 2 fps window recording, keeping only
# frames where the screen changes, and list the trial's last decisions for the log in src/replays.json.
# Usage: python tools/build_replays.py <data_dir> <cache_dir> [slug ...]
import json, os, subprocess, sys, tempfile
from collections import deque
import numpy as np
from PIL import Image
from huggingface_hub import hf_hub_download

DATA, CACHE = sys.argv[1], sys.argv[2]
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO, W, H, FPS, BUDGET, TAIL, LOG = 'Zhuhan/GameCUA', 1280, 720, 8, 320, 2400, 12


def fetch(path):
    return hf_hub_download(REPO, path, repo_type='dataset', local_dir=CACHE)


def recording(video):
    """The recording's last TAIL seconds at 2 fps."""
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-sseof', f'-{TAIL}', '-i', video, '-vf', f'fps=2,scale={W}:{H}',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    while len(buf := p.stdout.read(W * H * 3)) == W * H * 3:
        yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    p.wait()


def screenshots(seg, end):
    """For trials without a usable recording: the before/after screenshots of the last decisions."""
    for k in range(max(1, end - BUDGET // 2), end + 1):
        for side in ('before', 'after'):
            try:
                yield np.asarray(Image.open(fetch(f'{seg}/{k:05d}_{side}.png')).convert('RGB').resize((W, H)))
            except Exception:
                pass


def clip(frames, out):
    """Keep frames that differ from the last kept one and encode the final BUDGET of them
    as AV1 (small) and H.264 (fallback for older Safari)."""
    kept, prev = deque(maxlen=BUDGET), None
    for a in frames:
        s = np.asarray(Image.fromarray(a).convert('L').resize((160, 90)), dtype=np.float32)
        if prev is None or abs(s - prev).mean() > 0.8:
            kept.append(a)
            prev = s
    with tempfile.TemporaryDirectory() as tmp:
        for i, a in enumerate(kept):
            Image.fromarray(a).save(f'{tmp}/{i:04d}.png', compress_level=1)
        src = ['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', f'{tmp}/%04d.png', '-an', '-pix_fmt', 'yuv420p']
        subprocess.run(src + ['-c:v', 'libsvtav1', '-preset', '4', '-crf', '42', '-g', '64',
                              '-movflags', '+faststart', f'{out}.av1.mp4'], check=True)
        subprocess.run(src + ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', '29', '-g', '64',
                              '-movflags', '+faststart', f'{out}.h264.mp4'], check=True)
    return len(kept)


def main():
    replays = json.load(open(f'{DATA}/replays.json'))
    out_path = f'{SITE}/src/replays.json'
    out = json.load(open(out_path)) if os.path.exists(out_path) else {}
    os.makedirs(f'{SITE}/public/video', exist_ok=True)
    for slug in sys.argv[3:] or replays:
        last = replays[slug][-1]['img']
        seg, end = os.path.dirname(last), int(os.path.basename(last)[:5])
        video = fetch(f'{seg}/window.mp4')
        src = recording(video) if os.path.getsize(video) > 1e6 else screenshots(seg, end)
        frames = clip(src, f'{SITE}/public/video/{slug}')
        steps = []
        for k in range(end, 0, -1):
            if len(steps) == LOG:
                break
            try:
                d = json.load(open(fetch(f'{seg}/{k:05d}.json')))
            except Exception:
                continue  # a few decisions have no record (failed requests)
            steps.append({'decision': k, **{f: d['decision'][f] for f in ('observation', 'hypothesis', 'action')}})
        out[slug] = {'seconds': frames / FPS, 'steps': steps[::-1]}
        json.dump(out, open(out_path, 'w'), ensure_ascii=False, separators=(',', ':'))
        print(slug, frames, 'frames', flush=True)


main()
