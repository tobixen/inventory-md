# Category/Vocabulary TODO

Known issues and improvement areas for the SKOS vocabulary and category hierarchy system.

## Quick introduction

There are four components involved here:

* ~/tingbok - supposed to be the authorative source of categorization information, running as a service from tingbok.plann.no, fetching information from various sources.  Currently the user needs to deploy code changes.
* ~/inventory-md - the "inventory system", basically a CLI.
* ~/solveig-inventory - an inventory.  Data is in inventory.md, when running `inventory-md parse --auto` it will extract the data into inventory.json and build vocabulary.json.  Most category-problems observed by the user can be found by digging into vocabulary.json
* ~/furuset-inventory - another inventory instance.

We're trying to keep the same version numbers on tingbok and plann.  The project is still in a 0.x development phase, and I'm probably the only user, so we don't need to care about backward compatibility if it makes sense to change APIs and making breaking changes,

## Core ideas

* The category system is hierarchical.  food/spices/cumin could be a node.
* The tingbok has a vocabulary.yaml describing the root nodes and parts of the "inventory system" category tree.  This file should be slim, it shouldn't contain information available from other sources.  It's also not complete, it's just a starting point.
* Every category should have at least one path, but may have several paths.  food/vegetables/potato snd food/staples/potato is the same category, but with two paths.
* Tingbok should query multiple sources to find the relevant paths, translations, alternative lables and a good description of every category.

## Multiple-sources (important!)

There are still some remaining work here and quite some regressions after the latest rounds of work on tingbok and inventory-md.  Possibly the tingbok API needs to be changed a bit to reflect that tingbok is now supposed to do the full work of looking up categories?

I think that instead of fetching https://tingbok.plann.no/api/vocabulary it should fetch categories by a canonical "tingbok URL", starting with the virtual _root category.

I think there is no such thing as a canonical "tingbok URL" now.  This needs to be fixed.

Some of the categories in the current tingbok vocabulary.yaml has an uri field with a value, this infomation may safely be overwritten by the canonical tingbok URL

The source URIs should probably always be given with https rather than http, since https is the standard nowadays.

Recently a prune-vocabulary command was introduced to tingbok to remove redundant labels from vocabulary.yaml, but it does not remove `altLabel` - this should be fixed.

Some notes I made while investigating the solveig inventory:

* https://tingbok.plann.no/api/skos/lookup?label=clothing should probably not default to only showing agrovoc it should probably do a lookup in all sources. (this may be moot, do we need the lookup api call at all?)
* ~~(in solveig-inventory / tingbok vocabulary) "clothing" is missing quite some altlabels, including "costume".~~
  **Fixed**: `GET /api/vocabulary` now merges `altLabel` from DBpedia (skos:altLabel), Wikidata (aliases), AGROVOC (altLabel), and OFF (synonyms).
* ~~(in solveig-inventory) the cumin category was previously (v0.7.0) recognized as a subcategory of spice - now it's not.~~
  **Fixed**: `parse --auto` now calls `resolve_categories_via_tingbok()` for orphaned labels, querying `/api/skos/hierarchy` across AGROVOC/DBpedia/Wikidata.
* (in solveig-inventory) buillion is a subcategory of spice - needs verification after the above fix.
* "Categories by source" in the inventory UI — should be dynamically generated from tingbok data rather than hardcoded in inventory-md.

## Tingbok cache gracetime

The items in the cache currently has a 60 day time to live.

I think we should also have a quite long - maybe a years grace time - meaning that items passed the time to live should not be deleted from the cache.

The ideal logic goes like this:

0. We get some request from an end user
1. A lookup finds that the cache content is old
2. We try fetching an update from the upstream source
3. If we get a quick response from the upstream source, everything is fine.  If not, we deliver old data from the cache and continue trying to update the cache in the background.

## Google Product Taxonomy (GPT) as a future source

~~GPT is fully implemented in tingbok~~: `gpt.py` service, `gpt:{id}` URI scheme,
`download-taxonomy --gpt` CLI, wired into `populate-uris` and startup label fetching.
54 `gpt:` URIs already in vocabulary.yaml.

**Remaining:**

0) How does the GPT compare to the tingbok vocabulary?  Are there tingbok concepts
   without any `gpt:` URI that should have one?  Perhaps remap some categories.
   (This requires manual review against the GPT hierarchy.)

1) "Categories by source" in the inventory UI is missing GPT — but this is part of
   the broader "categories by source should be dynamically generated from tingbok"
   work, covered under "Remove redundant logic from inventory-md" below.

## Move "memory" information into docs

There is a file ~/.claude/projects/-home-tobias-inventory-system/memory - useful information should exists in the docs (tingbok and inventory-md) rather than in the memory file.  It's needed to look through and check if the old file maps well with the current realities.  The list below contains my comments after looking through the file.  My opinions below may involve changes in the code, both tingbok and inventory-md - small changes can be done immediately, big changes should be added to this TODO-CATEGORIES-document.

* "source priority" - I think we should treat the sources more or less equally, rather than having them as a prioritized list.
* There is no "package vocabulary" anymore, it's the Tingbok vocabulary
* There is nothing special about Wikidata - it's just one out of several sources
* "Plant-based foods and beverages" is not the same as "food", it is a sub-category of food.
* Probably all source-specific logic (`off.py`, SPARQL-logic, etc) should be removed from inventory-md and kept only in tingbok
* Lots of work has been done on multi-source tracking in the tingbok project, so the entire section is probably outdated.
* Tingbok should have some built-in rate-limiting handling.  Niquests comes with some built-in logic for this ... check Retry in niquests.packages.urllib3.util

## ~~Remove redundant logic from inventory-md~~ **Done** (2026-03-06)

(but quite some regressions are observed after this was done)

`skos.py`, `off.py`, and ~2300 lines of hierarchy/translation logic removed from
inventory-md.  The `inventory-md skos` CLI command and `--skos`/`--hierarchy` parse
flags are gone.  Remaining source references in `vocabulary.py` are limited to
`_uri_to_source()` (URI-to-source-name mapping) and the language fallback logic
(pure functions, no network calls).

The fallback to the old direct-source approach is replaced with:

## Create a new optional tingbok fallback

tingbok could be an optional dependency of inventory-md.  If the tingbok library exists and tingbok.plann.no doesn't respond, use the tingbok libraries directly.

We then need to rethink what dependencies should be optional and not, like, mcp is clearly not needed for this purpose

## Still some categories missing translations

This is probably not much relevant more, needs manual verification.

For categories that exist in the local vocabulary but have no matches in the other category sources (like root node "Health & Safety"), there must be translations locally in the package vocabulary.

~~household/books seems to be missing Norwegian translation and have a Danish translation.~~
**Fixed**: Multi-source tracking (`source_uris`) now finds supplementary DBpedia/Wikidata
URIs for concepts that only matched via OFF/AGROVOC, so translation phases can query all
available sources. Books now gets Norwegian from Wikidata even when originally matched via
DBpedia.
