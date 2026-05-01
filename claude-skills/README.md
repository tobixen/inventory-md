# Claude Skills for inventory-md

These skill files describe workflows for using an AI assistant to maintain an inventory managed by this system. They are generic — they use `$INVENTORY_DIR` and `$PHOTO_DIR` as placeholders for your actual paths.

Create personal skill files under `~/.claude/skills/` that reference these guides and add your instance-specific paths, tools, and conventions. See the [INSTALLATION guide](../docs/INSTALLATION.md) for setup instructions.

## Available skills

| File | Purpose |
|------|---------|
| `process-shopping.md` | Process a shopping receipt and update the inventory |
| `process-inventory-photos.md` | Process photos of containers/locations and update the inventory |
| `suggest-recipe.md` | Suggest recipes prioritising soon-to-expire inventory items |

## Item format reference

For categories, tags, quantities, best-before dates, and other field conventions, see [`docs/ADDING-ITEMS.md`](../docs/ADDING-ITEMS.md).

For general maintenance tasks, see [`docs/MAINTENANCE.md`](../docs/MAINTENANCE.md).
