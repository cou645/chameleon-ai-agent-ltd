#!/usr/bin/env python3
"""
translate-site.py — Build static translated copies of the Chameleon AI website.

Usage:
    python3 translate-site.py                      # build all languages (cache must be warm)
    python3 translate-site.py --seed               # bulk-fill the cache then build (first run)
    python3 translate-site.py --seed-only          # bulk-fill the cache only, no HTML output
    python3 translate-site.py --langs de,fr,es     # specific languages only
    python3 translate-site.py --seed --no-batch    # old one-string-at-a-time seed + --wait
    python3 translate-site.py --no-update-en       # don't inject switcher into English pages

Seeding uses `hashtext --batch` (one request per tile of strings x languages) by
default — far faster and cheaper than one request per string. It is synchronous,
so no --wait is needed after it. Pass --no-batch for the legacy background-fill
seed (then --wait matters).

Output layout:
    /de/*.html, /fr/*.html, ...  (translated copies)
    /*.html                      (English source, updated with lang switcher)
    /style.css                   (updated with lang-switcher CSS, once)
"""

import re
import os
import sys
import gzip
import json
import time
import hashlib
import subprocess
import argparse
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Comment

SITE_ROOT = Path(__file__).parent

LANGS = {
    "ar": {"name": "العربية",   "flag": "🇸🇦", "rtl": True},
    "cy": {"name": "Cymraeg",    "flag": "🏴󠁧󠁢󠁷󠁬󠁳󠁿"},
    "de": {"name": "Deutsch",    "flag": "🇩🇪"},
    "es": {"name": "Español",    "flag": "🇪🇸"},
    "fr": {"name": "Français",   "flag": "🇫🇷"},
    "hi": {"name": "हिन्दी",     "flag": "🇮🇳"},
    "it": {"name": "Italiano",   "flag": "🇮🇹"},
    "ja": {"name": "日本語",     "flag": "🇯🇵"},
    "ko": {"name": "한국어",     "flag": "🇰🇷"},
    "pt": {"name": "Português",  "flag": "🇵🇹"},
    "ru": {"name": "Русский",    "flag": "🇷🇺"},
    "zh": {"name": "中文",       "flag": "🇨🇳"},
  "el": {"name": "Ελληνικά",  "flag": "🇬🇷"},
  "id": {"name": "Indonesia",  "flag": "🇮🇩"},
  "pl": {"name": "Polski",    "flag": "🇵🇱"},
  "ro": {"name": "Română",    "flag": "🇷🇴"},
  "sw": {"name": "Kiswahili", "flag": "🇰🇪"},
  "uk": {"name": "Українська","flag": "🇺🇦"},
  "vi": {"name": "Tiếng Việt","flag": "🇻🇳"},
}

# Tags whose text content is never translated
SKIP_TAGS = {"style", "script", "code", "pre", "noscript"}

# Pages that are pure reference tables — still copied per language, but their
# text (protocol codes, single letters) is not worth sending to the translator.
SEED_SKIP_PAGES = {"codes.html"}

LANG_SWITCHER_CSS = """
/* ── Language switcher ── */
.lang-switcher { position: relative; flex-shrink: 0; margin-left: .4rem; }
.lang-btn {
  background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.35);
  border-radius: 20px; color: white; cursor: pointer; font-size: .82rem;
  font-weight: 600; letter-spacing: .02em;
  padding: .28rem .8rem; white-space: nowrap;
  transition: background .2s;
}
.lang-btn:hover { background: rgba(255,255,255,.3); }
.lang-menu {
  display: none; position: absolute; right: 0; top: calc(100% + 8px);
  background: white; border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,.18);
  border: 1px solid var(--border); min-width: 140px; z-index: 200;
  overflow: hidden;
}
.lang-switcher.open .lang-menu { display: block; }
.lang-switcher .lang-menu a {
  display: block; padding: .45rem 1rem; color: var(--text) !important;
  text-decoration: none; font-size: .88rem; white-space: nowrap;
  background: none; border-radius: 0;
  transition: background .15s;
}
.lang-switcher .lang-menu a:hover { background: var(--bg) !important; }
@media (max-width: 700px) { .lang-switcher { display: none; } }
"""

