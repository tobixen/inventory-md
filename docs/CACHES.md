# Cached data

There are two caches in the system.  Both of them should be considered to be valuable as the source data may be hard to fetch.  Both of them are "global" in nature, probably we should consider something better than just storing them in a local cache file.

## EAN cache

The EAN cache is currently not used by the system itself, only by auxiliary scripts and Claude skills.  It's fetching information from different sources, including the OpenFoodFacts database.  OFF is fast, reliable and for free - as for now.  Caching aids with both offloading the OFF infrastructure and making things more robust should the OFF database be down.  However, OFF only covers food and even if the coverage is good, it does not cover all kinds of local products or shop-specific EANs - so various other sources are also used, some with strict rate limits.  There is even a Claude "skill" included that instructs Claude to manually populate and update the cache with photos of barcodes cross-checked with information from shopping receipts, and also saving price observation points.  At that point, the cache stops being "just" a cache, then it's a database in its own right.

## SKOS cache

Four sources exist for category information - it's the "package" categories included in the inventory-md package (most root categories and linking up the sources in a good category hierarchy), and then it's AGROVOC, OFF (not a SKOS database, but it does contain hierarchical categories, and inventory items with a barcode can fetch the category directly without manual work), DBpedia and Wikidata.  The other EAN sources also deliver some category information - worth investigating for additional coverage.  It seems necessary to use all of them to get good coverage of translations and hierarchical paths.  All the SKOS sources have public database lookup servers that are chronically overloaded and hard to use - so it's necessary to try the lookups again and again and build up a local cache.  Except, AGROVOC seems to be small enough that it's reasonable to download the full database.

# Consolidation idea

It would be nice to have some decentralized or federated lookup system for EANs and SKOS, but I'm considering to start with a centralized database system - a small server primarily dedicated to inventory-md users, but secondarily being open for anyone.  It will run on a known address, and all inventory-md systems will primarily query this database for information.  The database will primarily serve information from the cache - and if the data there is missing, it will try to do lookups in the various sources available.  For the EAN data, it should also be able to receive EAN data.  If the server is unavailable or cannot come up with relevant information, the local inventory-md will try probing the various sources directly.

Such a server could replace the current static database included in the script itself.

Some rate-limiting is needed when querying other sources.  A simple way may be to let the process for fetching data from the upstream sources be single-threaded/single-process and if the thread is already busy, the server should return a 503.  Alternatively, it could perhaps also work on downloaded full copies not only of the AGROVOC (~1 GB), but also of the DBpedia database (~7 GB compressed, ~100 GB uncompressed for the full dump) and Wikidata database (~80 GB compressed JSON dump, though targeted subsets can be much smaller).

If too many clients become a problem, we'll probably manage to invent some kind of rate limiting of the clients as well.

## Contributions and Security

For now, we will not allow upload of category data.  The curated "package-local" hierarchy should start off as a git-controlled database - the other sources are used in read-only mode.  Upstream contribution is worth exploring: OFF has an open API for additions, DBpedia is edited through Wikipedia, and Wikidata has a public editing API - but integrating feedback loops adds complexity and should be a separate effort.

The EAN cache may be filled up with quite some junk if we should allow arbitrary actors on the Internet to upload data without any authentication.  We should consider something - perhaps allowing data entries to be signed.  Anyway, I'm pretty sure it will take some time (weeks?  months?) until authentication may be needed.  As for now, I assume inventory-md is a project used by one single person on the planet.

# Implementation notes (added by Claude, 2026-02-15)

## Current cache location status

The SKOS cache now supports the `INVENTORY_MD_SKOS__CACHE_DIR` environment variable, and the puppet module places it under `/var/cache/inventory-md/<instance>/skos/` on the server.  Default TTL was increased from 30 to 60 days.

The EAN cache (`ean_cache.json`) is still a flat JSON file in the working directory, managed by `scripts/extract_barcodes.py`.  It has no env var override yet.  Since the EAN cache is evolving into a database (with manually curated entries, price history, receipt mappings), it probably deserves a more structured storage format before being made configurable - a flat JSON file that gets fully rewritten on every save won't scale well with concurrent access from a server.

## Thoughts on the consolidation server

The single-threaded upstream fetcher with 503 is elegant - it naturally rate-limits without needing complex queuing or coordination.  A few considerations:

- **Local database subsets**: Full DBpedia/Wikidata dumps are huge, but the server only needs the class hierarchy + multilingual labels.  Targeted extracts (e.g., all `skos:broader`/`P279` triples + `rdfs:label` in ~10 languages) could be 1-5 GB each - very manageable alongside the existing AGROVOC N-Triples file.
- **Pre-warming**: Rather than only caching on first request, the server could pre-warm popular lookups from the package vocabulary's ~260 concepts.  This would make the first client experience much smoother.
- **EAN contribution model**: Even before authentication, an append-only log with IP attribution and timestamps would let you audit and roll back bad data.  Signing can come later.
- **Cache sharing between instances**: On a multi-instance host (like broxbox05 with furuset/solveig/demo), a shared lookup server would naturally deduplicate - all three instances query the same categories and EANs.  This is a stronger argument for the server than just caching locally per instance.
