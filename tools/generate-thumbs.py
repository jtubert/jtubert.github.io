#!/usr/bin/env python3
"""
Square thumbnails for the /work/ grid, one per entry.

Images are centre-cropped; videos use their poster, or a frame pulled with
ffmpeg when there is no poster. Skips work already done, so re-running is
cheap - only new or changed assets are processed.
"""
import csv, glob, os, subprocess, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, 'assets', 'thumbs')
SIZE = 360           # displayed ~244px in a 3-col grid; 360 covers ~1.5x
MAX_BYTES = 26000


def detail(im):
    """Spatial variation per channel. A blank or single-colour frame scores
    near zero; note that a solid cyan scores HIGH if you measure across
    channels instead, which is how the first pass shipped a blank tile."""
    a = np.asarray(im.convert('RGB')).astype(float)
    return float(np.mean([a[:, :, c].std() for c in range(3)]))

def best_frame(srcp, eid):
    """Sample across the clip and keep the frame with the most detail.
    Grabbing a fixed timestamp lands on title cards and fades."""
    dur = 0.0
    try:
        dur = float(subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', srcp], capture_output=True, text=True).stdout.strip())
    except Exception:
        pass
    marks = [dur * f for f in (0.15, 0.35, 0.55, 0.75)] if dur > 2 else [1.0]
    best, best_score = None, -1.0
    for i, t in enumerate(marks):
        tmp = os.path.join(OUT, f'_{eid}_{i}.png')
        try:
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{t:.2f}',
                            '-i', srcp, '-frames:v', '1', tmp], check=True)
            score = detail(Image.open(tmp))
        except Exception:
            continue
        if score > best_score:
            best, best_score = tmp, score
    return best

def clean(p):
    return (p or '').split('?')[0].split('#')[0].strip()

def exists(p):
    return p and p != 'N/A' and os.path.exists(os.path.join(ROOT, p))

def square(im, dst):
    """Crop biased above centre. Screenshots put their headline at the top and
    photographs put faces there, so a true centre crop slices through both."""
    w, h = im.size
    s = min(w, h)
    top = int((h - s) * 0.18)
    im = im.crop(((w - s) // 2, top, (w - s) // 2 + s, top + s))
    im = im.resize((SIZE, SIZE), Image.LANCZOS)
    for q in range(78, 25, -6):
        im.save(dst, 'JPEG', quality=q, optimize=True, progressive=True)
        if os.path.getsize(dst) < MAX_BYTES:
            break

def main():
    os.makedirs(OUT, exist_ok=True)
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, '_data/stories.csv'), encoding='utf-8'))
            if r.get('id') and r['id'] != 'homepage' and (r.get('title') or '') not in ('', 'N/A')]
    made = skipped = nothing = 0
    for r in rows:
        eid = r['id'].strip()
        dst = os.path.join(OUT, f'{eid}.jpg')
        asset, poster = clean(r.get('asset')), clean(r.get('poster'))
        src = None
        if r.get('type') == 'image' and exists(asset):
            src = asset
        elif exists(poster):
            src = poster
        elif exists(asset):
            src = asset                       # a video with no poster
        if not src:
            nothing += 1
            continue
        srcp = os.path.join(ROOT, src)
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(srcp):
            skipped += 1
            continue
        try:
            if src.lower().endswith(('.mp4', '.mov', '.webm')):
                square(Image.open(best_frame(srcp, eid)).convert('RGB'), dst)
                for t in glob.glob(os.path.join(OUT, f'_{eid}_*.png')):
                    os.remove(t)
            else:
                square(Image.open(srcp).convert('RGB'), dst)
            # A poster is preferred, but some posters are a title card or a
            # fade. If the result carries almost no detail and there is a video
            # behind it, pull a real frame instead.
            if detail(Image.open(dst)) < 20 and exists(asset) and \
               asset.lower().endswith(('.mp4', '.mov', '.webm')):
                frame = best_frame(os.path.join(ROOT, asset), eid)
                if frame and detail(Image.open(frame)) > detail(Image.open(dst)):
                    square(Image.open(frame).convert('RGB'), dst)
                for t in glob.glob(os.path.join(OUT, f'_{eid}_*.png')):
                    os.remove(t)
            made += 1
        except Exception as e:
            print(f'  {eid}: {e.__class__.__name__} on {src}')
            nothing += 1
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith('.jpg'))
    print(f'thumbs: {made} generated, {skipped} already current, {nothing} without art')
    print(f'  {len([f for f in os.listdir(OUT) if f.endswith(".jpg")])} files, {total//1024} KB total')
    return 0

if __name__ == '__main__':
    sys.exit(main())
