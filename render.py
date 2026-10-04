#!/usr/bin/env python3
"""Build a single, self-contained slides.html from the slide-*.md files.

Usage:
    ./render.py               # reads ./slide-*.md, writes ./slides.html
    ./render.py -o talk.html  # different output file
    ./render.py --no-notes    # leave the speaker notes out of the file

Requires: python3 with the "markdown" and "pygments" packages
    (dnf install python3-markdown python3-pygments, or pip install markdown pygments)

Markdown conventions:
  * files are ordered by their number: slide-0.md, slide-1.md, ...
  * a line holding only "---" starts a new slide
  * the first heading of a slide is its title; a "Slide 4.1.2:" prefix is
    dropped, and "(Backup)" in the prefix marks the slide as a backup slide
  * a blockquote starting with "> Notes" holds the speaker notes
  * the first slide of the first file is the title slide, and the first slide
    of the last file is the closing slide; both get a photo background

In the browser:
    right / space / PageDown   next slide        left / PageUp   previous slide
    Home / End                 first / last      f               fullscreen
    n                          show / hide notes p               presenter window
Printing the page (Ctrl+P, "Save as PDF") gives one slide per page.
"""

import argparse
import base64
import html
import re
import sys
from pathlib import Path

try:
    import markdown
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound
except ImportError as e:
    sys.exit(f"missing python package: {e.name} (pip install markdown pygments)")

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
LOGO = ASSETS / "ceph-logo.svg"
TITLE_PHOTO = ASSETS / "photo-title.jpg"
CLOSING_PHOTO = ASSETS / "photo-closing.jpg"

