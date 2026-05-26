# Category/Vocabulary TODO

Known issues and improvement areas for the SKOS vocabulary and category hierarchy system.

## Quick introduction

There are four components involved here:

* ~/tingbok - supposed to be the authorative source of categorization information, running as a service from tingbok.plann.no, fetching information from various sources.  Currently the user needs to deploy code changes.
* ~/inventory-md - the "inventory system", basically a CLI.
* ~/solveig-inventory - an inventory.  Data is in inventory.md, when running `inventory-md parse --auto` it will extract the data into inventory.json and build vocabulary.json.  Most category-problems observed by the user can be found by digging into ~/solveig-inventory/vocabulary.json
* ~/furuset-inventory - another inventory instance.

We're trying to keep the same version numbers on tingbok and plann.  The project is still in a 0.x development phase, and I'm probably the only user, so we don't need to care about backward compatibility if it makes sense to change APIs and making breaking changes,

## Core ideas

* The category system is hierarchical.  food/spices/cumin could be a node.
* The tingbok has a vocabulary.yaml describing the root nodes and parts of the "inventory system" category tree.  This file should be slim, it shouldn't contain information available from other sources.  It's also not complete, it's just a starting point.  The concepts in the vocabulary should be identified by a cannonical Tingbook URL.  We should also consider to have a canonical, though not guaranteed persistent Tingbok-URL for cached concepts.
* Every category should have at least one path, but may have several paths.  food/vegetables/potato snd food/staples/potato is the same category, but with two paths.
* Tingbok should query multiple sources to find the relevant paths, translations, alternative lables and a good description of every category.

## Shopping list category match problem, name conflicts and IDs

### Problems we'd like to solve

* The find-expired script is not able to understand that soybeans are food
* The shopping list generator currently has some logic for resolving and matching categories.  I think it belongs to a "higher level".  I don't want a lot of local algorithms in the shopping list generator - matching categories is a general problem.  We're doing it in the javascript too.
* There still seems to be some confusion that food/legumes/soy-beans is a different category than soy-beans - it shouldn't be
* At the other hand, in the Norwegian inventory, jul/belysning is NOT the same as belysning.  (jul/julebelysning could be an option, but it looks a bit redundant.  Or perhaps just julebelysning)

### Having IDs on the categories

GPT has numeric IDs on their product categories, Agrovoc and Wikidata has some kind of uid-scheme.  Do we need something similar for the categories that are in the vocabulary?  For the categories that are not in the vocabulary, it's not possible to have a persistent permanent ID, but we could possibly have temporary IDs on such categories.  Such categories are supposed to stay in cache as long as there are inventories using the category.

### Having "canonical names" on the categories

A category may have many names, even when disregarding languages, even when disregarding aliases and synonyms ...

* Potato - potatoes - food/vegetable/potatoes - food/staples/potatoes

* Seal meat - food/meat/seal

* Plush seal toy - toy/stuffed/seal - plush seal

* hardware/plumbing/seal - oring

Under ~/furusetalle9-inventory/inventory.md I have a Norwegian inventory.  It has categories like "klær/vinter", "jul/belysning", etc - it could be redone into "klær/vinterklær" (I already changed that one), "jul/julebelysning", etc, but I like it as it was.

I don't want to use full path in the inventory list, and I also don't want to use some random-looking IDs - and the category should be localized - but it could be an idea to enforce some kind of "canonical names".  I think it could make sense to let the rule be "take the as many legs of the category tree as needed, starting from the end".  So soy-beans, potatoes, but meat/seal, toy/stuffed/seal, plumbing/seal, etc.

## Split/combine source concepts?

Some sources lump together things (spices + herbs, underwear and socks), while others keep it separated.  Sometimes such a combination is just for the category tree (in GPT, "Underwear and socks" have subcategories socks and underwear).  Sometimes we want the Tingbok vocabulary category to combine multiple source URIs from the same source.  Specifically, I want "long johns" (Q2472769) and "longs" (Q56303142 in wikidata) to be combined into one category in Tingbok.  The other cases can probably be handled in the vocabulary as it is - if two different Tingbok vocabulary categories references the same source URI, we probably want to create a parent category referencing the source.  If we want to create an "underwear and socks" node in the hierarchy, we can define that in vocabulary, exclude other sources than GPT, and let socks and underwear be children of it.

## Clothing — needs verification

Fixed previously (restore of tingbok-sourced concepts overwritten by inventory-sourced stubs).
**Still todo**: needs to be verified fixed by re-running `inventory-md parse --auto` against a tingbok server that returns 200 for `/api/vocabulary`.

## Nuts — needs verification

