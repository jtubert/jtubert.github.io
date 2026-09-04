# jtubert.com

Personal site for Juan (John) Tubert, CTO at Tombras. Jekyll, built and served by
GitHub Pages from `github.com/jtubert/jtubert.github.io`. Live at
`https://www.jtubert.com`.

## The two surfaces

Everything is driven from one Google Sheet, and every entry appears twice:

1. **The homepage** is a single **AMP Web Story** (`index.markdown`). One
   `amp-story-page` per sheet row.
2. **`/work/<id>/`** is a normal HTML page per entry, plus the **`/work/`**
   landing. These exist because the story alone gave all 52 entries one URL,
   which is unindexable. The landing does **not** list the entries: it is a
   full-bleed clip with a headline and three picks over it, and the full list
   lives in the drawer behind the edge tab, the same drawer every entry page
   carries. The drawer is
   rendered server-side from `_data/nav.json`, so all 49 links are in the
   markup of every page either way.

## Content pipeline

```
Google Sheet  ->  _data/stories.csv  ->  work/<id>.md  ->  _site/work/<id>/
                (script.sh, curl)      (generate-entry-pages.py)   (jekyll)
```

**`_data/stories.csv` is overwritten by `npm run download`. Never hand-edit it,
and never store anything there you cannot regenerate.** Anything that must
survive a download lives in the repo instead:

| Repo-side, survives download | What it is |
|---|---|
| `_work_bodies/<id>.md` | The long-form body for an entry. One per entry; all 49 have one. |
| `_data/selected.yml` | The hand-picked ids that lead `/work/` as cards. Currently `book`, `ojo3`, `pods`. |
| `_data/summaries.yml` | Fallback summaries, used only when the sheet column is empty. |
| `assets/thumbs-src/<id>.jpg` | Hand-made card art that overrides the derived thumbnail. |
| `_data/media_links.yml` | Entries whose hero opens a PDF. `id: <url> | <optional caption>`. |
| `_data/audio.yml` | Entries with an episode to play. Same `id: <url> | <caption>` format. |

Generated, do not edit by hand: `work/*.md`, `_data/featured.json`,
`_data/years.yml`, `assets/thumbs/*`.

## Commands

```
npm run download_and_deploy   # the usual one: download, generate, thumbs, commit, push
npm run local                 # generate, then jekyll serve
npm run build                 # generate, then jekyll build
npm run generate_pages        # tools/generate-entry-pages.py
npm run generate_thumbs       # tools/generate-thumbs.py  (must run AFTER generate_pages)
```

Order matters: `generate_thumbs` reads `_data/featured.json`, which
`generate_pages` writes. It exits non-zero if that file is missing.

`npm run deploy` is `git add . && git commit && git push` with a generic
message. Prefer a real commit message when the change is worth explaining.

## Adding or changing content

**A new sheet row** does nothing until `npm run download_and_deploy` runs. Then
one row automatically produces: the `/work/<id>/` page, its listing on `/work/`
under the right year, a sitemap entry, a page in the AMP story, repointed
prev/next arrows on its neighbours, an updated "All N pieces of work" count, and
a CTA label derived from the link's destination. Deleting a row removes all of
that on the next run.

A row needs an **`id`** and a **`title`**. Rows with a blank or `N/A` title are
skipped, which is why `clio` and `google` have no pages. `order` controls
position.

A new row gets **no body** until `_work_bodies/<id>.md` exists, and will **not**
appear in "Selected" unless added to `_data/selected.yml`.

