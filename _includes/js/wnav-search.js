// The drawer's keyword filter, shared by /work/ and every entry page. It is
// included inside each page's drawer IIFE, so it defines no globals and the
// two drawers cannot drift apart. Its markup is _includes/wnav-search.html.
//
// Filtering is plain substring matching over the row's own text plus the year
// heading above it, so "2023", "webby" and "ojo 2025" all work. Nothing is
// fetched and nothing is scored: 50 rows are already in the markup, and a
// ranked search over 50 titles would be harder to predict, not easier to use.
var qi = document.getElementById('wnav-q');
var qclear = document.getElementById('wnav-qclear');
var qnote = document.getElementById('wnav-qnote');
var qbox = document.getElementById('wnav-scroll');
var qindex = null;

// Accents are stripped both sides, so "iberoamerica" finds "Iberoamérica".
// Titles come from a Google Sheet and are inconsistently accented, so matching
// the bytes would make some posts unreachable by the word people would type.
function wnavNorm(s) {
  return s.normalize ? s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
                     : s.toLowerCase();
}

// Built on the first keystroke rather than on load: the drawer is rendered
// server-side and never changes, and most visitors never search.
function wnavIndex() {
  if (qindex) return qindex;
  qindex = [];
  var group = null, kids = qbox.children;
  for (var i = 0; i < kids.length; i++) {
    var el = kids[i];
    if (el.className.indexOf('wnav-yhead') !== -1) {
      // label is the rendered "2026 · 7"; year is just the number, so the
      // count can be restated for the filter and put back afterwards
      group = { head: el, rows: [], year: el.textContent,
                label: el.textContent, n: el.textContent.split('\u00b7')[0].trim() };
      qindex.push(group);
    } else if (el.className.indexOf('wnav-row') !== -1 && group) {
      group.rows.push({ el: el, text: wnavNorm(group.year + ' ' + el.textContent) });
    }
  }
  return qindex;
}

// Every term has to appear somewhere in the row, so terms narrow rather than
// widen: "ojo 2025" is the posts about El Ojo from 2025, not both sets.
function wnavFilter() {
  var raw = qi.value.trim();
  var terms = wnavNorm(raw).split(/\s+/);
  if (terms.length === 1 && terms[0] === '') terms = [];
  var groups = wnavIndex(), hits = 0;
  for (var g = 0; g < groups.length; g++) {
    var shown = 0;
    for (var r = 0; r < groups[g].rows.length; r++) {
      var row = groups[g].rows[r], ok = true;
      for (var t = 0; t < terms.length; t++) {
        if (row.text.indexOf(terms[t]) === -1) { ok = false; break; }
      }
      // an empty query matches everything, so this doubles as the reset
      row.el.className = row.el.className.replace(/ ?wnav-hide/, '') + (ok ? '' : ' wnav-hide');
      if (ok) shown++;
    }
    groups[g].head.className = groups[g].head.className.replace(/ ?wnav-hide/, '') + (shown ? '' : ' wnav-hide');
    // a heading reading "2026 \u00b7 7" above a single match is a lie, so while
    // a query is live the count is what the query found
    groups[g].head.textContent = terms.length ? groups[g].n + ' \u00b7 ' + shown : groups[g].label;
    hits += shown;
  }
  if (qclear) qclear.hidden = !raw;
  if (qnote) {
    qnote.hidden = !raw;
    qnote.textContent = !raw ? ''
      : hits === 0 ? 'Nothing matches that'
      : hits === 1 ? '1 post' : hits + ' posts';
  }
  qbox.scrollTop = 0;
}

// Called when the drawer closes, so reopening it never shows yesterday's
// filter. Cheap to call when nothing was ever typed.
function wnavReset() {
  if (!qi || (!qi.value && !qindex)) return;
  qi.value = '';
  wnavFilter();
}

// Focusing the box on open is right on a desktop, where typing is the next
// thing you do. On a touch screen it throws the keyboard over the list you
// opened the drawer to read, so there focus stays where it was.
function wnavFocusSearch() {
  if (!qi || !window.matchMedia) return false;
  if (!window.matchMedia('(min-width:48rem) and (pointer:fine)').matches) return false;
  qi.focus({ preventScroll: true });
  return true;
}

if (qi && qbox) {
  qi.addEventListener('input', wnavFilter);
  qi.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      // The first Escape clears the query and the second closes the drawer, so
      // a search can be abandoned without losing the list. stopPropagation is
      // what keeps the page's own Escape handler from closing it outright.
      if (qi.value) { e.stopPropagation(); wnavReset(); }
      return;
    }
    if (e.key === 'Enter') {
      var first = qbox.querySelector('.wnav-row:not(.wnav-hide)');
      // .click() rather than location.href, so the delegated handler in
      // analytics.html still reports this as a menu_nav
      if (first) { e.preventDefault(); first.click(); }
    }
  });
  if (qclear) {
    qclear.addEventListener('click', function () { wnavReset(); qi.focus(); });
  }
}
