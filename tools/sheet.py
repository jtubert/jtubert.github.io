#!/usr/bin/env python3
"""Read or change one cell of the Google Sheet that drives the site, by entry
id and column name, so a fix does not have to wait for someone to paste it.

    python3 tools/sheet.py show <id>                    # every column of a row
    python3 tools/sheet.py get  <id> <column>
    python3 tools/sheet.py set  <id> <column> <value>   # writes, then verifies
    python3 tools/sheet.py set  <id> <column> <value> --dry-run
    python3 tools/sheet.py add  <new id> --before <id> column=value ...   # new row, orders shift

Credentials come from .env at the repo root (GOOGLE_CLIENT,
GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN) and are never printed. .env is
gitignored and must stay that way: this repo is public and `npm run deploy` is
`git add .`.

The tab is "CMS". script.sh asks the gviz endpoint for "Sheet1", which only
works because gviz falls back to the first tab when the name does not exist;
the Sheets API has no such fallback.

A value is written as the same TYPE the column already holds, because the gviz
CSV that `npm run download` reads blanks any cell whose type differs from its
column's. The `date` column holds real dates formatted "mmmm yyyy"; writing
"May 2026" there as text came back from the download as an empty date, and the
entry silently lost it. So dates go in as serial numbers with the column's own
format, numbers as numbers, and text as text, and after every write the CSV is
downloaded again to confirm the cell came through.
"""

import argparse, csv, datetime, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = '14C-HoYPzEA0CzmX80Lj_6H3qliqbl2NOjAwSuWFejIY'
TAB = 'CMS'
API = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET}'
# the same export script.sh downloads, so a check here is a check of the build's input
CSV_URL = f'https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet=Sheet1'
EPOCH = datetime.date(1899, 12, 30)   # Sheets' day zero for date serials
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july',
          'august', 'september', 'october', 'november', 'december']