# ── Translation ──────────────────────────────────────────────────────────────

def canon(text: str) -> str:
    """Canonical form used as the cache key: stripped, internal whitespace collapsed.
    HTML renders runs of whitespace as a single space, so this is display-neutral
    and lets multi-line source text nodes map to one stable cache entry / one line
    in the batch input file."""
    return re.sub(r"\s+", " ", text.strip())


def translatable(text: str) -> bool:
    c = canon(text)
    return bool(c) and re.search(r"[A-Za-z]", c) is not None


def hashtext(lang: str, text: str) -> str:
    """Look the string up in the hashtext cache. Returns the translation, or the
    original text unchanged on a cache miss / echo-of-source."""
    stripped = canon(text)
    if not stripped or not re.search(r'[A-Za-z]', stripped):
        return text
    try:
        result = subprocess.run(
            ["hashtext", lang, stripped],
            capture_output=True, text=True, timeout=15
        )
        out = result.stdout.strip()
        if not out or out == stripped:
            return text
        lead  = text[:len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        return lead + out + trail
    except Exception:
        return text


def _cache_dirs() -> list:
    env = os.environ.get("HASHTEXT_DIR", "")
    dirs = [d.strip() for d in re.split(r"[;:]", env) if d.strip()]
    if not dirs:
        dirs = ["/usr/share/locale/hashtext", "/tmp/hashtext"]
    return [Path(d) for d in dirs]


def cached_translation(lang: str, canon_text: str):
    """Read a base translation straight from the hashtext flat-file cache — no
    subprocess. Handles gzip-compressed and styled-JSON entries. Returns the
    translation string, or None on a miss."""
    h = hashlib.md5(canon_text.encode("utf-8")).hexdigest()
    for d in _cache_dirs():
        p = d / lang / f"{h}.hashtext"
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if raw[:2] == b"\x1f\x8b":                       # gzip
            try:
                raw = gzip.decompress(raw)
            except OSError:
                continue
        s = raw.decode("utf-8", "replace").strip()
        if s.startswith("{"):                            # styled {"t":"...","s":"..."}
            try:
                s = json.loads(s).get("t", "")
            except ValueError:
                pass
        if s:
            return s
    return None


def iter_text_nodes(soup):
    """Yield NavigableString nodes that should be translated."""
    for node in soup.find_all(string=True):
        if isinstance(node, Comment):
            continue
        if any(getattr(p, "name", None) in SKIP_TAGS for p in node.parents):
            continue
        text = str(node)
        if not text.strip() or not re.search(r'[A-Za-z]', text):
            continue
        yield node


# ── Path fixing ──────────────────────────────────────────────────────────────

def fix_relative_paths(soup):
    """Prefix ../ to all relative href/src values (page lives one level deep)."""
    for tag in soup.find_all(True):
        for attr in ("href", "src"):
            val = tag.get(attr, "")
            if val and not re.match(r'(https?:|mailto:|#|//|\.\.)', val):
                tag[attr] = f"../{val}"


# ── Language switcher HTML ───────────────────────────────────────────────────

def _switcher(label: str, flag: str, items_html: str) -> str:
    return (
        '<div class="lang-switcher">'
        f'<button class="lang-btn" onclick="this.parentElement.classList.toggle(\'open\')">'
        f'{flag} {label} ▾</button>'
        f'<div class="lang-menu">{items_html}</div>'
        '</div>'
    )


def switcher_for_en(fname: str, langs: list) -> str:
    items = "".join(
        f'<a href="{lng}/{fname}">{LANGS[lng]["flag"]} {lng.upper()} — {LANGS[lng]["name"]}</a>'
        for lng in langs
    )
    return _switcher("EN", "🌐", items)


def switcher_for_lang(current: str, fname: str, langs: list) -> str:
    info = LANGS[current]
    items = [f'<a href="../{fname}">🌐 EN — English</a>']
    items += [
        f'<a href="../{lng}/{fname}">{LANGS[lng]["flag"]} {lng.upper()} — {LANGS[lng]["name"]}</a>'
        for lng in langs if lng != current
    ]
    return _switcher(current.upper(), info["flag"], "".join(items))


def inject_switcher(soup, html: str):
    """Replace or insert the lang-switcher at the end of .nav-links."""
    nav_links = soup.find("div", class_="nav-links")
    if not nav_links:
        return
    old = nav_links.find("div", class_="lang-switcher")
    if old:
        old.decompose()
    nav_links.append(BeautifulSoup(html, "html.parser"))


# ── HTML rendering ───────────────────────────────────────────────────────────

def render(soup) -> str:
    """Serialize soup to a complete HTML document string."""
    html_tag = soup.find("html")
    return "<!DOCTYPE html>\n" + str(html_tag) + "\n"


# ── Commands ─────────────────────────────────────────────────────────────────

def collect_strings() -> list:
    """Every unique canonical translatable string across all English pages."""
    html_files = sorted(SITE_ROOT.glob("*.html"))
    seen, ordered = set(), []
    for f in html_files:
        if f.name in SEED_SKIP_PAGES:
            continue
        soup = BeautifulSoup(f.read_text(), "lxml")
        old = soup.find("div", class_="lang-switcher")   # don't seed the switcher's own text
        if old:
            old.decompose()
        for node in iter_text_nodes(soup):
            c = canon(str(node))
            if c and c not in seen:
                seen.add(c)
                ordered.append(c)
    return ordered, len(html_files)


def cmd_seed_batch(langs: list, strings_per_call: int, tile_langs: int, jobs: int):
    """Bulk-fill the hashtext cache with `hashtext --batch` — one request per
    tile of (strings x languages). Synchronous; no --wait needed afterwards."""
    strings, n_pages = collect_strings()
    print(f"  {len(strings)} unique strings across {n_pages} pages")
    if not strings:
        return

    import tempfile, os
    fd, path = tempfile.mkstemp(prefix="ht-batch-", suffix=".txt", dir=str(SITE_ROOT))
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write("\n".join(strings) + "\n")
        cmd = [
            "hashtext", "--batch",
            "--langs", ",".join(langs),
            "--file", path,
            "--strings", str(strings_per_call),
            "--jobs", str(jobs),
        ]
        if tile_langs and tile_langs < len(langs):
            cmd += ["--tile-langs", str(tile_langs)]
        print("  " + " ".join(cmd))
        # stream progress straight through; no timeout (batch is the long part)
        rc = subprocess.run(cmd).returncode
        if rc != 0:
            print(f"  [warn] hashtext --batch exited {rc}")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    # report coverage per language from the now-warm cache
    for lang in langs:
        hits = sum(1 for s in strings if hashtext(lang, s).strip() != s)
        print(f"  {lang:4s}  {hits}/{len(strings)} cached")


def cmd_seed(langs: list):
    """Legacy seed: one `hashtext <lng> <text>` call per string, relying on the
    binary's background-fill. Kept for --no-batch. --wait matters after this."""
    strings, n_pages = collect_strings()
    print(f"  {len(strings)} unique strings across {n_pages} pages")
    for lang in langs:
        hits = 0
        sys.stdout.write(f"  {lang:4s}  ")
        sys.stdout.flush()
        for text in strings:
            if hashtext(lang, text).strip() != text:
                hits += 1
            sys.stdout.write(".")
            sys.stdout.flush()
        print(f"  {hits}/{len(strings)} cached")


def cmd_build(langs: list, update_en: bool = True):
    """Generate translated HTML pages and optionally update English source pages."""
    html_files = sorted(SITE_ROOT.glob("*.html"))

    # Add lang-switcher CSS to style.css (once)
    css_path = SITE_ROOT / "style.css"
    if css_path.exists() and "lang-switcher" not in css_path.read_text():
        with css_path.open("a") as f:
            f.write(LANG_SWITCHER_CSS)
        print("  Added lang-switcher CSS to style.css")

    # Generate one set of translated pages per language
    for lang in langs:
        out_dir = SITE_ROOT / lang
        out_dir.mkdir(exist_ok=True)
        total = trans = 0

        for html_file in html_files:
            soup = BeautifulSoup(html_file.read_text(), "lxml")

            # Drop any pre-existing switcher so we don't translate it
            old = soup.find("div", class_="lang-switcher")
            if old:
                old.decompose()

            # Set <html lang="…"> and optional dir="rtl"
            html_tag = soup.find("html")
            if html_tag:
                html_tag["lang"] = lang
                if LANGS[lang].get("rtl"):
                    html_tag["dir"] = "rtl"
                elif "dir" in html_tag.attrs:
                    del html_tag["dir"]

            # Rewrite relative paths for subdirectory depth
            fix_relative_paths(soup)

            # Translate every eligible text node from the warm cache (direct file
            # reads, no subprocess)
            nodes = list(iter_text_nodes(soup))
            count_page = html_file.name not in SEED_SKIP_PAGES   # reference pages don't count toward %
            if count_page:
                total += len(nodes)
            for node in nodes:
                original = str(node)
                key = canon(original)
                t = cached_translation(lang, key)
                if not t or t == key:
                    continue
                lead  = original[:len(original) - len(original.lstrip())]
                trail = original[len(original.rstrip()):]
                node.replace_with(lead + t + trail)
                if count_page:
                    trans += 1

            # Inject language switcher
            inject_switcher(soup, switcher_for_lang(lang, html_file.name, langs))

            (out_dir / html_file.name).write_text(render(soup))

        pct = int(100 * trans / total) if total else 0
        print(f"  [{lang}]  {len(html_files)} pages  {trans}/{total} nodes translated ({pct}%)")

    # Update English source pages with switcher pointing to ALL built language dirs,
    # not just the ones in this run — so adding new langs doesn't drop existing ones.
    if update_en:
        all_built = sorted(
            d.name for d in SITE_ROOT.iterdir()
            if d.is_dir() and d.name in LANGS
        )
        for html_file in html_files:
            soup = BeautifulSoup(html_file.read_text(), "lxml")
            inject_switcher(soup, switcher_for_en(html_file.name, all_built))
            html_file.write_text(render(soup))
        print(f"  Updated {len(html_files)} English pages with lang switcher ({', '.join(all_built)})")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Build static translated copies of the Chameleon AI website.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  First run (seed caches, wait 60s, build):
    python3 translate-site.py --seed --wait 60

  Rebuild after cache is already warm:
    python3 translate-site.py

  Only German and French:
    python3 translate-site.py --langs de,fr

  Just warm the cache, build later:
    python3 translate-site.py --seed-only --langs de,fr,es
"""
    )
    p.add_argument("--langs", default=",".join(LANGS),
                   help="Comma-separated language codes (default: all cached)")
    p.add_argument("--seed-only", action="store_true",
                   help="Fill the hashtext cache then exit (no HTML output)")
    p.add_argument("--seed", action="store_true",
                   help="Fill the cache before building (recommended on first run)")
    p.add_argument("--no-batch", action="store_true",
                   help="Legacy seed: one hashtext call per string (then --wait applies)")
    p.add_argument("--wait", type=int, default=45,
                   help="Seconds to wait after a --no-batch seed before building (default 45)")
    p.add_argument("--batch-strings", type=int, default=16,
                   help="Source strings per hashtext --batch request (default 16)")
    p.add_argument("--batch-tile-langs", type=int, default=10,
                   help="Target languages per hashtext --batch request (default 10)")
    p.add_argument("--batch-jobs", type=int, default=3,
                   help="Parallel hashtext --batch requests (default 3; higher risks rate limits)")
    p.add_argument("--no-update-en", action="store_true",
                   help="Don't inject the lang switcher into English source pages")
    args = p.parse_args()

    active = [l.strip() for l in args.langs.split(",") if l.strip() in LANGS]
    if not active:
        sys.exit("No valid language codes. Available: " + ", ".join(LANGS))

    print(f"Languages ({len(active)}): {', '.join(active)}")

    if args.seed or args.seed_only:
        print("[seed]")
        if args.no_batch:
            cmd_seed(active)
            if not args.seed_only:
                print(f"[seed] Waiting {args.wait}s for background translations to fill cache...")
                time.sleep(args.wait)
        else:
            cmd_seed_batch(active, args.batch_strings, args.batch_tile_langs, args.batch_jobs)
        if args.seed_only:
            print("[done] Run without --seed-only to generate HTML.")
            return

    print("[build]")
    cmd_build(active, update_en=not args.no_update_en)
    print("[done]")


if __name__ == "__main__":
    main()
