# Cached data

There are two caches in the system.  Both of them should be considered to be valuable as the source data may be hard to fetch.  Both of them are "global" in nature, probably we should consider something better than just storing them in a local cache file.

## EAN-cache

The EAN-cache is currently not used by the system itself, only by auxillary scripts and Claude skills.  It's fetching information from different sources, including the OpenFoodFacts database.  OFF is fast, reliable and for free - as for now.  Caching aids with both offloading the OFF infastructure and making things more robust should the OFF database be down.  However, OFF only covers food and even if the coverage is good, it does not cover all kind of local products or shop-specific EANs - so various other sources are also used, some with strict rate limits.  There is even a claude "skill" included that instructs claude to manually populate and update the cache with photos of bar-codes cross-checked with information from shopping receipts, and also saving price observation points.  At that point, the cache stops being "just" a cache, then it's a database in it's own right.

## SKOS cache

Four sources exists for category information - it's the "package" categories included in the inventory-md package (most root categories and linking up the sources in a good category hierarchy), and then it's AGROVOC, OFF (not a SKOS database, but it does contain hierarchical categories, and inventory with a barcode can fetch the category directly without manual work), DBPedia and Wikidata.  TODO: the other EAN sources also delivers some category information, we should look into that as well.  It seems necessary to use all of them to get good coverage of translations and hierachical paths.  All the SKOS source have public database lookup servers that are chronically overloaded and hard to use - so it's necessary to try the lookups again and again and build up a local cache.  Except, AGROVOC seems to be small enough that it's reasonable to download the full database.

# Consolidation idea

It would be nice to have some decentralized or federated lookup system for EANs and SKOS, but I'm considering to start with a centralized database system - a small server primarily dedicated inventory-md users, but secondarily being open for anyone.  It will run run on a known address, and all inventory-md systems will primarily query this database for information.  The database will primarily serve information from the cache - and if the data there is missing, it will try to do lookups in the various sources available.  For the EAN data, it should also be able to receive EAN-data.  If the server is unavailable or cannot come up with relevant information, the local inventory-md will try probing the various sources directly.

Such a server could replace the current static database included in the script itself.

Some rate-limiting is needed when querying other sources.  A simple way may be to let the process for fetching data from the upstream sources be a single-treaded/single-process and if the thread is already busy, the server should return a 503.  Alternatively, it could perhaps also work on downloaded full copies not only of the AGROVOC (~1G), but also of the dbpedia database (7G?  TODO: check it up) and wikidata database (TODO: how big?).

If too many clients becomes a problem, we'll probably manage to invent some kind of rate limiting of the clients as well.

## Contributions and Security

As for now, We will not allow upload of category data.  The curated "package-local" hierarchy should start off as a git-controlled database - the other sources are used in read-only mode.  TODO: do some research on how dbpedia, OFF and wikidata is curated and if it makes sense to have some kind of feedback loops for contributing data upstream.

The EAN cache may be filled up with quite some junk if we should allow arbitrary actors on the Internet to upload data without any authentication.  We should consider something - perhaps allowing data entries to be signed.  Anyway, I'm pretty sure it will take some time (weeks?  months?) until authentication may be needed.  As for now, I assume inventory-md is a project used by one single person on the planet.
