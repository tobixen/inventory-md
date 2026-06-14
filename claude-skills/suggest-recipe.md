# Skill: Suggest a Recipe

Suggest recipes that prioritize using items from the inventory, especially items nearing or past their best-before date.

## Rules

1. **Prioritize expiring items**: See below on how to sort out expired and soon-expiring food.  Priority spending food in this order:  food that has expired few days ago, food that will expire in some few days, food that expired long ago, food that will expire in the far future.

2. **Consider a balanced meal**: A good meal should include vegetables, proteins (personal preferences matters - some are vegans, others crave meat in every meal) and staples (potatoes, bread, rice, pasta or other cheap fillers), sometimes a sauce may be needed.  Exceptions do apply (particularly if no shopping is possible).

3. **Ingredient list format**: Every recipe must start with an ingredient list in this format:
   ```
   ## Ingredients

   - [ ] 💧 200g dried beans `ID:pinto-beans` (location: F-12, bb:2024-04) ⚠️ expired — quality check before use
   - [ ] 1 tsp cumin `ID:cumin-jar` (location: F-13, bb:2026-08)
   - [ ] 🛒 500g ground beef (expected location: fridge)

   **Preparation needed:**
   - [ ] 💧 Beans need overnight soaking
   ```

   Sort things by location (expected location for things that needs shopping).

4. **Include location and expiry**: For inventory items, always consult the json file and include the item ID, container, and best-before date (the `find_expiring_items.py` should present all this data).  Add `⚠️ expired — quality check before use` for expired items; do not sort expired items into a separate section.  Skip location for items that needs to be shopped.

5. **Shopping mode**:
   - Default: Assume extra ingredients can be purchased (mark with 🛒)
   - If user says "no shopping": Only use inventory items; suggest alternatives

6. **Highlight preparation needs**:
   - 🛒 = needs to be purchased
   - 💧 = needs soaking
   - ❄️ = needs thawing
   - ⏰ = needs advance prep (marinating, etc.)

7. **Mark deviations** from traditional recipes:
   ```
   > **Note:** Traditional Greek fava uses no garlic, but it adds depth — omit if you prefer authentic.
   ```

8. **Consider timing**.  Avoid surprises like "Fry on strong heat for 30s while constantly stirring" followed with a point "add three finely chopped onions".  Sometimes it may be needed to chop vegetables and other things before frying things, other times the chopping can be done in parallell.

9. **Quantity should be repeated in the instruction**.  Rather than "add the chopped onions", write "add one medium-sized (~120g) chopped onion"

## Searching Inventory

### Using inventory.json (preferred)

```bash
cd $INVENTORY_DIR
inventory-md parse --auto   # regenerate inventory.json
```

### Find food items sorted by expiry date

```bash
inventory-md expiring inventory.json            # expired items
inventory-md expiring inventory.json --limit 10
inventory-md expiring inventory.json --before 2026-06
inventory-md expiring inventory.json --all
inventory-md expiring inventory.json --food     # food only (uses vocabulary.json)
```

### Look up specific items (id, location, best-before)

`expiring` only lists items that *have* a best-before date. To resolve the
location/bb of the exact items you want in an ingredient list — including fresh
produce with no bb yet (e.g. just-bought asparagus, onions, tomatoes) — use:

```bash
inventory-md lookup inventory.json --id bacon-pikok --id asparagus-2026-06-06
inventory-md lookup inventory.json --match onion --match tomato   # substring on id+name
```

(`scripts/find_expiring_items.py` and `scripts/lookup_items.py` remain as thin
wrappers around these subcommands and accept the same arguments.)

## Workflow

### Step 1: Suggest recipes
1. Search inventory for expiring food items
2. Identify 2–3 recipes that use those items
3. Present brief summaries
4. **Ask user which recipe(s) to make** using AskUserQuestion

### Step 2: After user approval
1. Save full recipe to `$INVENTORY_DIR/recipes/` with filename `YYYY-MM-DD-recipe-name.md` (date first)
2. Create a dated wanted-items file for shopping needs:
   ```
   $INVENTORY_DIR/wanted-items-YYYY-MM-DD.md
   ```

### Dated wanted-items format

Filename: `wanted-items-YYYY-MM-DD-recipe-name.md`

```markdown
# Items needed for [recipe name] [date].

* category:yogurt - Yogurt (for curry topping)
* category:coriander - Fresh coriander/cilantro
```

The purpose of the file is to aid the generation of the shopping list.  The shopping list generator goes by category, so the category field is the most important.  **Use a specific category**.  For instance, if the receipt needs onions, then use `category:onion`.  If `category:vegetables` is used, the shopping list generator may consider that it's no need to buy onions since we have carrots in the fridge).

The file should be reusable, so it should contain all items needed, both those needed to be purchased and those already in the inventory.  (this will also remind me to buy *more* onions if all the onions I have will be used in the cooking).

Resolve the category with the vocabulary tooling.

```bash
inventory-md vocabulary lookup lemon
inventory-md vocabulary lookup "sweet pepper"
inventory-md vocabulary lookup "onion"
```

## Recipe File Format

Filename: `YYYY-MM-DD-recipe-name.md`

```markdown
# Recipe Name

Brief description.

## Ingredients

**From inventory:**
- [ ] ... `ID:xxx` (location, bb:date) ⚠️ expired — quality check before use
- [ ] ... `ID:xxx` (location, bb:date)

**Needs shopping:**
- [ ] 🛒 ...

**Preparation needed:**
- [ ] 💧/⏰ ...

## Equipment

Note any adaptations for available kitchen equipment.

## Instructions

1. Step by step...

## Variations

> **Note:** Deviations from traditional recipe...

## Items used from inventory

| Item | ID | Location | Status |
|------|-----|----------|--------|
| ... | ... | ... | EXPIRED/OK/bb:date |

---

*Generated YYYY-MM-DD to use expired X from Y*
```