**Templates** are chosen per row by the sheet's `template` column, resolved as
`_includes/templates/<TEMPLATE>.html`: `DEFAULT` (46), `FULL-VIDEO` (4),
`QUOTE` (1), `HOMEPAGE` (1, the cover). Note `template: QUOTE` is what makes an
entry render as a pull quote; the `category` column also has a `QUOTE` value
which means something else entirely (quoted in someone else's article).

## Writing rules

- **No em dashes.** Anywhere in site copy: bodies, summaries, titles, headlines.
  Restructure the sentence instead of substituting another dash. The only
  remaining ones are the `<title>` separators (`Work — Juan (John) Tubert`) and
  the homepage's `sr-only` h1, which are deliberate and unresolved.
- Bodies are one or two paragraphs, roughly 60 to 150 words, first person, plain.
  Ground them in the linked source. Where the link is a LinkedIn post or there is
  none, stay short and claim only what the entry itself supports.
- Cross-link entries with `[text](/work/<id>/)`. There are 49 such links; keep
  them resolving and never self-referential.
- Never invent facts to fill a page. Several bodies were written from PDFs the
  user supplied (`Mirren Live slides 2026.pdf`, `LA Presentation.pdf`,
  `AdAi presentation 2024.pdf`), which are in the repo root.

## Layout

Two stylesheets, both inlined: `_includes/css/head.css` for the AMP story,
`_includes/css/entry.css` for `/work/` and the entry pages.

**Entry pages** (`_layouts/entry.html`). Flat DOM in the order head, media, CTA,
body, which is exactly what a phone should stack, so mobile carries no rules at
all. Above `62rem` the container is `70rem` (`.wrap-entry`) and `.entry-main`
becomes a two-column grid: media in the left column, everything else in the
right. The grid has an **empty fourth row at `1fr`**; without it the media,
spanning the real rows, stretches them and opens gaps under the meta, CTA and
body. `ojoquote` has no media and falls back to a centred column via
`.no-media`.

**`/work/` landing** (`.wrap-index`, `.index-hero`). Full-bleed footage with
the copy at its foot: `.stage-bg` is `position:fixed` at `z-index:-1`, and the
wrap is a `100svh` flex column so `.index-hero` can sit on `margin-top:auto`.
Everything fits one viewport at 1440x900, 1280x720, 768x1024 and 390x844.

**The dark treatment is scoped to `.stage-page` on `<body>`.** The entry pages
share this stylesheet, so anything unscoped turns them dark too. The scoped
set is the masthead rule, `.whoami`, the inverted `.brandmark img`, `.lede`,
and the solid-red `.wnav-tab`.

`.stage-veil` carries **two** gradients. A diagonal keeps the left quiet for
the type and leaves the right open on the person, who sits on the right of a
locked-off two-shot. On its own it put the copy halfway along its own ramp,
over the brightest part it covers, so a second vertical pass darkens the foot.

The headline is a sentence rather than a title, about 120 characters against
the 30 an entry page carries, so `.index-hero h1` overrides the shared `h1`
size down to `clamp(1.5rem, 3.6vw, 2.15rem)`.

## Image and video specs

| Where | Aspect | Deliver | Notes |
|---|---|---|---|
| Story page media (`DEFAULT`) | **3:2** | 1200x800 | Well is a constant 3:2, `object-position: 50% 40%` so the crop favours the top. Max rendered 530px CSS. |
| `/work/` pick thumbnails | **1:1** | 600x600+ | Displayed at 52px (60 on phones). Build outputs 288px JPEG. One subject, no small text, nothing in the corners. |
| `/work/` backdrop | **16:9 or wider** | 1920x1080 wanted | Five clips in `assets/bg/`, one picked per visit. All silent, 13 to 20s, under 410 KB each. The widest source is 960x540, so every one upscales on a laptop. |
| Homepage cover video | **9:16** | portrait | Full bleed. |

Hand-made card art goes in `assets/thumbs-src/<id>.jpg` and beats the derived
frame. `tools/generate-thumbs.py` tracks source path, mtime and size in
`assets/thumbs/sources.json`, so swapping art in or deleting it invalidates
correctly. It only generates for ids in `_data/selected.yml`.

## Behaviour worth knowing

- **Mute note.** Videos autoplay muted, so video pages show "Plays muted. Use the
  player controls for sound." It only appears where the clip actually has an
  audio track: the generator runs `ffprobe` per asset and sets `has_audio`. Four
  clips are silent screen recordings (`comfyui`, `gifmaker`, `test`, `work2025`)
  and correctly show nothing. No ffprobe means no note, rather than a false
  promise of sound.
- **CTAs** open in a new tab with `rel="noopener noreferrer"` and are labelled
  from the link's **destination**, not the media type: outlet-named where the
  domain is known ("Read the article in AdAge"), generic otherwise. Both story
  templates carry the outlink: `DEFAULT` and `FULL-VIDEO`. `FULL-VIDEO`
  hardcodes its label, so a search for the shared markup will miss it.
- **Hero PDFs.** `_data/media_links.yml` gives an entry a PDF of the original.
  On image entries the hero itself becomes the link; on video entries only the
  caption does, since a clickable video would swallow the player controls.
  Percent-encode spaces in the path. The caption defaults to the article
  wording, so decks pass their own after a `|`.
- **Audio.** `_data/audio.yml` puts a player under the hero. `preload="metadata"`
  so the file is not fetched until play. Encode speech as mono: the source for
  `podcast` was 320kbps dual-mono stereo at 80 MB, and 64kbps mono is 16 MB with
  no audible loss, since its side channel measured 0.08% of the mid.
- **The `/work/` backdrop is one of five, picked at random per visit**, from
  `assets/bg/`. Each has a matching `.jpg` poster and its own phone focal
  point. The pick runs in an inline script **immediately after the `<video>`,
  not at the foot of the page**: poster and source must be set together and
  before first paint, or the browser paints one clip's still and then loads
  another's video under it. The element ships with **no `src` or `poster` at
  all** for the same reason, so with scripting off there is no backdrop, which
  the veil over the dark ground survives. Only the chosen clip is fetched.

  | file | source | window | why that window |
  |---|---|---|---|
  | `sofa` | `EO2025_VecinoTurbet_small` | 3:20 +13s | One locked-off two-shot for all 11m35s, but a lower-third names the interviewer around 3:35. |
  | `ojostage` | `ojo_long` | 10:12 +13s | Bottom 15% cropped: the source carries burned-in subtitles exactly where the copy sits. |
  | `workwall` | `work2025` | all 20s | Already 2.37:1, so almost nothing is lost to the crop. |
  | `nodes` | `comfyui` | all 15s | The darkest of the five, so the best type legibility. |
  | `pods` | `pods_compressed` | 0:16 +13s | Only this window. Elsewhere the clip is a talking head and screen-shared slides whose text fights the headline. |

  All are silent, so they are muted with no controls and carry no mute note.
  Reduced motion pauses whichever was picked and its poster stands in.
- **`assets/test.mp4` must never be a backdrop.** It is the most cinematic
  clip in the repo and has **TONGYI WANX burned into every frame**, which is
  Alibaba's video-model watermark. Fine as the artifact on `/work/test/`;
  not as a full-bleed hero.
- **A phone keeps about a quarter of a 16:9 backdrop.** At 390px wide, cover
  crops a 960x540 clip to roughly 26% of its width, and the quarter worth
  keeping differs per clip, so each carries its own `--focus-x` (on `sofa`,
  centred lands on the gap between the two men; `64%` is him). Below `48rem`
  the veil also turns vertical, since a diagonal built for a wide screen
  leaves the foot of a tall one too bright to read on.
- **Byte-range requests matter when a video is seeked.** GitHub Pages serves
  them, `python3 -m http.server` does not, so against a plain local server a
  seek silently does nothing. Check `video.seekable.end(0)`: the duration means
  ranges work, `0` means the server, not the page, is what you are measuring.
  Nothing seeks right now, but the trap cost an hour once already.
- **`amp-story-cta-layer` is dead** in amp-story 1.0. Use
  `amp-story-page-outlink`.
- **Story CTAs cannot open in a new tab.** The runtime overwrites the anchor's
  target with `_top`, so `target="_blank"` validates but is inert. Deliberate
  upstream (ampproject/amphtml#36428): a new tab needs a trusted event and
  Safari does not treat the swipe-up as trusted, which broke navigation on iOS.
  Do not re-add it. The `/work/` entry pages are ordinary HTML and do open in a
  new tab.
- **AMP constraints**: `amp-custom` CSS is capped at 75,000 bytes and forbids
  `!important`. `amp-video` does not support `layout="intrinsic"`. Validate with
  `npx amphtml-validator _site/index.html` after touching anything in the story.

## Environment gotchas

- **`python3` resolves to different interpreters** depending on the shell.
  Homebrew's has no Pillow; miniforge's does. `generate-thumbs.py` re-execs
  itself into one that has Pillow, so do not pin a path in `package.json`.
- **Ruby/Jekyll** runs through `Gemfile.local` with a pinned PATH, already baked
  into the npm scripts. `npm run unquarantine` clears the macOS quarantine flag
  that blocks gem binaries after a fresh `bundle install`.
- **Git identity**: this is a GitHub repo, so the global noreply email is
  correct. The `jtubert@tombras.com` rule in the global CLAUDE.md applies only to
  Bitbucket remotes.
- **`pbcopy` mangles accents** unless `LANG=en_US.UTF-8` is set. Always set it
  when putting text on the clipboard for the sheet, and verify the round trip.

## Verification habits that have paid off here

Measure, do not eyeball, and **include a control that can fail**. Several real
bugs in this repo were only caught that way:

- A grep for `media-note` matched the inlined CSS rule on all 49 pages and looked
  like a pass. Query the rendered element instead.
- A layout "all clear" means nothing unless the same check fails somewhere. The
  responsive checks flip at exactly 992px, 0 pages below and 48 above.
- The AMP story's outlink count caught one template that a text search missed
  (41 of 42).
- Blank grid thumbnails came from measuring variance **across** channels; a solid
  cyan scores high. Per-channel spatial standard deviation is the right metric.

After pushing, GitHub Pages takes roughly 60 to 90 seconds. Poll the live URL and
check the actual bytes rather than assuming the deploy worked.

## Open items

- `_data/years.yml` is still generated but nothing reads it any more: it was
  only for the old `/work/` list. Harmless, but it is dead output.
- `_data/featured.json` still carries a `blurb` per entry. The picks show only
  the category and the title now, so the blurb goes nowhere.

- Six sheet cells had em dashes and were fixed by hand. The `mirren` title still
  reads "Will be speaking..." in future tense while the body is past tense; the
  corrected title and summary were handed over for pasting.
- `/work/ojo3/` has a portrait 9:16 video that renders about 1100px tall in the
  hero. Deliberately left as is.
- `robots.txt` still describes the site as "Single-page AMP Story site" and
  contains an em dash. Out of date since `/work/` pages exist.
- Sitemap has not been submitted in Google Search Console.
- `assets/tombras_logo_rgb_vert.png` and `assets/tombras-logo-alpha.png` are
  unreferenced.