Two problems were fixed: flat food nuts hierarchy (peanuts/cashews not under `food/nuts`) and hardware nuts miscategorised.
**Still todo**: needs to be verified fixed.

## Tingbok hard-coded vocabulary vs other concepts

**Remaining**:
* The caching for `/api/lookup` results is currently done by the underlying SKOS service
  (per concept/label files in `~/.cache/tingbok/skos/`).  Separating lookup results into
  their own cache directory for easier inspection was requested but not yet done.
* Translation warnings ("bedding" = animal litter vs. household bedding) should be
  generated at lookup time and written to a separate YAML/JSON file on the server.

## EAN-support from the parse script

**Remaining**: auto-write `category:xxx` back into the inventory markdown file.

## EAN update support

Currently price and other information on receipts is correlated with photos of bar-codes, this is at the moment a Claude-based effort (see inventory-md/claude-skills).  Now that the database should stay at Tingbok, we need an interface for updating Tingbok.  The skill should be updated to reflect this (is it "cheapest" to do those updates via REST or MCP?).

## Multiple-sources (important!)

There are still some remaining work here and quite some regressions after the latest rounds of work on tingbok and inventory-md.  Possibly the tingbok API needs to be changed a bit to reflect that tingbok is now supposed to do the full work of looking up categories?

I think that instead of fetching https://tingbok.plann.no/api/vocabulary it should fetch categories by a canonical "tingbok URL", starting with the virtual _root category.

I think there is no such thing as a canonical "tingbok URL" now.  This needs to be fixed.
See `~/tingbok/docs/canonical-urls.md` for the proposed URL scheme and a redesigned
batch-resolve vocabulary API.

Some of the categories in the current tingbok vocabulary.yaml has an uri field with a value, this infomation may safely be overwritten by the canonical tingbok URL.

The source URIs should probably always be given with https rather than http, since https is the standard nowadays.

Some notes I made while investigating the solveig inventory:

* https://tingbok.plann.no/api/skos/lookup?label=clothing should probably not default to only showing agrovoc it should probably do a lookup in all sources. (this may be moot, do we need the lookup api call at all?)
* (in solveig-inventory) buillion is a subcategory of spice - needs verification after previous cumin fix.
* "Categories by source" in the inventory UI — should be dynamically generated from tingbok data rather than hardcoded in inventory-md.

## Create a new optional tingbok fallback

tingbok could be an optional dependency of inventory-md.  If the tingbok library exists and tingbok.plann.no doesn't respond, use the tingbok libraries directly.

We then need to rethink what dependencies should be optional and not, like, mcp is clearly not needed for this purpose

## Google Product Taxonomy (GPT) as a future source

GPT is fully implemented in tingbok: `gpt.py` service, `gpt:{id}` URI scheme,
`download-taxonomy --gpt` CLI, wired into `populate-uris` and startup label fetching.
54 `gpt:` URIs already in vocabulary.yaml.

**Remaining:**

0) How does the GPT compare to the tingbok vocabulary?  Are there tingbok concepts
   without any `gpt:` URI that should have one?  Perhaps remap some categories.
   (This requires manual review against the GPT hierarchy.)

1) "Categories by source" in the inventory UI is missing GPT — but this is part of
   the broader "categories by source should be dynamically generated from tingbok"
   work, covered under "Multiple-sources" above.

## Move "memory" information into docs

There is a file ~/.claude/projects/-home-tobias-inventory-md/memory - useful information should exists in the docs (tingbok and inventory-md) rather than in the memory file.  It's needed to look through and check if the old file maps well with the current realities.  The list below contains my comments after looking through the file.  My opinions below may involve changes in the code, both tingbok and inventory-md - small changes can be done immediately, big changes should be added to this TODO-CATEGORIES-document.

* "source priority" - I think we should treat the sources more or less equally, rather than having them as a prioritized list.
* There is no "package vocabulary" anymore, it's the Tingbok vocabulary
* There is nothing special about Wikidata - it's just one out of several sources
* "Plant-based foods and beverages" is not the same as "food", it is a sub-category of food.
* Probably all source-specific logic (`off.py`, SPARQL-logic, etc) should be removed from inventory-md and kept only in tingbok
* Lots of work has been done on multi-source tracking in the tingbok project, so the entire section is probably outdated.
* Tingbok should have some built-in rate-limiting handling.  Niquests comes with some built-in logic for this ... check Retry in niquests.packages.urllib3.util

## Still some categories missing translations

Needs manual verification — possibly no longer relevant given current multi-source tracking.

For categories that exist in the local vocabulary but have no matches in the other category sources (like root node "Health & Safety"), there must be translations locally in the package vocabulary.
