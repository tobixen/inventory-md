# Cached data

There are two caches in the system.  Both of them should be considered to be valuable as the source data may be hard to fetch.  Both of them are "global" in nature, probably we should consider something better than just storing them in a local cache file.

## EAN cache

The EAN cache is currently not used by the system itself, only by auxiliary scripts and Claude skills.  It's fetching information from different sources, including the OpenFoodFacts database.  OFF is fast, reliable and for free - as for now.  Caching aids with both offloading the OFF infrastructure and making things more robust should the OFF database be down.  However, OFF only covers food and even if the coverage is good, it does not cover all kinds of local products or shop-specific EANs - so various other sources are also used, some with strict rate limits.  There is even a Claude "skill" included that instructs Claude to manually populate and update the cache with photos of barcodes cross-checked with information from shopping receipts, and also saving price observation points.  At that point, the cache stops being "just" a cache, then it's a database in its own right.

## SKOS cache

Four sources exist for category information - it's the "package" categories included in the inventory-md package (most root categories and linking up the sources in a good category hierarchy), and then it's AGROVOC, OFF (not a SKOS database, but it does contain hierarchical categories, and inventory items with a barcode can fetch the category directly without manual work), DBpedia and Wikidata.  The other EAN sources also deliver some category information - worth investigating for additional coverage.  It seems necessary to use all of them to get good coverage of translations and hierarchical paths.  All the SKOS sources have public database lookup servers that are chronically overloaded and hard to use - so it's necessary to try the lookups again and again and build up a local cache.  Except, AGROVOC seems to be small enough that it's reasonable to download the full database.

# Tingbok — centralised lookup service

The consolidation server described above is now implemented as
[tingbok](https://github.com/tobixen/tingbok), running at
**https://tingbok.plann.no**.

inventory-md queries tingbok by default for the package vocabulary.  If
tingbok is unreachable, it falls back to the bundled `vocabulary.yaml`
transparently.  SKOS and EAN lookups via tingbok are planned for later
phases.

## Configuration

The tingbok URL is configured under the `tingbok` key:

```yaml
# inventory-md.yaml / inventory-md.json
tingbok:
  url: https://tingbok.plann.no   # default — omit to use the public server
```

To point at a local instance (e.g. for development):

```yaml
tingbok:
  url: http://localhost:5100
```

To disable tingbok entirely and always use the bundled vocabulary:

```yaml
tingbok:
  url: ""   # or "false"
```

The same setting can be overridden with the environment variable
`INVENTORY_MD_TINGBOK__URL`.

## Roadmap

- **Phase 1 (done):** Vocabulary endpoint — tingbok serves the package
  vocabulary; inventory-md fetches it on startup.
- **Phase 2 (planned):** SKOS lookups — migrate AGROVOC/DBpedia/Wikidata
  lookup and caching logic from `skos.py` into tingbok; inventory-md falls
  back to direct upstream queries if tingbok is unavailable.
- **Phase 3 (planned):** EAN lookups — migrate barcode lookup and caching
  from `scripts/extract_barcodes.py` into tingbok.

Some rate-limiting will be needed when querying upstream sources.  A
single-threaded upstream fetcher returning 503 when busy is the planned
approach — it naturally rate-limits without complex queuing.

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