FENCE = re.compile(r"^(```+|~~~+)\s*([\w+-]*)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
SLIDE_PREFIX = re.compile(r"^Slide\s+[\d.]+\s*(\((?P<tag>[^)]*)\))?\s*:\s*", re.I)
BARE_URL = re.compile(r"(?<![<(\[`\w])(https?://[^\s<>)]+)")
STRIKE = re.compile(r"~~(.+?)~~")


# --------------------------------------------------------------- parsing

def slide_files(directory):
    files = []
    for path in directory.glob("slide-*.md"):
        m = re.fullmatch(r"slide-(\d+)\.md", path.name)
        if m:
            files.append((int(m.group(1)), path))
    return [path for _, path in sorted(files)]


def split_slides(text):
    """Split a file into slides on '---' lines that are outside code fences."""
    slides, current, fence = [], [], None
    for line in text.splitlines():
        m = FENCE.match(line)
        if m:
            if fence is None:
                fence = m.group(1)[0]
            elif line.strip().startswith(fence):
                fence = None
        if fence is None and line.strip() == "---":
            slides.append(current)
            current = []
        else:
            current.append(line)
    slides.append(current)
    return [s for s in slides if any(line.strip() for line in s)]


def extract_notes(lines):
    """Pull '> Notes ...' blockquotes out of a slide. Returns (body, notes)."""
    body, notes, i = [], [], 0
    while i < len(lines):
        if re.match(r"^>\s*Notes\b", lines[i], re.I):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            block[0] = re.sub(r"^Notes\s*[:-]?\s*", "", block[0], flags=re.I)
            block[0] = block[0][:1].upper() + block[0][1:]
            notes.append("\n".join(block))
        else:
            body.append(lines[i])
            i += 1
    return body, "\n\n".join(notes)


def extract_title(lines):
    """Take the first heading off a slide. Returns (level, title, tag, rest)."""
    fence = None
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if m:
            fence = None if fence else m.group(1)
        if fence:
            continue
        m = HEADING.match(line)
        if m:
            title, tag = m.group(2), None
            prefix = SLIDE_PREFIX.match(title)
            if prefix:
                tag = prefix.group("tag")
                title = title[prefix.end():]
            return len(m.group(1)), title, tag, lines[:i] + lines[i + 1:]
        if line.strip():
            break
    return 0, "", None, lines


# ------------------------------------------------------------- rendering

def render_code(code, lang):
    if not lang:
        # compiler / program output: highlight the words that matter
        out = html.escape(code)
        out = re.sub(r"\b(error|static assertion failed)\b", r'<span class="err">\1</span>', out)
        out = re.sub(r"\bnote:", '<span class="nt">note:</span>', out)
        out = re.sub(r"(?m)^(\s*\d*\s*\|\s*)([\^~]+)\s*$", r'\1<span class="err">\2</span>', out)
        return f'<pre class="code output"><code>{out}</code></pre>'
    try:
        lexer = get_lexer_by_name(lang, stripnl=False)
    except ClassNotFound:
        return f'<pre class="code"><code>{html.escape(code)}</code></pre>'
    out = highlight(code, lexer, HtmlFormatter(nowrap=True)).rstrip("\n")
    return f'<pre class="code lang-{html.escape(lang)}"><code>{out}</code></pre>'


def render_markdown(lines, line_breaks=False):
    """Markdown to HTML, with code fences highlighted by pygments."""
    blocks, text, i = [], [], 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if m:
            fence, lang, code = m.group(1), m.group(2), []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                code.append(lines[i])
                i += 1
            i += 1
            text += ["", f"@@CODE{len(blocks)}@@", ""]
            blocks.append(render_code("\n".join(code), lang))
        else:
            line = STRIKE.sub(r"<del>\1</del>", lines[i])
            text.append(BARE_URL.sub(r"<\1>", line))
            i += 1
    extensions = ["tables", "sane_lists"] + (["nl2br"] if line_breaks else [])
    out = markdown.markdown("\n".join(text), extensions=extensions)
    for n, block in enumerate(blocks):
        out = out.replace(f"<p>@@CODE{n}@@</p>", block)
    return out


def inline(text):
    out = markdown.markdown(text)
    return re.sub(r"^<p>|</p>$", "", out.strip())


def build_slides(files, with_notes=True):
    slides = []
    for file_index, path in enumerate(files):
        for slide_index, lines in enumerate(split_slides(path.read_text())):
            lines, notes = extract_notes(lines)
            level, title, tag, body = extract_title(lines)
            first = slide_index == 0
            if first and file_index == 0:
                kind = "title"
            elif first and file_index == len(files) - 1:
                kind = "closing"
            elif level == 1:
                kind = "section"
            else:
                kind = "content"
            slides.append({
                "kind": kind,
                "title": title,
                "tag": tag,
                "body": render_markdown(body, line_breaks=kind in ("title", "closing")),
                "notes": render_markdown(notes.splitlines()) if with_notes and notes else "",
                "source": path.name,
            })
    return slides


def slide_html(slide, number, total, logo):
    classes = f"slide {slide['kind']}" + (" backup" if slide["tag"] else "")
    badge = f'<span class="badge">{html.escape(slide["tag"])}</span>' if slide["tag"] else ""
    title = inline(slide["title"]) if slide["title"] else ""
    heading = f"<h1>{title}{badge}</h1>" if title else ""
    notes = f'<aside class="notes">{slide["notes"]}</aside>' if slide["notes"] else ""
    return f"""
<section class="{classes}" data-source="{slide['source']}" data-title="{html.escape(slide['title'].replace('`', ''), quote=True)}">
  <div class="logo">{logo}</div>
  <header>{heading}</header>
  <div class="body"><div class="fit">{slide['body']}</div></div>
  <footer><span class="page">{number} / {total}</span></footer>
  {notes}
</section>"""


def data_uri(path, mime):
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


# ------------------------------------------------------------------ page

# Colours are the ones of https://ceph.io (src/css/settings.colors.css):
# navy, royal, gunmetal, blue, the reds, and the two greys. The lighter blue
# is the site's blue at a lightness that is readable on a dark background.
CSS = r"""
:root {
  --navy: hsl(237, 74%, 13%);
  --royal: hsl(237, 74%, 25%);
  --gunmetal: hsl(235, 16%, 16%);
  --blue: hsl(214, 82%, 51%);
  --blue-light: hsl(214, 82%, 76%);
  --red: hsl(360, 84%, 67%);
  --red-light: hsl(360, 84%, 83%);
  --grey-300: hsl(210, 40%, 96%);
  --grey-500: hsl(210, 29%, 87%);
  --grey-dim: hsl(210, 20%, 66%);
  --font: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --mono: "JetBrains Mono", "Source Code Pro", "DejaVu Sans Mono", ui-monospace, Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body { background: #05061c; color: var(--grey-300); font-family: var(--font); overflow: hidden; }

#screen { position: fixed; inset: 0; }
#stage { position: absolute; width: 1280px; height: 720px; transform-origin: 0 0; overflow: hidden;
  background: var(--navy); }

.slide { position: absolute; inset: 0; padding: 52px 72px 44px; display: flex; flex-direction: column;
  visibility: hidden; background: var(--navy); }
.slide.current { visibility: visible; }

.logo { position: absolute; top: 34px; right: 48px; width: 104px; line-height: 0; }
.logo svg { width: 100%; height: auto; }

header { flex: none; padding-right: 150px; }
h1 { margin: 0 0 26px; font-size: 38px; line-height: 1.18; font-weight: 600; color: #fff;
  letter-spacing: -0.01em; text-wrap: balance; }
h1 code { font-size: 0.86em; }
.badge { display: inline-block; margin-left: 16px; padding: 4px 12px; border: 1px solid var(--red);
  border-radius: 999px; color: var(--red); font-size: 14px; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; vertical-align: middle; }

.body { flex: 1; min-height: 0; overflow: hidden; }
.fit { font-size: 27px; line-height: 1.42; }
.fit > :first-child { margin-top: 0; }
.fit > :last-child { margin-bottom: 0; }
.fit p { margin: 0 0 0.7em; }
.fit ul, .fit ol { margin: 0 0 0.7em; padding-left: 1.25em; }
.fit li { margin: 0 0 0.5em; padding-left: 0.25em; }
.fit li::marker { color: var(--red); font-weight: 600; }
.fit strong { color: #fff; font-weight: 600; }
.fit em { color: var(--red-light); font-style: italic; }
.fit del { color: var(--grey-dim); }
.fit a { color: var(--blue-light); text-decoration-color: hsla(214, 82%, 76%, 0.5); text-underline-offset: 0.18em;
  overflow-wrap: anywhere; }
.fit h2, .fit h3 { margin: 0.9em 0 0.4em; font-size: 0.8em; font-weight: 600; color: var(--red);
  letter-spacing: 0.08em; text-transform: uppercase; }

code { font-family: var(--mono); font-size: 0.86em; }
:not(pre) > code { padding: 0.08em 0.32em; border-radius: 5px; background: hsla(214, 82%, 76%, 0.13);
  color: var(--blue-light); white-space: nowrap; }
pre.code { margin: 0 0 0.75em; padding: 0.85em 1.1em; border-radius: 10px; background: var(--gunmetal);
  border: 1px solid hsla(210, 40%, 96%, 0.09); border-left: 4px solid var(--blue); overflow: hidden;
  font-size: 0.74em; line-height: 1.42; tab-size: 2; }
pre.code code { font-size: 1em; color: var(--grey-500); }
pre.output { border-left-color: var(--red); background: hsl(237, 40%, 9%); }
.err { color: var(--red); font-weight: 600; }
.nt { color: var(--blue-light); }

/* pygments tokens */
.code .c, .code .c1, .code .cm, .code .ch, .code .cs { color: var(--grey-dim); font-style: italic; }
.code .cp, .code .cpf { color: var(--red-light); }
.code .k, .code .kd, .code .kr, .code .kn, .code .kc, .code .ow { color: var(--red); }
.code .kt, .code .nc, .code .nn, .code .nb { color: var(--blue-light); }
.code .nf, .code .fm { color: #fff; }
.code .s, .code .s1, .code .s2, .code .sc, .code .se { color: var(--red-light); }
.code .m, .code .mi, .code .mf, .code .mh { color: var(--red-light); }
.code .o, .code .p { color: var(--grey-500); }

table { border-collapse: collapse; margin: 0 0 0.75em; font-size: 0.9em; }
th, td { padding: 0.42em 1em 0.42em 0; text-align: left; border-bottom: 1px solid hsla(210, 40%, 96%, 0.16); }
th { color: var(--red); font-size: 0.74em; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; }

footer { position: absolute; right: 48px; bottom: 18px; font-size: 14px; color: var(--grey-dim);
  font-variant-numeric: tabular-nums; }
#progress { position: absolute; left: 0; bottom: 0; height: 4px; background: var(--red); transition: width 0.2s; }

/* section openers: the first slide of each file */
.section h1 { font-size: 50px; margin-bottom: 34px; padding-top: 18px; }
.section h1::before { content: ""; display: block; width: 72px; height: 6px; margin-bottom: 24px;
  border-radius: 3px; background: var(--red); }
.section .fit { font-size: 31px; }

/* title and closing slides: photo background, tinted like the site's hero */
.title, .closing { justify-content: center; padding: 72px 88px; background-size: cover; background-position: center; }
.title { background-image: linear-gradient(90deg, hsla(237, 74%, 13%, 0.92) 0%, hsla(237, 74%, 20%, 0.72) 52%,
  hsla(237, 74%, 25%, 0.25) 100%), var(--photo-title); }
.closing { background-image: linear-gradient(90deg, hsla(237, 74%, 13%, 0.9) 0%, hsla(237, 74%, 16%, 0.7) 55%,
  hsla(237, 74%, 25%, 0.2) 100%), var(--photo-closing); }
.title .logo, .closing .logo { top: 56px; left: 88px; right: auto; width: 168px; }
.title header, .closing header { padding: 0; }
.title h1, .closing h1 { font-size: 84px; line-height: 1.05; margin: 0 0 18px; letter-spacing: -0.02em; }
.title .body, .closing .body { flex: none; overflow: visible; }
.title .fit h2 { margin: 0 0 56px; font-size: 34px; font-weight: 400; color: var(--grey-300);
  letter-spacing: 0; text-transform: none; }
.title .fit h3 { margin: 0 0 10px; font-size: 16px; }
.title .fit p { font-size: 26px; line-height: 1.5; }
.closing .fit { font-size: 25px; max-width: 800px; }
.closing .fit > p:first-child { font-size: 40px; color: var(--red-light); margin-bottom: 1.3em; }
.title footer, .closing footer { display: none; }

/* notes: 'n' shows them under the slide, 'p' opens the presenter window */
.notes { display: none; }
#notes { position: fixed; left: 0; right: 0; bottom: 0; max-height: 34%; overflow: auto; display: none;
  padding: 16px 28px; background: hsla(235, 16%, 12%, 0.97); border-top: 3px solid var(--red);
  font-size: 20px; line-height: 1.45; color: var(--grey-300); }
#notes p, #notes ul { margin: 0 0 0.5em; }
#notes:empty::before { content: "no notes for this slide"; color: var(--grey-dim); }
body.show-notes #notes { display: block; }

body.presenter #screen { right: 42%; bottom: 30%; }
body.presenter #notes { display: block; left: 58%; top: 0; max-height: none; border-top: 0;
  border-left: 3px solid var(--red); font-size: 24px; padding: 28px 32px; }
#status { display: none; position: fixed; left: 0; right: 42%; bottom: 0; height: 30%; padding: 22px 28px;
  font-size: 22px; color: var(--grey-dim); }
body.presenter #status { display: block; }
#status b { display: block; color: #fff; font-size: 30px; font-weight: 600; margin: 4px 0 18px; }
#status .clock { color: var(--red); font-size: 44px; font-weight: 600; font-variant-numeric: tabular-nums; }

@media print {
  @page { size: 1280px 720px; margin: 0; }
  html, body { height: auto; overflow: visible; background: none; }
  #screen { position: static; }
  #stage { position: static; transform: none !important; width: auto; height: auto; overflow: visible; }
  .slide { position: relative; width: 1280px; height: 720px; visibility: visible; break-after: page;
    -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  #progress, #notes, #status { display: none !important; }
}
"""

JS = r"""
(function () {
  var stage = document.getElementById('stage');
  var screenBox = document.getElementById('screen');
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var notes = document.getElementById('notes');
  var progress = document.getElementById('progress');
  var presenter = /[?&]presenter/.test(location.search);
  var peer = presenter ? window.opener : null;
  var current = 0;
  var started = Date.now();

  // shrink the text of a slide until it fits, vertically and horizontally
  function fitSlide(slide) {
    var body = slide.querySelector('.body'), fit = slide.querySelector('.fit');
    if (!body || !fit || slide.classList.contains('title') || slide.classList.contains('closing')) return;
    fit.style.fontSize = '';
    var size = parseFloat(getComputedStyle(fit).fontSize), min = size * 0.5;
    function overflows() {
      if (fit.scrollHeight > body.clientHeight + 1) return true;
      var pres = fit.querySelectorAll('pre, table');
      for (var i = 0; i < pres.length; i++) {
        if (pres[i].scrollWidth > pres[i].clientWidth + 1) return true;
        if (pres[i].offsetWidth > body.clientWidth + 1) return true;
      }
      return false;
    }
    while (overflows() && size > min) {
      size -= 0.5;
      fit.style.fontSize = size + 'px';
    }
  }
  function fitAll() { slides.forEach(fitSlide); }

  function scale() {
    var w = screenBox.clientWidth, h = screenBox.clientHeight;
    var s = Math.min(w / 1280, h / 720);
    stage.style.transform = 'translate(' + (w - 1280 * s) / 2 + 'px,' + (h - 720 * s) / 2 + 'px) scale(' + s + ')';
  }

  function show(n, fromPeer) {
    current = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach(function (s, i) { s.classList.toggle('current', i === current); });
    var own = slides[current].querySelector('.notes');
    notes.innerHTML = own ? own.innerHTML : '';
    progress.style.width = (100 * current / Math.max(1, slides.length - 1)) + '%';
    if (location.hash !== '#' + (current + 1)) history.replaceState(null, '', '#' + (current + 1));
    var next = slides[current + 1];
    document.getElementById('next').textContent = next ? next.dataset.title : 'end of the talk';
    if (!fromPeer && peer && !peer.closed) peer.postMessage({ slide: current }, '*');
  }

  window.addEventListener('message', function (e) {
    if (e.data && typeof e.data.slide === 'number') {
      if (!peer && e.source) peer = e.source;
      show(e.data.slide, true);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    switch (e.key) {
      case 'ArrowRight': case 'ArrowDown': case 'PageDown': case ' ': case 'Enter':
        show(current + 1); break;
      case 'ArrowLeft': case 'ArrowUp': case 'PageUp': case 'Backspace':
        show(current - 1); break;
      case 'Home': show(0); break;
      case 'End': show(slides.length - 1); break;
      case 'n': document.body.classList.toggle('show-notes'); scale(); break;
      case 'f':
        if (document.fullscreenElement) document.exitFullscreen();
        else document.documentElement.requestFullscreen();
        break;
      case 'p':
        if (!presenter) {
          peer = window.open(location.pathname + '?presenter#' + (current + 1), 'presenter');
        }
        break;
      default: return;
    }
    e.preventDefault();
  });

  stage.addEventListener('click', function (e) {
    if (e.target.closest('a')) return;
    var box = stage.getBoundingClientRect();
    show(current + (e.clientX - box.left < box.width / 3 ? -1 : 1));
  });

  window.addEventListener('resize', scale);
  window.addEventListener('hashchange', function () {
    var n = parseInt(location.hash.slice(1), 10);
    if (n && n - 1 !== current) show(n - 1);
  });

  if (presenter) {
    document.body.classList.add('presenter');
    setInterval(function () {
      var t = Math.floor((Date.now() - started) / 1000);
      document.getElementById('clock').textContent =
        Math.floor(t / 60) + ':' + ('0' + (t % 60)).slice(-2);
    }, 1000);
  }

  scale();
  fitAll();
  show((parseInt(location.hash.slice(1), 10) || 1) - 1, true);
  window.addEventListener('load', fitAll);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitAll);
})();
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" media="print" onload="this.onload=null;this.removeAttribute('media');"
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap">
<style>
:root {{ --photo-title: url({photo_title}); --photo-closing: url({photo_closing}); }}
{css}
</style>
</head>
<body>
<div id="screen"><div id="stage">
{slides}
<div id="progress"></div>
</div></div>
<div id="notes"></div>
<div id="status">next<b id="next"></b><span class="clock" id="clock">0:00</span></div>
<script>{js}</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="build slides.html from slide-*.md")
    parser.add_argument("-d", "--dir", type=Path, default=HERE, help="directory holding the slide-*.md files")
    parser.add_argument("-o", "--output", type=Path, default=None, help="output file (default: <dir>/slides.html)")
    parser.add_argument("--no-notes", action="store_true", help="do not include the speaker notes")
    args = parser.parse_args()

    files = slide_files(args.dir)
    if not files:
        sys.exit(f"no slide-*.md files in {args.dir}")
    for asset in (LOGO, TITLE_PHOTO, CLOSING_PHOTO):
        if not asset.exists():
            sys.exit(f"missing asset: {asset}")

    slides = build_slides(files, with_notes=not args.no_notes)
    logo = re.sub(r"<title>.*?</title>", "", LOGO.read_text()).strip()
    body = "\n".join(slide_html(s, i + 1, len(slides), logo) for i, s in enumerate(slides))
    title = re.sub(r"<[^>]+>", "", inline(slides[0]["title"])) or "Slides"

    output = args.output or args.dir / "slides.html"
    output.write_text(PAGE.format(
        title=html.escape(title),
        photo_title=data_uri(TITLE_PHOTO, "image/jpeg"),
        photo_closing=data_uri(CLOSING_PHOTO, "image/jpeg"),
        css=CSS, slides=body, js=JS))
    print(f"{output}: {len(slides)} slides from {len(files)} files, {output.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
