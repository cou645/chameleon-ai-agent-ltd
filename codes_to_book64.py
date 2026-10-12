#!/usr/bin/env python3
"""codes.html -> Logistics-4x4.Lbook64: page = code. B55 -> B5, Z03 -> Z3
(codes are letter + doubled digit, Z is Z00-Z09). B0 = the B category
tables (Z0 also covers Z00). L0 = legend, Q0 = quick ref.
Run: /root/pyside6-venv/bin/python codes_to_book64.py"""
import os
import sys

from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "book64"))
from book64 import Book  # noqa: E402

soup = BeautifulSoup(open(os.path.join(HERE, "codes.html"),
                          encoding="utf-8"), "html.parser")
txt = lambda el: " ".join(el.get_text(" ").split()) if el else ""
md_table = lambda rows: "\n".join(
    ["| " + " | ".join(r) + " |" for r in rows[:1]] +
    ["|" + "---|" * len(rows[0])] +
    ["| " + " | ".join(r) + " |" for r in rows[1:]])

letters = {}                       # letter -> [(profile, icon, name, rows)]
profile = ""
for el in soup.select(".profile-header, .cat-label"):
    if "profile-header" in el["class"]:
        profile = txt(el.select_one(".ph-icon")) + " " + \
            txt(el.select_one(".ph-title"))
        continue
    table = el.find_next_sibling("table")
    rows = []
    for tr in table.select("tbody tr"):
        c, m = (txt(td) for td in tr.find_all("td"))
        rows.append(("**%s**" % c, "**%s**" % m) if "crit" in
                    (tr.get("class") or []) else (c, m))
    letters.setdefault(txt(el.select_one(".cat-letter")), []).append(
        (profile, txt(el.select_one(".cat-icon")),
         txt(el.select_one(".cat-name")), rows))

book = Book("md")
for letter, cats in letters.items():
    names = " / ".join(dict.fromkeys(n for _, _, n, _ in cats))
    body = ["Title:%s — %s" % (letter, names),
            "Icon:U+%X" % ord(cats[0][1][0]), "",
            "# %s — %s" % (letter, names)]
    for prof, icon, name, rows in cats:
        body += ["", "## %s %s" % (icon, name), "*%s*" % prof, "",
                 md_table([("Code", "Meaning")] + rows)]
    book.pages[letter + "0"] = "\n".join(body) + "\n"
    for code in dict.fromkeys(r[0].strip("*") for c in cats for r in c[3]):
        page = letter + code[2]
        if page == letter + "0":
            continue                        # Z00 lives on the Z0 table
        body = ["Title:%s" % code, "Icon:U+%X" % ord(cats[0][1][0]), "",
                "# %s" % code]
        for prof, icon, name, rows in cats:
            for c, m in rows:
                if c.strip("*") == code:
                    body += ["", "## %s %s" % (icon, name), "*%s*" % prof,
                             "", m]
        body += ["", "All %s codes: page %s0." % (letter, letter)]
        book.pages[page] = "\n".join(body) + "\n"

hdr = soup.select_one(".doc-header")
how = soup.select_one(".how-it-works")
sos = soup.select_one(".sos-band")
book.pages["L0"] = "\n".join([
    "Title:Legend — how the codes work", "Icon:U+1F6E1", "",
    "# " + txt(hdr.h1), "*%s*" % txt(hdr.select_one(".edition")), "",
    *(txt(p) + "\n" for p in hdr.find_all("p", class_=lambda c: not c)),
    "## " + txt(how.h3), "", txt(how.p), "",
    "```", "A11", "│└┴─ severity: 11 = nominal → 99 = emergency",
    "└─── category letter", "```", "",
    *(txt(p) + "\n" for p in how.find_all("p")[1:]),
    "## Profiles", "",
    *("- **%s** %s" % (txt(u.select_one(".ut-letter")), txt(u.select("div")[1]))
      for u in how.select(".ut")), "",
    "## 🆘 " + txt(sos.h4), "", txt(sos.p), "",
    "**%s**" % " + ".join(txt(c) for c in sos.select(".sos-chip")), "",
    "Every code has its own page: B55 → page B5, Z03 → page Z3. "
    "Page B0 holds all B codes.",
]) + "\n"

q = soup.select_one(".qref-table")
book.pages["Q0"] = "\n".join([
    "Title:Quick reference", "Icon:U+1F4CB", "",
    "# Quick reference — common situations", "",
    md_table([[txt(c) for c in tr.find_all(["th", "td"])]
              for tr in q.select("tr")]),
]) + "\n"

out = os.path.join(HERE, "Logistics-4x4.Lbook64")
book.save(out)
assert set(Book.load(out).pages) == set(book.pages)
print(out, len(book.pages), "pages")
