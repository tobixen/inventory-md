# Adding Items to the Inventory

This guide covers the data format and field conventions for inventory items. For step-by-step workflows (processing shopping receipts, processing photos, etc.) see the skill files under `claude-skills/`.

## Item Line Format

Items are bullet points inside a container section in `inventory.md`:

```markdown
## ID:container-id Container description

* category:CONCEPT ID:item-id EAN:EANCODE bb:YYYY-MM qty:N mass:Xg PRODUCT NAME
```

Fields may appear in any order but the human-readable description should come last.

## Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `category:` | Yes | What the item IS (see [Categories](#categories)) |
| `ID:` | Yes | Unique identifier for cross-referencing |
| `tag:` | Optional | Attributes: condition, ownership, colour, etc. |
| `qty:` | Optional | Count of identical items |
| `mass:` | Optional | Net mass per unit (e.g. `mass:500g`, `mass:1.2kg`) |
| `volume:` | Optional | Volume per unit (e.g. `volume:1l`, `volume:400ml`) |
| `bb:` | Food/perishables | Best-before date (see [Best-before dates](#best-before-dates)) |
| `price:` | Optional | Price at purchase point (e.g. `price:EUR:2.49/pcs`) |
| `value:` | Optional | Replacement or resale value estimate |
| `EAN:` | When known | Product barcode |
| `ISBN:` | When known | For books |

An item line may cover multiple identical items (e.g. six cans of beans). If items on the same line differ in expiry date or purchase price, split them onto separate lines.

## Categories

A **category** classifies what an item IS — `milk`, `hammer`, `trousers`, `multimeter`. Every item should have at least one.

Use the `category:` prefix. Simple labels are automatically expanded to a full SKOS path:

```markdown
* category:milk       → food/dairy/milk
* category:hammer     → tool/hand_tool/hammer
* category:potatoes   → food/vegetables/potatoes
```

**Category sources** (priority order):
1. **OFF (Open Food Facts)** — best for food (~14 K nodes, multilingual)
2. **AGROVOC** — agricultural vocabulary (produce, farming terms)
3. **DBpedia** — general knowledge (tools, equipment, non-food items)

**Syntax details:**
- Simple label: `category:potatoes` — expanded via SKOS lookup
- Full path: `category:food/vegetables/potatoes` — kept as-is
- Multiple categories: `category:oatmeal,breakfast` — comma-separated
- Hierarchical disambiguation: `category:hardware/nut` vs `category:food/nuts`

All categories should be resolvable through Tingbok:
```
https://tingbok.plann.no/api/lookup/LABEL
```

Be as specific as possible. Categories are what the item is; use `tag:` for everything else.

**Examples:**
- Dairy: `category:milk`, `category:cheese`, `category:yogurt`
- Vegetables: `category:potatoes`, `category:onions`, `category:carrots`
- Bread: `category:bread`, `category:baguette`
- Condiments: `category:soy sauce`, `category:ketchup`, `category:mayonnaise`
- Seafood: `category:salmon`, `category:tuna`, `category:shrimp`
- Tools: `category:hammer`, `category:drill`
- Clothes: `category:clothes/winter`, `category:trousers`

## Tags

Tags describe attributes of an item — condition, ownership, colour, size, intended user, etc. Use `tag:` prefix. Multiple tags are allowed.

```markdown
* category:trousers tag:old tag:children Winter trousers, size 128
* category:drill tag:brand:makita tag:condition:used Makita drill
```

Common cross-cutting tags: `tag:TODO` (needs review), `tag:condition:new`, `tag:condition:used`.

## Quantities and Measurements

- `qty:N` — number of identical items (e.g. `qty:6` for six tins)
- `mass:Xg` / `mass:Xkg` — **net mass per unit**. Use `mass:total/qty` for non-uniform items.
- `volume:Xl` / `volume:Xml` — volume per unit. Use for liquids; rarely combined with mass.

**Divisor convention** for non-uniform items: if 1.2 kg of onions were bought, counted as six, and four remain, write `qty:4 mass:1200g/6` — the average mass per onion is 200 g, giving ~800 g estimated total.

Do not round weights down to zero (e.g. 43 g of garlic → `mass:43g`, not omitted).

## Best-before Dates

Food and perishable items should include a `bb:` field.

**Formats:** `bb:YYYY-MM`, `bb:YYYY-MM-DD`, `bb:YYYY-MM-DDTHH:MM`

If the date is estimated rather than printed on the product, append `:EST`:

```markdown
* category:milk bb:2026-06-12 Whole milk 1l
* category:potatoes bb:2026-08:EST qty:4 mass:1200g/6 Potatoes
```

Note: Norwegian law distinguishes a soft "best before (often still good)" from a hard "use by (safety deadline)". No convention exists yet in this system to distinguish them.

**Typical shelf-life estimates** (for `:EST` use):
- Fresh milk: ~10 days from purchase
- Potatoes (cool/dark): ~3 months
- Chocolate: ~6–8 months
- Fresh bread: 3–5 days
- Bananas: 5–7 days

To find expiring items:
```bash
cd $INVENTORY_DIR
inventory-md parse --auto
inventory-md expiring             # items already expired
inventory-md expiring --limit 10  # top 10 soonest to expire
inventory-md expiring --before 2026-06
```

Or with the script directly:
```bash
~/inventory-md/scripts/find_expiring_food.py inventory.json
~/inventory-md/scripts/find_expiring_food.py inventory.json --limit 10
~/inventory-md/scripts/find_expiring_food.py inventory.json --before 2026-06
~/inventory-md/scripts/find_expiring_food.py inventory.json --all
```

## Price and Value

- `price:CURRENCY:AMOUNT/UNIT` — what was paid (e.g. `price:EUR:2.49/pcs`, `price:NOK:49.90/kg`)
- `value:CURRENCY:AMOUNT` — replacement or resale value estimate

When buying a bundle, record the **net per-unit price** (total paid ÷ quantity), not the list price.
