#!/usr/bin/env python3
"""
Generate one indexable page per story entry from _data/stories.csv.

The AMP story is a single URL, so all 52 entries share one title, one
description and one canonical. These pages give each entry its own.
Run after editing the spreadsheet; wired into `npm run generate_pages`.
"""
import csv, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, 'work')
CSV  = os.path.join(ROOT, '_data', 'stories.csv')

# Accurate, non-inventive phrasing per category. Anything unlisted falls back
# to the category name itself, so a new category never breaks the build.
PHRASE = {
    'ARTICLE': 'Press coverage', 'SPEAKER': 'Speaking engagement', 'WORK': 'Work',
    'INTERVIEW': 'Interview', 'AWARD': 'Award', 'PANELIST': 'Panel',
    'JUDGE': 'Judging', 'AI TEST': 'AI experiment', 'CERTIFICATION': 'Certification',
    'BOOK': 'Book', 'VIDEO': 'Video', 'QUOTE': 'Quote', 'GAME': 'Game',
    'PODCAST': 'Podcast',
}
MONTHS = {m.lower(): i for i, m in enumerate(
    ['January','February','March','April','May','June','July',
     'August','September','October','November','December'], 1)}
MONTHS.update({m[:3].lower(): i for m, i in list(MONTHS.items())})

def blank(v):
    return not v or v.strip() in ('', 'N/A')

def iso_date(label):
    """'June 2026' -> '2026-06-01'. Returns '' when unparseable."""
    if blank(label):
        return ''
    m = re.match(r'^\s*([A-Za-z]+)\s+(\d{4})\s*$', label)
    if not m:
        return ''
    mon = MONTHS.get(m.group(1).lower())
    return f"{m.group(2)}-{mon:02d}-01" if mon else ''

def yaml_str(v):
    """Double-quoted YAML scalar - safe for apostrophes, colons, quotes."""
    return '"' + str(v).replace('\\', '\\\\').replace('"', '\\"') + '"'

def build_summary(title, category, date_label):
    phrase = PHRASE.get((category or '').upper(), (category or 'Work').title())
    tail = f"{phrase} by Juan (John) Tubert, CTO at Tombras"
    if not blank(date_label):
        tail += f", {date_label.strip()}"
    s = f"{title.strip()} — {tail}."
    return s if len(s) <= 158 else s[:155].rstrip(' ,—-') + '…'

def main():
    rows = [r for r in csv.DictReader(open(CSV, encoding='utf-8')) if r.get('id')]
    os.makedirs(OUT, exist_ok=True)
    # Clear only previously generated entry pages - a stale entry must not
    # linger as a live URL - while leaving hand-written files (index.html) alone.
    for f in os.listdir(OUT):
        path = os.path.join(OUT, f)
        if f == 'index.html' or not f.endswith('.html'):
            continue
        with open(path, encoding='utf-8') as fh:
            head = fh.read(400)
        if 'layout: "entry"' in head:
            os.remove(path)

    # resolve the eligible set up front: prev/next need to know the neighbours,
    # so a visitor landing on any entry from search can walk the whole collection
    eligible, skipped = [], []
    for r in rows:
        eid = (r.get('id') or '').strip()
        if eid == 'homepage':       # that's the story cover, not an entry
            continue
        if blank(r.get('title')):
            skipped.append((eid, 'no title'))
            continue
        eligible.append(r)

    written = 0
    for idx, r in enumerate(eligible):
        eid = r['id'].strip()
        title = r['title'].strip()
        prev_r = eligible[idx-1] if idx > 0 else None
        next_r = eligible[idx+1] if idx < len(eligible)-1 else None

        asset = (r.get('asset') or '').strip()
        has_asset = not blank(asset) and os.path.exists(os.path.join(ROOT, asset))
        poster = (r.get('poster') or '').strip()
        mtype = (r.get('type') or 'image').strip()
        link = (r.get('link') or '').strip()
        cat = (r.get('category') or 'Work').strip()
        date_label = (r.get('date') or '').strip()

        # og:image: the entry's own art where it has some, else the story poster
        if has_asset and mtype == 'image':
            image = asset
        elif not blank(poster) and os.path.exists(os.path.join(ROOT, poster)):
            image = poster
        else:
            image = 'assets/story-poster-landscape.jpg'

        fm = {
            'layout': 'entry',
            'permalink': f'/work/{eid}/',
            'entry_id': eid,
            'title': title,
            'category': cat,
            'date_label': date_label,
            'iso_date': iso_date(date_label),
            'link': '' if blank(link) else link,
            'asset': asset if has_asset else '',
            'poster': '' if blank(poster) else poster,
            'image': image,
            'media_type': mtype,
            'cta_label': 'Watch the video' if mtype == 'video' else 'Read more',
            'summary': build_summary(title, cat, date_label),
            'sitemap_lastmod': iso_date(date_label),
            'prev_id': prev_r['id'].strip() if prev_r else '',
            'prev_title': prev_r['title'].strip() if prev_r else '',
            'next_id': next_r['id'].strip() if next_r else '',
            'next_title': next_r['title'].strip() if next_r else '',
            'position': idx + 1,
            'total': len(eligible),
        }
        body = '---\n' + ''.join(f'{k}: {yaml_str(v)}\n' for k, v in fm.items()) + '---\n'
        with open(os.path.join(OUT, f'{eid}.html'), 'w', encoding='utf-8') as fh:
            fh.write(body)
        written += 1

    print(f"generated {written} entry pages in work/")
    for eid, why in skipped:
        print(f"  skipped {eid}: {why}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
