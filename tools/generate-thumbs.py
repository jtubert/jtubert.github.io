#!/usr/bin/env python3
"""
Small square thumbnails for the cards that lead /work/.

Only the featured entries need one - the rest of the index is a text list -
so this generates from _data/featured.json, which the page generator writes.

Images are centre-cropped; videos use their poster, or a frame pulled with
ffmpeg when there is no poster. Skips work already done, so re-running is
cheap - only new or changed assets are processed.
"""
import csv, glob, json, os, shutil, subprocess, sys

# `python3` resolves to a different interpreter depending on which shell runs
# this - homebrew's has no Pillow, miniforge's does. Rather than pin a path in
# package.json, find one that works and hand off to it.
try:
    from PIL import Image, ImageStat
except ModuleNotFoundError:
    if os.environ.get('_THUMBS_REEXEC'):
        sys.exit('thumbs: no python3 with Pillow found. pip install Pillow')
    for cand in ('/opt/homebrew/Caskroom/miniforge/base/bin/python3',
                 '/usr/local/bin/python3', '/opt/homebrew/bin/python3',
                 '/usr/bin/python3', shutil.which('python3')):
        if not cand or not os.path.exists(cand):
            continue
        if subprocess.run([cand, '-c', 'import PIL'], capture_output=True).returncode == 0:
            os.environ['_THUMBS_REEXEC'] = '1'
            os.execv(cand, [cand] + sys.argv)
    sys.exit('thumbs: no python3 with Pillow found. pip install Pillow')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, 'assets', 'thumbs')
SIZE = 288           # 90px of picture inside the border; 288 covers a 3x screen
MAX_BYTES = 24000
HAND = os.path.join(ROOT, 'assets', 'thumbs-src')   # hand-made art wins


def detail(im):
    """Spatial variation per channel. A blank or single-colour frame scores
    near zero; note that a solid cyan scores HIGH if you measure across
    channels instead, which is how the first pass shipped a blank tile."""
    sd = ImageStat.Stat(im.convert('RGB')).stddev
    return sum(sd) / len(sd)

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
    fp = os.path.join(ROOT, '_data', 'featured.json')
    if not os.path.exists(fp):
        print('thumbs: no _data/featured.json - run generate-entry-pages.py first')
        return 1
    want = {i['id'] for i in json.load(open(fp, encoding='utf-8'))['items']}
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, '_data/stories.csv'), encoding='utf-8'))
            if (r.get('id') or '').strip() in want]
    # Entries demoted out of the featured set shouldn't leave art behind.
    for f in os.listdir(OUT):
        if f.endswith('.jpg') and f[:-4] not in want:
            os.remove(os.path.join(OUT, f))
    # Which source produced each file, so that swapping art - or deleting an
    # override so the derived frame comes back - actually invalidates it.
    mpath = os.path.join(OUT, 'sources.json')
    try:
        manifest = json.load(open(mpath, encoding='utf-8'))
    except Exception:
        manifest = {}
    made = skipped = nothing = 0
    for r in rows:
        eid = r['id'].strip()
        dst = os.path.join(OUT, f'{eid}.jpg')
        asset, poster = clean(r.get('asset')), clean(r.get('poster'))
        src = None
        # A file dropped in assets/thumbs-src/ beats anything derived from the
        # sheet: art composed for a 90px square always reads better than a
        # crop out of a video frame or a title card.
        for ext in ('.png', '.jpg', '.jpeg', '.webp'):
            cand = os.path.join('assets', 'thumbs-src', eid + ext)
            if os.path.exists(os.path.join(ROOT, cand)):
                src = cand
                break
        if src:
            pass
        elif r.get('type') == 'image' and exists(asset):
            src = asset
        elif exists(poster):
            src = poster
        elif exists(asset):
            src = asset                       # a video with no poster
        if not src:
            nothing += 1
            continue
        srcp = os.path.join(ROOT, src)
        stamp = [src, int(os.path.getmtime(srcp)), SIZE]
        if os.path.exists(dst) and manifest.get(eid) == stamp \
           and Image.open(dst).size == (SIZE, SIZE):
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
            if not src.startswith('assets/thumbs-src') and \
               detail(Image.open(dst)) < 20 and exists(asset) and \
               asset.lower().endswith(('.mp4', '.mov', '.webm')):
                frame = best_frame(os.path.join(ROOT, asset), eid)
                if frame and detail(Image.open(frame)) > detail(Image.open(dst)):
                    square(Image.open(frame).convert('RGB'), dst)
                for t in glob.glob(os.path.join(OUT, f'_{eid}_*.png')):
                    os.remove(t)
            manifest[eid] = stamp
            made += 1
        except Exception as e:
            print(f'  {eid}: {e.__class__.__name__} on {src}')
            nothing += 1
    json.dump({k: v for k, v in manifest.items() if k in want}, open(mpath, 'w'), indent=1)
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith('.jpg'))
    print(f'thumbs: {made} generated, {skipped} already current, {nothing} without art')
    print(f'  {len([f for f in os.listdir(OUT) if f.endswith(".jpg")])} files, {total//1024} KB total')
    return 0

if __name__ == '__main__':
    sys.exit(main())
