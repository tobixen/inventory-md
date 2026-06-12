# Code Review: inventory-md (2026-06-11)

**Reviewer:** Claude (Fable 5, AI-assisted full review)
**Scope:** All of `src/inventory_md/`, `scripts/`, packaging and Makefile, at commit `5fefd1f`.
**Baseline:** Follows up on `CODE-REVIEW.md` (2025-12-28) and `code-review-2026-05-08.md`.

**Health snapshot:** 623 tests pass, `ruff check` is clean. Test coverage has grown
enormously since the 2025-12 review (parser, CLI, config, vocabulary, ledger,
staging, queries, labels, photo registry all covered). The codebase is in good
shape; most findings below are pipeline-consistency issues and duplication, not
broken core functionality.

---

## Status of previous findings

**Fixed since 2025-12-28:**
- Path traversal in photo upload — `sanitize_path_component()` / `validate_container_id()` (api_server.py:28-98)
- Wildcard CORS — now env-configurable, credentials disabled with `*` (api_server.py:136-150)
- Global git config mutation — replaced with inline `-c safe.directory` (api_server.py:499)
- Missing parser/CLI tests — extensive suites added

**Still open from 2026-05-08 (not repeated in detail here):**
- `vocabulary.py` mirrors tingbok's data model and hierarchy logic; canonical concept URLs + an ancestors endpoint remain the biggest architectural ROI
- `_SOURCE_LABELS` / `_uri_to_source()` knowledge belongs in tingbok
- `sync_eans_to_inventory.py` still has no tests and is still a standalone script

---

## 1. Bugs and correctness

### 1.1 Shopping pipeline: `to_tingbok` is never set by the producer (HIGH)
`tingbok_push.py:180` only pushes items flagged `to_tingbok: true`, but
`shop_import.py:_new_item_row()` does not emit that field, `scripts/staging.py`
does not document it, and `claude-skills/process-shopping.md` never instructs the
review step to set it. A staging file that goes through the documented pipeline
therefore pushes **zero** observations, silently — the exact failure mode the
`require_flat()` refactor (issue 1 in `shopping-pipeline-issues-2026-06-07.md`)
was added to prevent for the `shops:` schema.

Fix options: emit `to_tingbok: true` (or `false`) in the scaffold so the reviewer
flips it consciously, document it in `staging.py`'s schema docstring and the
skill, and make `tingbok_push` warn loudly when *every* item was skipped.

