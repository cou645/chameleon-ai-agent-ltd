# Graph Report - website  (2026-07-25)

## Corpus Check
- 3 files · ~593,333 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 21 nodes · 32 edges · 6 communities (3 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `db049131`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- cmd_build
- cmd_seed
- translate-site.py
- README.md
- inject_switcher
- iter_text_nodes

## God Nodes (most connected - your core abstractions)
1. `cmd_build()` - 10 edges
2. `cmd_seed()` - 5 edges
3. `hashtext()` - 4 edges
4. `iter_text_nodes()` - 4 edges
5. `fix_relative_paths()` - 3 edges
6. `_switcher()` - 3 edges
7. `switcher_for_en()` - 3 edges
8. `switcher_for_lang()` - 3 edges
9. `inject_switcher()` - 3 edges
10. `render()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `cmd_build()` --calls--> `hashtext()`  [EXTRACTED]
  translate-site.py → translate-site.py  _Bridges community 1 → community 0_
- `cmd_build()` --calls--> `iter_text_nodes()`  [EXTRACTED]
  translate-site.py → translate-site.py  _Bridges community 5 → community 0_
- `cmd_seed()` --calls--> `iter_text_nodes()`  [EXTRACTED]
  translate-site.py → translate-site.py  _Bridges community 5 → community 1_
- `cmd_build()` --calls--> `switcher_for_en()`  [EXTRACTED]
  translate-site.py → translate-site.py  _Bridges community 2 → community 0_
- `cmd_build()` --calls--> `inject_switcher()`  [EXTRACTED]
  translate-site.py → translate-site.py  _Bridges community 4 → community 0_

## Import Cycles
- None detected.

## Communities (6 total, 3 thin omitted)

### Community 0 - "cmd_build"
Cohesion: 0.33
Nodes (6): cmd_build(), fix_relative_paths(), Prefix ../ to all relative href/src values (page lives one level deep)., Serialize soup to a complete HTML document string., Generate translated HTML pages and optionally update English source pages., render()

### Community 1 - "cmd_seed"
Cohesion: 0.40
Nodes (5): cmd_seed(), hashtext(), main(), Warm the hashtext cache for all languages by translating every unique string., Call hashtext binary. Returns translation (cache hit) or original (cache miss).

### Community 2 - "translate-site.py"
Cohesion: 0.83
Nodes (3): _switcher(), switcher_for_en(), switcher_for_lang()

## Knowledge Gaps
- **1 isolated node(s):** `Deploy trigger: Fri Apr 24 19:45:40 BST 2026`
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `cmd_build()` connect `cmd_build` to `cmd_seed`, `translate-site.py`, `inject_switcher`, `iter_text_nodes`?**
  _High betweenness centrality (0.274) - this node is a cross-community bridge._
- **Why does `cmd_seed()` connect `cmd_seed` to `translate-site.py`, `iter_text_nodes`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Why does `hashtext()` connect `cmd_seed` to `cmd_build`, `translate-site.py`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **What connects `Deploy trigger: Fri Apr 24 19:45:40 BST 2026` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._