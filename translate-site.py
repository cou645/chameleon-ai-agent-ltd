#!/usr/bin/env python3
"""
translate-site.py — Build static translated copies of the Chameleon AI website.

Usage:
    python3 translate-site.py                      # build all languages (cache must be warm)
    python3 translate-site.py --seed               # warm caches then build (first run)
    python3 translate-site.py --seed-only          # warm caches only, no HTML output
    python3 translate-site.py --langs de,fr,es     # specific languages only
    python3 translate-site.py --seed --wait 60     # custom wait between seed and build
    python3 translate-site.py --no-update-en       # don't inject switcher into English pages

Output layout:
    /de/*.html, /fr/*.html, ...  (translated copies)
    /*.html                      (English source, updated with lang switcher)
    /style.css                   (updated with lang-switcher CSS, once)
"""

import re
import sys
import time
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

def hashtext(lang: str, text: str) -> str:
    """Call hashtext binary. Returns translation (cache hit) or original (cache miss)."""
    stripped = text.strip()
    if not stripped or not re.search(r'[A-Za-z]', stripped):
        return text
    try:
        result = subprocess.run(
            ["hashtext", lang, stripped],
            capture_output=True, text=True, timeout=15
        )
        out = result.stdout.strip()
        if not out:
            return text
        lead  = text[:len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        return lead + out + trail
    except Exception:
        return text


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

def cmd_seed(langs: list):
    """Warm the hashtext cache for all languages by translating every unique string."""
    html_files = sorted(SITE_ROOT.glob("*.html"))
    all_strings: set = set()
    for f in html_files:
        soup = BeautifulSoup(f.read_text(), "lxml")
        # Strip injected switcher so its text doesn't pollute the string set
        old = soup.find("div", class_="lang-switcher")
        if old:
            old.decompose()
        for node in iter_text_nodes(soup):
            all_strings.add(str(node).strip())

    print(f"  {len(all_strings)} unique strings across {len(html_files)} pages")

    for lang in langs:
        hits = 0
        sys.stdout.write(f"  {lang:4s}  ")
        sys.stdout.flush()
        for text in all_strings:
            result = hashtext(lang, text)
            if result.strip() != text:
                hits += 1
            sys.stdout.write(".")
            sys.stdout.flush()
        print(f"  {hits}/{len(all_strings)} cached")


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

            # Translate every eligible text node
            nodes = list(iter_text_nodes(soup))
            total += len(nodes)
            for node in nodes:
                result = hashtext(lang, str(node))
                if result != str(node):
                    node.replace_with(result)
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
                   help="Warm hashtext caches then exit (no HTML output)")
    p.add_argument("--seed", action="store_true",
                   help="Warm caches before building (recommended on first run)")
    p.add_argument("--wait", type=int, default=45,
                   help="Seconds to wait after seeding before building (default 45)")
    p.add_argument("--no-update-en", action="store_true",
                   help="Don't inject the lang switcher into English source pages")
    args = p.parse_args()

    active = [l.strip() for l in args.langs.split(",") if l.strip() in LANGS]
    if not active:
        sys.exit("No valid language codes. Available: " + ", ".join(LANGS))

    print(f"Languages ({len(active)}): {', '.join(active)}")

    if args.seed or args.seed_only:
        print("[seed]")
        cmd_seed(active)
        if args.seed_only:
            print("[done] Run without --seed-only to generate HTML.")
            return
        print(f"[seed] Waiting {args.wait}s for background translations to fill cache...")
        time.sleep(args.wait)

    print("[build]")
    cmd_build(active, update_en=not args.no_update_en)
    print("[done]")


if __name__ == "__main__":
    main()
