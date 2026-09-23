#!/usr/bin/env python3
"""
Generate one indexable page per story entry from _data/stories.csv.

The AMP story is a single URL, so all 52 entries share one title, one
description and one canonical. These pages give each entry its own.
Run after editing the spreadsheet; wired into `npm run generate_pages`.
"""
import csv, datetime, json, os, re, subprocess, sys

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

def git_date(*paths):
    """When a set of files last changed, from git, as an ISO 8601 datetime at the
    start of that day in the commit's own timezone: 2026-09-16T00:00:00-04:00.

    A full datetime because Google's Profile page markup rejects a bare date in
    dateModified ("Invalid datetime value"); it was YYYY-MM-DD until September
    2026. Pinned to the start of the day rather than the exact commit time so the
    value stays stable: an uncommitted change has to be dated before its commit
    exists, and an exact time would then change once more on the next run after
    committing, churning every generated page and resubmitting it to IndexNow.

    Feeds "Page updated", dateModified and the sitemap's lastmod. It used to be
    the build clock, which stamped every URL as modified on every deploy; Google
    learns to ignore a lastmod that always says now, and answer engines weight
    recency, so the date has to mean something. A path with uncommitted changes
    counts as today, because that change is about to ship.
    """
    rel = [os.path.relpath(x, ROOT) for x in paths if os.path.exists(x)]
    if not rel:
        return ''
    def git(*args):
        return subprocess.run(['git', *args, '--', *rel], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
    def day_start(dt):
        return dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    try:
        if git('status', '--porcelain'):
            return day_start(datetime.datetime.now().astimezone())
        stamp = git('log', '-1', '--format=%cI')
        # git writes a UTC commit as ...Z, which fromisoformat only accepts
        # from Python 3.11; older ones raise, and the except below would then
        # silently drop the date
        if stamp.endswith('Z'):
            stamp = stamp[:-1] + '+00:00'
        if not stamp:
            # a file that exists but has no commit and no uncommitted change:
            # not in a git repository, or ignored. Say so rather than dropping
            # the date without a word.
            print(f"  warning: git has no date for {', '.join(rel)}; that page gets no last-modified date")
            return ''
        return day_start(datetime.datetime.fromisoformat(stamp))
    except Exception as e:
        # never invent a date: the page omits one, but not silently
        print(f"  warning: could not read the git date for {', '.join(rel)} ({e}); "
              f"that page gets no last-modified date")
        return ''

def write_lastmod(entries):
    """Dates for the pages the generator does not write itself."""
    j = lambda *p: os.path.join(ROOT, *p)
    data = {
        'home':  git_date(CSV, j('index.markdown'), j('_includes', 'templates')),
        'work':  git_date(CSV, j('work', 'index.html'), j('_data', 'selected.yml')),
        'about': git_date(j('about', 'index.html'), j('_data', 'about.yml'), j('_data', 'person.yml')),
        'entries': entries,
    }
    with open(j('_data', 'lastmod.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    return data

TITLE_LIMIT = 65
TITLE_SUFFIXES = (' — Juan (John) Tubert', ' — Juan Tubert', '')


def load_short_titles():
    path = os.path.join(ROOT, '_data', 'titles.json')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith('_')}


def seo_title(eid, title):
    """The <title> text: the longest form that fits TITLE_LIMIT.

    Bing Site Scan flagged 22 pages for "Title too long", exactly the ones over 71
    characters, and the cause was mostly the 21-character " — Juan (John) Tubert"
    added to every post. So each post gets the fullest name suffix that fits, and
    a post too long even without one uses its hand-written short form from
    _data/titles.json. The h1, og:title and structured data keep the full title."""
    short = SHORT_TITLES.get(eid)
    base = title
    if short:
        if not isinstance(short, dict) or not isinstance(short.get('short'), str) or not short['short'].strip():
            # a hand-edited entry missing "short" used to crash the whole build
            print(f"  warning: _data/titles.json entry for {eid} has no usable \"short\"; ignoring it")
        elif short.get('for') == title:
            base = short['short']
        else:
            print(f"  warning: _data/titles.json has a short title for {eid} written for a different "
                  f"sheet title; ignoring it until it is updated")
    for suffix in TITLE_SUFFIXES:
        if len(base + suffix) <= TITLE_LIMIT:
            return base + suffix
    cut = base[:TITLE_LIMIT - 1].rsplit(' ', 1)[0].rstrip(' ,:;')
    print(f"  warning: title for {eid} is {len(base)} characters with no short form in "
          f"_data/titles.json; truncated to {cut}…")
    return cut + '…'


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






BODIES = os.path.join(ROOT, '_work_bodies')


def has_audio(path):
    """Whether a clip actually carries sound. The pages autoplay muted, so they
    tell the reader to unmute - but only where there is something to hear.
    Four of the clips are silent screen recordings."""
    full = os.path.join(ROOT, path.split('?')[0])
    if not os.path.exists(full):
        return False
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'a',
             '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', full],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return bool(out)
    except Exception:
        # no ffprobe on this machine: stay silent rather than promise sound
        return False


def load_pairs(filename, default_label):
    """id: <url> | <optional caption>, one per line. Used by media_links.yml
    and audio.yml, both repo-side so a sheet download cannot clear them."""
    path = os.path.join(ROOT, '_data', filename)
    out = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            m = re.match(r'^\s*([A-Za-z0-9_-]+)\s*:\s*(\S+)\s*(?:\|\s*(.+?)\s*)?$', line)
            if m:
                out[m.group(1)] = (m.group(2), m.group(3) or default_label)
    return out


def load_media_links():
    """Entries whose hero image opens a PDF of the original article."""
    return load_pairs('media_links.yml', 'Read the original article as a PDF')


def load_audio():
    """Entries with an episode to play on the page."""
    return load_pairs('audio.yml', 'Listen to the full episode')


def load_selected():
    """The ids that lead /work/, from _data/selected.yml. A repo-side file, so
    it survives `npm run download` overwriting the sheet."""
    path = os.path.join(ROOT, '_data', 'selected.yml')
    ids = re.findall(r'^\s*-\s*["\']?([A-Za-z0-9_-]+)["\']?\s*$',
                     open(path, encoding='utf-8').read(), re.M)
    return ids


def write_nav(eligible, year_of):
    """Everything the in-page navigation drawer lists: all entries grouped by
    year, newest first, with the month for each. Written as JSON so the layout
    can loop it without recomputing the year carry-forward in Liquid."""
    groups = []
    for r in eligible:
        eid = r['id'].strip()
        yr = year_of.get(eid, 'Undated')
        month = (r.get('date') or '').strip().split(' ')[0][:3]
        if not groups or groups[-1]['year'] != yr:
            groups.append({'year': yr, 'count': 0, 'items': []})
        groups[-1]['count'] += 1
        groups[-1]['items'].append({
            'id': eid,
            'title': strip_tags(r.get('title') or ''),
            'month': month,
        })
    with open(os.path.join(ROOT, '_data', 'nav.json'), 'w', encoding='utf-8') as f:
        json.dump({'years': groups, 'total': len(eligible)},
                  f, ensure_ascii=False, indent=1)
    return groups


def write_featured(items):
    """Emitted as JSON, which Jekyll reads as data the same as YAML, so titles
    and blurbs carrying quotes need no escaping dance."""
    with open(os.path.join(ROOT, '_data', 'featured.json'), 'w', encoding='utf-8') as f:
        json.dump({'items': items}, f, ensure_ascii=False, indent=2)
    stale = os.path.join(ROOT, '_data', 'featured.yml')
    if os.path.exists(stale):
        os.remove(stale)
    return [i['id'] for i in items]


def write_year_index(eligible, featured):
    """Year label per entry plus a count per year, written for the /work/ index.

    Doing it here rather than in Liquid because one entry has no date and has
    to inherit the year of the entry above it - and a heading whose count
    disagrees with the rows beneath it is worse than no count at all.
    """
    order, counts, label = [], {}, {}
    current = ''
    for r in eligible:
        eid = r['id'].strip()
        skip = eid in featured
        date = (r.get('date') or '').strip()
        yr = date.split()[-1] if date and date.split()[-1].isdigit() else ''
        if yr:
            current = yr
        year = current or 'Undated'
        label[eid] = year
        if skip:
            continue
        if year not in counts:
            counts[year] = 0
            order.append(year)
        counts[year] += 1
    out = os.path.join(ROOT, '_data', 'years.yml')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# Generated by tools/generate-entry-pages.py - do not edit.\n')
        f.write('# Year each entry belongs to, and how many fall in each year.\n')
        f.write('order:\n')
        for y in order:
            f.write(f'  - "{y}"\n')
        f.write('counts:\n')
        for y in order:
            f.write(f'  "{y}": {counts[y]}\n')
        f.write('entry:\n')
        for eid, y in label.items():
            f.write(f'  "{eid}": "{y}"\n')
    return order, counts, label

def load_body(eid):
    """Long-form page content, if written. Markdown, one file per entry.
    Lives in the repo rather than the sheet: 150-300 words does not belong
    in a spreadsheet cell, and `npm run download` would overwrite it."""
    path = os.path.join(BODIES, eid + '.md')
    if not os.path.exists(path):
        return ''
    return open(path, encoding='utf-8').read().strip()

def strip_tags(text):
    """Titles occasionally carry markup (a <br> used for the story layout).
    It renders as a line break in the H1 but leaks literally into <title>
    and og:title, so metadata gets a plain-text version."""
    return ' '.join(re.sub(r'<[^>]+>', ' ', text or '').split())

def on_disk(path):
    """Asset paths may carry a cache-busting query (assets/x.gif?v=1); the
    file on disk has no query, so strip it before testing existence."""
    if not path or path.strip() in ('', 'N/A'):
        return False
    return os.path.exists(os.path.join(ROOT, path.split('?', 1)[0].split('#', 1)[0]))

VIDEO_HOSTS = ('youtube.com', 'youtu.be', 'vimeo.com', 'instagram.com')

# A broadcaster's own page for a segment. The piece there is watched, not read,
# so the category's usual "Read the ..." verb is wrong however the sheet
# classifies it. Kept apart from VIDEO_HOSTS, which are video sites outright.
BROADCAST_HOSTS = ('telemundo47.com',)

# Proper brand names per host, with the preposition that reads correctly:
# "in" for publications, "on" for platforms.
OUTLETS = {
    'adage.com':                ('Ad Age', 'in'),
    'adweek.com':               ('Adweek', 'in'),
    'campaignlive.com':         ('Campaign', 'in'),
    'forbes.com':               ('Forbes', 'in'),
    'adlatina.com':             ('Adlatina', 'in'),
    'latinspots.com':           ('Latinspots', 'in'),
    'commarts.com':             ('Communication Arts', 'in'),
    'cioapplications.com':      ('CIO Applications', 'in'),
    'musebyclios.com':          ('Muse by Clios', 'in'),
    'dailydooh.com':            ('DailyDOOH', 'in'),
    'afrotech.com':             ('AfroTech', 'in'),
    'spectrumnoticias.com':     ('Spectrum Noticias', 'on'),
    'youtube.com':              ('YouTube', 'on'),
    'youtu.be':                 ('YouTube', 'on'),
    'instagram.com':            ('Instagram', 'on'),
    'linkedin.com':             ('LinkedIn', 'on'),
    'jtubert.medium.com':       ('Medium', 'on'),
    'amazon.com':               ('Amazon', 'on'),
    'roblox.com':               ('Roblox', 'on'),
    'huggingface.co':           ('Hugging Face', 'on'),
    'business.google.com':      ('Google', 'on'),
    'thinkwithgoogle.com':      ('Google', 'on'),
    'webbyawards.com':          ('the Webby Awards', 'on'),
    'winners.webbyawards.com':  ('the Webby Awards', 'on'),
    'iadas.net':                ('IADAS', 'on'),
    'thefwa.com':               ('The FWA', 'on'),
    'aicpawards.awardcore.com': ('the AICP Awards', 'on'),
    'aw.certmetrics.com':       ('AWS', 'on'),
    'elojodeiberoamerica.com':  ('El Ojo', 'on'),
    'live.mirren.com':          ('Mirren Live', 'on'),
}

VERBS = {
    'ARTICLE': 'Read the article', 'INTERVIEW': 'Read the interview',
    'QUOTE': 'Read the article', 'PANELIST': 'Read the article',
    'BOOK': 'Buy the book', 'GAME': 'Play the game',
    'CERTIFICATION': 'View the certification',
}

# Some destinations are not articles at all - a jury listing, an awards
# winners page, a social post, an event agenda. Matched on host (and path
# where the host serves more than one kind of thing) before the category
# fallback, because "Read the article in X" is wrong for all of these.
DESTINATION_RULES = [
    ('linkedin.com',              None,          'See the post on LinkedIn'),
    ('jtubert.medium.com',        None,          'Read the post on Medium'),
    ('winners.webbyawards.com',   None,          'See the award on the Webby Awards'),
    ('webbyawards.com',           None,          'See the award on the Webby Awards'),
    ('thefwa.com',                'jury',        'See the jury on The FWA'),
    ('iadas.net',                 'bio',         'View the profile on IADAS'),
    ('aicpawards.awardcore.com',  None,          'See the AICP Awards'),
    ('live.mirren.com',           'agenda',      'See the agenda on Mirren Live'),
    ('elojodeiberoamerica.com',   None,          'See the session on El Ojo'),
    ('business.google.com',       None,          'Read the case study on Google'),
    ('thinkwithgoogle.com',       None,          'Read the case study on Google'),
    ('aw.certmetrics.com',        None,          'Verify the certification on AWS'),
    ('roblox.com',                None,          'Play the game on Roblox'),
    ('amazon.com',                None,          'Buy the book on Amazon'),
]

def cta_label(link, category, override=''):
    """Name the destination, and describe what it actually is.
    A `cta` column on the sheet overrides everything."""
    if override and override.strip() and override.strip() != 'N/A':
        return override.strip()
    host = link.split('//')[-1].split('/')[0].lower()
    bare = host[4:] if host.startswith('www.') else host
    path = '/' + '/'.join(link.split('//')[-1].split('/')[1:])
    for h, needle, label in DESTINATION_RULES:
        if bare == h and (needle is None or needle in path.lower()):
            return label
    name, prep = OUTLETS.get(bare, (None, 'on'))
    cat = (category or '').upper()
    if any(v in bare for v in VIDEO_HOSTS):
        verb = 'Watch'
    elif any(v in bare for v in BROADCAST_HOSTS):
        verb = VERBS.get(cat, 'Watch').replace('Read the', 'Watch the')
    else:
        verb = VERBS.get(cat, 'Read more')
    if not name:
        return verb
    if verb == 'Watch':
        return f'Watch {prep} {name}'
    if verb == 'Read more':
        verb = 'Read the article' if prep == 'in' else 'Read'
    return f'{verb} {prep} {name}'

def load_summaries():
    """Fallback summaries kept in the repo, since `npm run download`
    overwrites stories.csv from the Google Sheet."""
    path = os.path.join(ROOT, '_data', 'summaries.yml')
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        k, v = line.split(':', 1)
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        out[k.strip()] = v
    return out

SUMMARIES = load_summaries()

def pick_summary(eid, row, title, cat, date_label):
    """Sheet column wins, then the repo file, then a generated fallback."""
    col = (row.get('summary') or row.get('description') or '').strip()
    if col and col != 'N/A':
        return col
    if SUMMARIES.get(eid):
        return SUMMARIES[eid]
    return build_summary(title, cat, date_label)

SELECTED = load_selected()
SHORT_TITLES = load_short_titles()
MEDIA_LINKS = load_media_links()
AUDIO = load_audio()


def main():
    rows = [r for r in csv.DictReader(open(CSV, encoding='utf-8')) if r.get('id')]
    os.makedirs(OUT, exist_ok=True)
    # Clear only previously generated entry pages - a stale entry must not
    # linger as a live URL - while leaving hand-written files (index.html) alone.
    for f in os.listdir(OUT):
        path = os.path.join(OUT, f)
        if f == 'index.html' or not (f.endswith('.html') or f.endswith('.md')):
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
    featured_items = []
    for idx, r in enumerate(eligible):
        eid = r['id'].strip()
        title = r['title'].strip()
        prev_r = eligible[idx-1] if idx > 0 else None
        next_r = eligible[idx+1] if idx < len(eligible)-1 else None

        asset = (r.get('asset') or '').strip()
        has_asset = on_disk(asset)
        poster = (r.get('poster') or '').strip()
        mtype = (r.get('type') or 'image').strip()
        link = (r.get('link') or '').strip()
        cat = (r.get('category') or 'Work').strip()
        date_label = (r.get('date') or '').strip()

        # og:image: the entry's own art where it has some, else the story poster
        if has_asset and mtype == 'image':
            image = asset
        elif on_disk(poster):
            image = poster
        else:
            image = 'assets/story-poster-landscape.jpg'

        fm = {
            'layout': 'entry',
            'permalink': f'/work/{eid}/',
            'entry_id': eid,
            'title': title,
            'title_plain': strip_tags(title),
            'seo_title': seo_title(eid, strip_tags(title)),
            'category': cat,
            'date_label': date_label,
            'iso_date': iso_date(date_label),
            'link': '' if blank(link) else link,
            'asset': asset if has_asset else '',
            'poster': '' if blank(poster) else poster,
            'image': image,
            'media_type': mtype,
            'media_link': MEDIA_LINKS.get(eid, ('', ''))[0],
            'media_link_label': MEDIA_LINKS.get(eid, ('', ''))[1],
            'audio_file': AUDIO.get(eid, ('', ''))[0],
            'audio_label': AUDIO.get(eid, ('', ''))[1],
            'has_audio': 'yes' if (mtype == 'video' and has_asset
                                   and has_audio(asset)) else '',
            'cta_label': cta_label(link, cat, r.get('cta') or r.get('cta_label') or ''),
            # template QUOTE means the title IS the quotation. Note `category`
            # QUOTE means something else - quoted in someone else's article.
            'is_quote': 'yes' if (r.get('template') or '').strip().upper() == 'QUOTE' else '',
            'summary': pick_summary(eid, r, title, cat, date_label),
            'sitemap_lastmod': iso_date(date_label),
            # when the written piece was last revised, not when the sheet row
            # was: a download rewrites the whole CSV, which would stamp all 49
            'last_modified_at': git_date(os.path.join(ROOT, '_work_bodies', f'{eid}.md')),
            'prev_id': prev_r['id'].strip() if prev_r else '',
            'prev_title': prev_r['title'].strip() if prev_r else '',
            'next_id': next_r['id'].strip() if next_r else '',
            'next_title': next_r['title'].strip() if next_r else '',
            'position': idx + 1,
            'total': len(eligible),
        }
        prose = load_body(eid)
        if eid in SELECTED:
            featured_items.append({
                'id': eid,
                'title': fm['title_plain'],
                'category': cat,
                'blurb': fm['summary'],
                'date': date_label,
            })
        fm['has_body'] = 'yes' if prose else ''
        fm['word_count'] = str(len(prose.split())) if prose else '0'
        page = '---\n' + ''.join(f'{k}: {yaml_str(v)}\n' for k, v in fm.items()) + '---\n'
        if prose:
            page += '\n' + prose + '\n'
        with open(os.path.join(OUT, f'{eid}.md'), 'w', encoding='utf-8') as fh:
            fh.write(page)
        written += 1

    # keep the order given in selected.yml rather than sheet order
    featured_items.sort(key=lambda i: SELECTED.index(i['id']))
    featured = write_featured(featured_items)
    lastmod = write_lastmod({r['id'].strip(): git_date(os.path.join(ROOT, '_work_bodies', f"{r['id'].strip()}.md"))
                             for r in eligible})
    order, counts, year_of = write_year_index(eligible, featured)
    nav = write_nav(eligible, year_of)
    print(f"generated {written} entry pages in work/")
    print(f"  featured: {featured}")
    dated = sum(1 for v in lastmod['entries'].values() if v)
    print(f"  lastmod: {dated}/{len(lastmod['entries'])} entries dated, "
          f"home {lastmod['home']}, work {lastmod['work']}, about {lastmod['about']}")
    print("  years: " + ", ".join(f"{y} ({counts[y]})" for y in order))
    for eid, why in skipped:
        print(f"  skipped {eid}: {why}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