def env():
    path = os.path.join(ROOT, '.env')
    if not os.path.exists(path):
        sys.exit('no .env at the repo root; it needs GOOGLE_CLIENT, GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN')
    out = {}
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            out[k.replace('export ', '').strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in ('GOOGLE_CLIENT', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN') if not out.get(k)]
    if missing:
        sys.exit(f'.env is missing {", ".join(missing)}')
    return out


def token():
    e = env()
    body = urllib.parse.urlencode({
        'client_id': e['GOOGLE_CLIENT'], 'client_secret': e['GOOGLE_CLIENT_SECRET'],
        'refresh_token': e['GOOGLE_REFRESH_TOKEN'], 'grant_type': 'refresh_token',
    }).encode()
    try:
        return json.load(urllib.request.urlopen('https://oauth2.googleapis.com/token', body))['access_token']
    except urllib.error.HTTPError as err:
        # Google's error body names the problem (invalid_grant and so on), never the secret
        sys.exit(f'could not get an access token: HTTP {err.code} {err.read().decode(errors="replace")[:300]}')


def api(tok, url, data=None, method='GET'):
    req = urllib.request.Request(url, method=method, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as err:
        sys.exit(f'Sheets API: HTTP {err.code} {err.read().decode(errors="replace")[:400]}')


def grid(tok):
    """The tab as rows of cells, each with its displayed text, typed value and
    number format, plus the tab's numeric id for writes."""
    fields = ('sheets.properties(sheetId,title),sheets.data.rowData.values('
              'formattedValue,effectiveValue,userEnteredFormat.numberFormat)')
    d = api(tok, f'{API}?ranges={urllib.parse.quote(TAB)}&fields={urllib.parse.quote(fields)}')
    s = d['sheets'][0]
    if s['properties']['title'] != TAB:
        sys.exit(f'expected the tab {TAB!r}, got {s["properties"]["title"]!r}')
    rows = [r.get('values', []) for r in s['data'][0].get('rowData', [])]
    return s['properties']['sheetId'], rows


def text(cell):
    return (cell or {}).get('formattedValue', '')


def locate(rows, eid, column=None):
    header = [text(c) for c in rows[0]]
    if 'id' not in header:
        sys.exit('no "id" column in the header row')
    idc = header.index('id')
    hits = [n for n, r in enumerate(rows) if n and len(r) > idc and text(r[idc]) == eid]
    if len(hits) != 1:
        sys.exit(f'expected one row with id {eid!r}, found {len(hits)}')
    if column is None:
        return hits[0], None, header
    if column not in header:
        sys.exit(f'no column {column!r}; columns are: {", ".join(h for h in header if h)}')
    return hits[0], header.index(column), header


def a1(row, col):
    s, i = '', col + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return f'{TAB}!{s}{row + 1}'


def column_kind(rows, col, skip_row):
    """What the column holds, by majority of its other non-empty cells:
    ('date', pattern), ('number', format) or ('text', None)."""
    kinds = Counter()
    formats = {}
    for n, r in enumerate(rows[1:], 1):
        if n == skip_row or len(r) <= col or not r[col].get('effectiveValue'):
            continue
        ev, nf = r[col]['effectiveValue'], r[col].get('userEnteredFormat', {}).get('numberFormat')
        if 'numberValue' in ev:
            k = 'date' if nf and nf.get('type') in ('DATE', 'DATE_TIME') else 'number'
            formats.setdefault(k, nf)
        else:
            k = 'text'
        kinds[k] += 1
    if not kinds:
        return 'text', None
    k = kinds.most_common(1)[0][0]
    return k, formats.get(k)


def parse_date(value):
    """'May 2026', 'May 1, 2026', '2026-05' or '2026-05-01'. A month alone means
    its first day, which is what every existing date in the column is."""
    v = value.strip()
    m = re.fullmatch(r'([A-Za-z]+)\s+(?:(\d{1,2}),?\s+)?(\d{4})', v)
    if m and m.group(1).lower() in MONTHS:
        return datetime.date(int(m.group(3)), MONTHS.index(m.group(1).lower()) + 1, int(m.group(2) or 1))
    m = re.fullmatch(r'(\d{4})-(\d{2})(?:-(\d{2}))?', v)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))
    sys.exit(f'{value!r} is not a date this column can hold; use e.g. "May 2026" or "2026-05-01"')


def typed(value, kind, fmt):
    """The cell payload for `value`, in the column's type and format."""
    if kind == 'date':
        cell = {'userEnteredValue': {'numberValue': (parse_date(value) - EPOCH).days}}
        cell['userEnteredFormat'] = {'numberFormat': fmt or {'type': 'DATE', 'pattern': 'mmmm yyyy'}}
        return cell, 'userEnteredValue,userEnteredFormat.numberFormat'
    if kind == 'number':
        try:
            n = float(value)
        except ValueError:
            sys.exit(f'{value!r} is not a number, and this column holds numbers')
        return {'userEnteredValue': {'numberValue': int(n) if n.is_integer() else n}}, 'userEnteredValue'
    return {'userEnteredValue': {'stringValue': value}}, 'userEnteredValue'


def csv_value(eid, column, tries=8):
    """The cell as `npm run download` will see it. gviz can trail an edit by a
    few seconds, so a mismatch is retried before it counts."""
    last = None
    for i in range(tries):
        raw = urllib.request.urlopen(f'{CSV_URL}&cachebust={time.time()}').read().decode('utf-8')
        for r in csv.DictReader(io.StringIO(raw)):
            if r.get('id') == eid:
                last = r.get(column, '')
        yield last
        time.sleep(2)


def add(tok, gid, rows, new_id, before, pairs, dry_run):
    """Insert a row for `new_id` directly above the row `before`, taking its
    `order` and moving every row from there down by one, the way new rows have
    been added by hand. Each value goes in as its column's type."""
    header = [text(c) for c in rows[0]]
    idc = header.index('id')
    if any(len(r) > idc and text(r[idc]) == new_id for r in rows[1:]):
        sys.exit(f'a row with id {new_id!r} already exists; use set to change it')
    n, _, _ = locate(rows, before)
    vals = {}
    for p in pairs:
        if '=' not in p:
            sys.exit(f'expected column=value, got {p!r}')
        k, v = p.split('=', 1)
        vals[k.strip()] = v
    vals['id'] = new_id
    unknown = [k for k in vals if k not in header]
    if unknown:
        sys.exit(f'no column {", ".join(map(repr, unknown))}; columns are: {", ".join(h for h in header if h)}')
    if any('—' in v for v in vals.values()):
        sys.exit('refusing to write an em dash: the site copy has none (see CLAUDE.md); restructure the sentence')

    oc = header.index('order')
    order_of = lambda r: (r[oc].get('effectiveValue', {}) if len(r) > oc else {}).get('numberValue')
    vals.setdefault('order', text(rows[n][oc]))
    new_order = float(vals['order'])
    # rows at and below the insertion point that sit at or after the new order
    bumps = [(i, order_of(r)) for i, r in enumerate(rows) if i >= n and order_of(r) is not None
             and order_of(r) >= new_order]

    cells = []
    for c, h in enumerate(header):
        if h in vals and vals[h] != '':
            kind, fmt = column_kind(rows, c, None)
            cell, _ = typed(vals[h], kind, fmt)
            cells.append(cell)
            print(f'  {h}: {vals[h]!r} ({kind})')
        else:
            cells.append({})
    print(f'insert above {before!r} (row {n + 1}) at order {vals["order"]}; '
          f'{len(bumps)} rows below move down one in order')
    if dry_run:
        print('nothing written')
        return

    requests = [
        # inheritFromBefore false: the new row takes the formatting of the row
        # below it, a real entry, not of whatever sits above
        {'insertDimension': {'range': {'sheetId': gid, 'dimension': 'ROWS', 'startIndex': n, 'endIndex': n + 1},
                             'inheritFromBefore': False}},
        {'updateCells': {'range': {'sheetId': gid, 'startRowIndex': n, 'endRowIndex': n + 1,
                                   'startColumnIndex': 0, 'endColumnIndex': len(header)},
                         'rows': [{'values': cells}],
                         'fields': 'userEnteredValue,userEnteredFormat.numberFormat'}},
    ]
    for i, o in bumps:
        new = o + 1
        requests.append({'updateCells': {
            'range': {'sheetId': gid, 'startRowIndex': i + 1, 'endRowIndex': i + 2,
                      'startColumnIndex': oc, 'endColumnIndex': oc + 1},
            'rows': [{'values': [{'userEnteredValue': {'numberValue': int(new) if float(new).is_integer() else new}}]}],
            'fields': 'userEnteredValue'}})
    api(tok, f'{API}:batchUpdate', {'requests': requests}, 'POST')

    _, rows = grid(tok)
    m, _, _ = locate(rows, new_id)
    wrote = {h: text(rows[m][c]) for c, h in enumerate(header) if h in vals and c < len(rows[m])}
    orders = [order_of(r) for r in rows[1:] if order_of(r) is not None]
    dupes = sorted({o for o in orders if orders.count(o) > 1})
    print(f'sheet: row {m + 1} added; duplicate orders: {dupes or "none"}')
    # the download must carry every value, or a type mismatch has blanked one
    for _ in range(8):
        raw = urllib.request.urlopen(f'{CSV_URL}&cachebust={time.time()}').read().decode('utf-8')
        got = next((r for r in csv.DictReader(io.StringIO(raw)) if r.get('id') == new_id), None)
        bad = {h: (wrote[h], (got or {}).get(h)) for h in wrote if got is None or got.get(h) != wrote[h]}
        if not bad:
            print('download: every value matches')
            return
        time.sleep(2)
    sys.exit(f'download disagrees with the sheet on {bad}; check the row before deploying')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('cmd', choices=['show', 'get', 'set', 'add'])
    ap.add_argument('id')
    ap.add_argument('args', nargs='*', help='get/set: column [value]; add: column=value ...')
    ap.add_argument('--before', help='add: the id of the row the new one goes above')
    ap.add_argument('--dry-run', action='store_true', help='say what would be written, write nothing')
    a = ap.parse_args()
    a.column = a.args[0] if a.cmd in ('get', 'set') and a.args else None
    a.value = a.args[1] if a.cmd == 'set' and len(a.args) > 1 else None
    if a.cmd in ('get', 'set') and not a.column:
        ap.error(f'{a.cmd} needs a column')
    if a.cmd == 'set' and a.value is None:
        ap.error('set needs a value')
    if a.cmd == 'add' and not a.before:
        ap.error('add needs --before <id>')

    tok = token()
    gid, rows = grid(tok)

    if a.cmd == 'add':
        add(tok, gid, rows, a.id, a.before, a.args, a.dry_run)
        return

    if a.cmd == 'show':
        n, _, header = locate(rows, a.id)
        for c, h in enumerate(header):
            if h:
                print(f'{a1(n, c):>9}  {h}: {text(rows[n][c]) if c < len(rows[n]) else ""!r}')
        return

    n, c, _ = locate(rows, a.id, a.column)
    before = text(rows[n][c]) if c < len(rows[n]) else ''
    if a.cmd == 'get':
        print(f'{a1(n, c)}  {before!r}')
        return

    if '—' in a.value:
        sys.exit('refusing to write an em dash: the site copy has none (see CLAUDE.md); restructure the sentence')
    kind, fmt = column_kind(rows, c, n)
    cell, fields = typed(a.value, kind, fmt)
    print(f'{a1(n, c)}  {a.column} holds {kind}' + (f' ({fmt.get("pattern")})' if fmt and fmt.get('pattern') else ''))
    if a.dry_run:
        print(f'would write {a.value!r} over {before!r}; nothing written')
        return

    api(tok, f'{API}:batchUpdate', {'requests': [{'updateCells': {
        'range': {'sheetId': gid, 'startRowIndex': n, 'endRowIndex': n + 1,
                  'startColumnIndex': c, 'endColumnIndex': c + 1},
        'rows': [{'values': [cell]}], 'fields': fields}}]}, 'POST')

    _, rows = grid(tok)
    after = text(rows[n][c]) if c < len(rows[n]) else ''
    print(f'sheet: {before!r} -> {after!r}')
    seen = None
    for seen in csv_value(a.id, a.column):
        if seen == after:
            print(f'download: {seen!r}, matches')
            return
    sys.exit(f'download shows {seen!r}, not {after!r}: the cell may not have the column\'s type, '
             'and npm run download would lose it. Check the sheet before deploying.')


if __name__ == '__main__':
    main()
