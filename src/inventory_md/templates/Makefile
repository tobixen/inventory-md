# DO NOT EDIT — this file is managed by inventory-md and will be overwritten.
# To update to the latest version: make update-makefile
# To customise behaviour, set variables before including, or add targets after.
INVENTORY_MD ?= inventory-md

# All files that feed into parse --auto
PARSE_INPUTS := inventory.md $(wildcard wanted-items.md wanted-items-*.md)

.PHONY: all search.html update-makefile help

all: inventory.json search.html update-makefile

# Parse: generates inventory.json, vocabulary.json and shopping-list.md in one go.
# Runs only when inventory.md or any wanted-items file is newer than inventory.json.
inventory.json: $(PARSE_INPUTS)
	$(INVENTORY_MD) parse --auto inventory.md

# search.html and Makefile: commands are silent no-ops when already current
search.html:
	$(INVENTORY_MD) update-template

update-makefile:
	$(INVENTORY_MD) update-makefile

help:
	@echo "Inventory Makefile"
	@echo ""
	@echo "  make                 Parse if inputs changed, refresh search.html and Makefile"
	@echo "  make update-makefile   Update this Makefile to latest package version"