### 1.2 `_normalize_ean` strips all leading zeros (MEDIUM)
`scripts/ledger.py:163`: `gtin[-13:].lstrip("0")` is presumably meant to convert
a zero-padded GTIN-14 to EAN-13, but it removes *every* leading zero, so a
legitimate EAN like `0001234567895` becomes `1234567895` (no longer a valid
EAN-13, and won't match tingbok/OFF). Should strip at most `len-13`... actually
the `[-13:]` slice already does the truncation; the `lstrip("0")` should simply
be dropped (UPC-A-as-EAN-13 keeps its leading zero in most databases) or
restricted to stripping down to 12 digits for UPC-A normalisation — decide which
convention tingbok uses and match it.

### 1.3 Best-before normalisation: two implementations, opposite semantics (MEDIUM)
- `parser._normalize_bb_date()` (parser.py:114) pads `2026-06` → `2026-06-30` (*last* day of month)
- `queries.normalize_bb()` (queries.py:36) pads `2026-06` → `2026-06-01` (*first* day)

Since `queries` reads `inventory.json` (already normalised by the parser) the
divergence rarely bites today, but anything feeding `queries.normalize_bb` raw
values gets a month-off-by-29-days answer. They also disagree on the EST marker
(`bb:...:EST` suffix vs a standalone `EST` token). Pick one normaliser (the
parser's last-day semantics is the conservative one for "best before") and one
EST syntax, and have `queries` import it.

### 1.4 `check_quality.py --fix-categories` edits a generated file (MEDIUM)
`apply_fixes()` (check_quality.py:399) rewrites **inventory.json**, which is
regenerated from `inventory.md` on every `inventory-md parse` — the fixes are
silently lost on the next parse. The fix must be applied to `inventory.md`
(or this should become `inventory-md parse --fix-categories`, as the May review
already suggested).

### 1.5 Chat endpoint: retired default model, fake conversations, unbounded loop (MEDIUM)
- api_server.py:158: default model `claude-3-haiku-20240307` is retired; requests with the default will fail. Use a current alias (e.g. `claude-haiku-4-5-20251001`).
- `conversation_id` is accepted and echoed back, but every request builds a fresh single-message history (api_server.py:1091) — the API advertises statefulness it doesn't have. Either implement history or drop the field.
- The tool-use loop (api_server.py:1099) has no iteration cap; a confused model can burn tokens indefinitely. Cap it (e.g. 10 rounds).

### 1.6 Blocking work inside async endpoints (LOW-MEDIUM)
All `async def` endpoints call synchronous code: file I/O, `git pull`/`commit`/
`push` subprocesses, full re-parse of the inventory, and the *synchronous*
Anthropic client (api_server.py:1094). Any in-flight request blocks the entire
event loop — a slow `git push` freezes every other request, including `/health`.
Either make the endpoints plain `def` (FastAPI then runs them in a threadpool)
or move the heavy work to `run_in_executor`.

### 1.7 `add_child_to_item`: `parent_id` can be `None` (LOW)
api_server.py:598-625: when the parent item is found as a heading that contains
no `ID:` token, `parent_id` stays `None` and `add_item_to_container(None, ...)`
goes looking for the literal string `ID:None`. Return a clear error (or derive
an ID) instead.

### 1.8 `openprices_publish.py --suggest-from-photo` is unreachable without ledger rows (LOW)
The "nothing to publish" exit (openprices_publish.py:247) runs *before* the
`--suggest-from-photo` branch (line 252), and `--proof`/`--date`/`--shop` are
required args — so the hint mode only works when a publishable ledger slice
already exists. Hoist the suggestion branch above the row filtering.

### 1.9 Metadata regex swallows URLs and times (LOW, known limitation?)
`extract_metadata` (parser.py:159) matches `(\w+):(\S+)` style pairs, so an item
description containing `https://example.com/x` gets a bogus `https` metadata key
(and the URL removed from the name), and a time like `12:30` becomes
`{"12": "30"}`. If item texts may carry URLs or times,
consider a whitelist of known keys (the parser already special-cases most of
them) or require the parenthesised form for non-standard keys. At minimum,
document the limitation.

### 1.10 Dead code / stale artifacts (LOW)
- `src/inventory_md/__init__.py:11` hardcodes `__version__ = "0.1.0"` while the real version comes from hatch-vcs `_version.py` (currently 0.13.x). `inventory_md.__version__` lies; import from `._version` instead.
- `labels.show_date` config option is dead: `cli.labels_generate(show_date=...)` (cli.py:703) accepts it and never uses it; the date is always drawn.
- `parser.validate_inventory` (parser.py:519): the multiple-parents check can never fire — each container dict has exactly one `parent`, so `containers_with_parents[id]` only grows via duplicate IDs, which are already reported separately.
- `container["photos_link"]` is initialised to `""` and never set by the markdown-it parser, so the `photos_link`-based image-dir fallback (parser.py:407-409) is dead.
- `update_template()`/`update_makefile()` accept a `force` parameter that is ignored (cli.py:155-172); the `--force` CLI flag is a no-op.

### 1.11 Config-vs-code mismatches (LOW)
- `parser.add_container_id_prefixes()` (parser.py:434-447) hardcodes `# Intro`, `# Nummereringsregime` and the Norwegian "Oversikt..." heuristics, while `parse_inventory` reads section names from config. Non-Norwegian inventories get ID-prefixing applied inside their intro sections.
- `config.py`'s module/`find_config_files` docstrings say the CWD is searched for `inventory-md.yaml/json`, but `CONFIG_FILENAMES` (config.py:23) also picks up generic `./config.yaml` / `./config.json` — surprising in a directory that has an unrelated `config.yaml`. Either document it prominently or drop the generic names for CWD.
- `sync_eans_to_inventory.find_container_section()` (line 147) only matches `## ` headings; top-level `# ID:` containers (supported by the parser and api_server) are never found.

---

## 2. Security

### 2.1 API server has no authentication (MEDIUM, deployment-dependent)
Every mutating endpoint (`/api/items`, `/api/photos`, `DELETE /api/containers`)
and the Claude-billed `/api/chat` are open to anyone who can reach the port.
Defaults bind 127.0.0.1, but `serve --api-proxy` happily exposes them, and the
systemd units are designed for LAN access. A single shared token (header checked
by a FastAPI dependency, value in the instance `.conf`) would close this cheaply.
Related: a successful mutation auto-pushes to the git remote (api_server.py:519)
— combined with no auth, a network peer can publish commits.

### 2.2 Path sanitisation checked, no issues
`sanitize_path_component` was probed for bypasses (`....`, embedded separators,
`fo..o`, dot-prefixes): deletion-based `..` collapsing cannot reconstruct a
traversal here because separators are removed first and empty results are
rejected. No action needed.

---

## 3. Duplication

The dominant theme this round. In rough order of value to fix:

1. ~~**Language fallback chains now live in three places**~~ **FIXED 2026-06-12**: `DEFAULT_LANGUAGE_FALLBACKS` in `vocabulary.py` is now the single source of truth; `DEFAULTS["language_fallbacks"]` in `config.py` is built from it; `Config.get_language_fallback_chain` delegates to `vocabulary.get_fallback_chain`. Tingbok copy still separate (out of scope here).
2. ~~**Descendant checks**: `shopping_list._is_descendant` (shopping_list.py:284) reimplements `vocabulary.is_descendant_of`~~ **FIXED 2026-06-12**: `_is_descendant` removed; `tag_matches()` now calls `vocabulary.is_descendant_of()` directly.
3. **Lidl receipt parsing**: `ledger.lidl_receipt_to_rows` and `shop_import.parse_lidl_receipt` duplicate the line-item walk, `_KG_SUFFIX` constant included (ledger.py:55, shop_import.py:52). One should produce the canonical row and the other consume it.
4. **api_server markdown surgery**: `add_child_to_item`, `add_item_to_container`, `remove_container`, `remove_item_from_container` each re-scan lines for `ID:<x>` headings and re-derive section bounds (~4 copies of the same loop, api_server.py:574-873). Extract a `find_container_section(lines, container_id) -> (start, end, level)` helper — `sync_eans_to_inventory.py` has a fifth variant of the same logic.
5. **Quality checks**: `check_quality.check_duplicate_ids/check_missing_parents` duplicate `parser.validate_inventory`; `check_quality.load_inventory_lang` reimplements `Config`'s file discovery.
6. **Barcode plumbing**: `sync_eans_to_inventory.py` duplicates `extract_barcodes.py`'s extraction and `is_ean` (without checksum validation) and queries OFF directly while everything else goes through tingbok.
7. ~~**Private API leakage**: `queries.py:74`, `cli.py:1344` and `shopping_list.py:432` all call `vocabulary._create_broader_stubs`~~ **FIXED 2026-06-12**: renamed to `create_broader_stubs` (public) and called automatically inside `load_local_vocabulary()`; all three external call sites removed.
8. `_deep_copy` (config.py:127) reimplements `copy.deepcopy` for the limited case; fine, but the stdlib call is one line.
9. `openprices_publish.py` defines both `OSM_CACHE` (XDG cache) and `SHOP_OSM` (XDG config) — two different files both named `shop-osm.json` holding different things (geocode cache vs confirmed shop locations). Rename one.

---

## 4. Consistency and ergonomics

- **Argument parsing**: `check_quality.py` and `extract_barcodes.py` and `sync_eans_to_inventory.py` hand-roll `sys.argv` scanning (check_quality.py:482 will `IndexError` if `--tingbok-url` is the last arg) while every other script uses argparse. Converge on argparse.
- **HTTP stack**: niquests (most), requests-fallback (shop_import, extract_barcodes), raw urllib (tingbok_push, serve proxy). Pick niquests-with-fallback everywhere or accept urllib for the zero-dep scripts — but tingbok_push imports yaml anyway, so it isn't zero-dep.
- **`parse` does much more than parse**: `parse_command` (cli.py:175-480) is ~300 lines that parse, thumbnail, generate listings, fetch vocabulary, look up EANs, **push observations to tingbok** (a remote write!), and generate the shopping list. A command named `parse` silently PUT-ing to a network service is surprising; consider `--no-push`/`--offline`, and split the function into testable stages. The `niquests.Session` opened there is also never closed.
- **Performance** (matters as the inventory grows): `vocabulary.resolve_category` rebuilds the full path-alias map on every call (vocabulary.py:976) and `lookup_concept` rebuilds the label index per call — `parse_inventory_for_shopping` calls `resolve_category` once per category per item, making shopping-list generation quadratic-ish. Build the maps once and pass them down.
- **`dev` extra weight**: `dev` includes `easyocr`, which drags in torch + multi-GB CUDA wheels. A plain `pip install -e .[dev]` to run unit tests downloads gigabytes (it exhausted the disk during this review). Move `easyocr` to its existing `ocr` extra only, and let CI/test runs skip it.
- **Repo hygiene**: `uv.lock` is untracked but not gitignored — decide (commit it for reproducibility, or ignore it). Both `venv/` and `.venv/` exist locally. Editor backup files (`*~`) are correctly ignored.
- **Makefile**: personal instance names and paths (`furuset`, `solveig`, `/home/tobias/...inventory.git`) are baked into a published repo's Makefile (lines 9-10, 387-390). Works, but consider moving instance lists to an untracked include (`-include local.mk`).

---

## 5. Positives

- The staging-file schema documentation in `scripts/staging.py` is exemplary: field semantics (`price` vs `line_total`), the history of the retired schema, and the rationale all in one place, enforced by `require_flat()`.
- Dry-run-by-default with explicit `--commit` across all publishing scripts (tingbok_push, openprices_publish, off_upload, sync_eans) is exactly right for irreversible external writes.
- `ledger.py`'s append-or-enrich model with documented identity vs enrichable fields is a clean design, and `detect_removals` over git history is a clever consumption join.
- Test discipline: 623 fast tests, `filterwarnings = error`, integration tests marked and auto-skipped.
- The Dec-2025 security findings were all actually fixed, with tests.

---

## Summary table

| # | Finding | Severity | Location |
|---|---------|----------|----------|
| 1.1 | `to_tingbok` never emitted/documented → tingbok_push silently pushes nothing | High | shop_import.py, staging.py, tingbok_push.py:180 |
| 1.2 | `lstrip("0")` corrupts leading-zero EANs | Medium | ledger.py:163 |
| 1.3 | Two bb-normalisers with opposite month-padding | Medium | parser.py:114, queries.py:36 |
| 1.4 | `--fix-categories` edits generated inventory.json | Medium | check_quality.py:399 |
| 1.5 | Retired default chat model; fake conversation_id; unbounded tool loop | Medium | api_server.py:158,1091,1099 |
| 2.1 | No auth on mutating/chat endpoints; auto-push | Medium | api_server.py |
| 1.6 | Sync blocking calls in async endpoints | Low-Med | api_server.py |
| ~~3.1~~ | ~~Fallback chains ×3~~ | ~~Medium~~ | **FIXED 2026-06-12** |
| ~~3.2~~ | ~~Descendant check ×2~~ | ~~Medium~~ | **FIXED 2026-06-12** |
| ~~3.7~~ | ~~`_create_broader_stubs` private leakage ×3~~ | ~~Medium~~ | **FIXED 2026-06-12** |
| 3.3-3.6 | Duplication (Lidl parse ×2, section-scan ×5, quality checks, barcode plumbing) | Medium (aggregate) | see §3 |
| 1.7 | `parent_id=None` → searches for `ID:None` | Low | api_server.py:598 |
| 1.8 | `--suggest-from-photo` unreachable without ledger rows | Low | openprices_publish.py:247 |
| 1.10 | Stale `__version__`, dead `show_date`, dead validate branch, no-op `--force` | Low | various |
| 1.11 | Hardcoded Norwegian sections in `add_container_id_prefixes`; CWD `config.yaml` pickup | Low | parser.py:434, config.py:23 |
| 4 | argv parsing, HTTP stack mix, `parse` network side effects, quadratic category resolution, dev-extra weight | Low | see §4 |

**Recommended order of attack:** 1.1 (one real data-loss-shaped pipeline gap),
then 1.2/1.3/1.4 (small, sharp correctness fixes), then the §3 deduplication
starting with the descendant check and fallback chains, then api_server hardening
(1.5/1.6/2.1) whenever the chat server is next touched.
