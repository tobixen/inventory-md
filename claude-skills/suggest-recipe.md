# Skill: Suggest a Recipe

Suggest recipes that prioritize using items from the inventory, especially items nearing or past their best-before date.

## Trigger
- User asks for recipe suggestions
- User asks "what can I make with..."
- User wants to use up expired or soon-to-expire items
- `/suggest-recipe` command

## Rules

1. **Prioritize expired items**: Always check inventory for EXPIRED items first and try to incorporate them.

2. **Ingredient list format**: Every recipe must start with an ingredient list in this format:
   ```
   ## Ingredients

   **From inventory (use first - expired):**
   - [ ] 💧 200g dried beans `ID:pinto-beans` (F-12, EXPIRED 2024-04)

   **From inventory:**
   - [ ] 1 tsp cumin `ID:cumin-jar` (F-13)

   **Needs shopping:**
   - [ ] 🛒 500g ground beef

   **Preparation needed:**
   - [ ] 💧 Beans need overnight soaking
   ```

3. **Include location and expiry**: For inventory items, always include the item ID, container, and expiry date (with EXPIRED marker if past).

4. **Shopping mode**:
   - Default: Assume extra ingredients can be purchased (mark with 🛒)
   - If user says "no shopping": Only use inventory items; suggest alternatives

5. **Highlight preparation needs**:
   - 🛒 = needs to be purchased
   - 💧 = needs soaking
   - ❄️ = needs thawing
   - ⏰ = needs advance prep (marinating, etc.)

6. **Mark deviations** from traditional recipes:
   ```
   > **Note:** Traditional Greek fava uses no garlic, but it adds depth — omit if you prefer authentic.
   ```

## Searching Inventory

### Using inventory.json (preferred)

```bash
cd $INVENTORY_DIR
inventory-md parse --auto   # regenerate inventory.json
```

### Find food items sorted by expiry date

```bash
~/inventory-md/scripts/find_expiring_food.py inventory.json           # expired items
~/inventory-md/scripts/find_expiring_food.py inventory.json --limit 10
~/inventory-md/scripts/find_expiring_food.py inventory.json --before 2026-06
~/inventory-md/scripts/find_expiring_food.py inventory.json --all
```

### Using grep (fallback)

```bash
grep -n "EXPIRED" inventory.md
grep -n "category:food/legumes" inventory.md
grep -in "beans\|cumin\|rice" inventory.md
```

## Workflow

### Step 1: Suggest recipes
1. Search inventory for EXPIRED food items
2. Identify 2–3 recipes that use those items
3. Present brief summaries
4. **Ask user which recipe(s) to make** using AskUserQuestion

### Step 2: After user approval
1. Save full recipe to `$INVENTORY_DIR/recipes/`
2. Create a dated wanted-items file for shopping needs:
   ```
   $INVENTORY_DIR/wanted-items-YYYY-MM-DD.md
   ```

### Dated wanted-items format
```markdown
# Temporary Shopping Items - YYYY-MM-DD

Items needed for [recipe name].

## For [recipe name]

* category:yogurt - Yogurt (for curry topping)
* category:coriander - Fresh coriander/cilantro
```

## Recipe File Format

```markdown
# Recipe Name

Brief description mentioning which expired items it uses.

## Ingredients

**From inventory (use first - expired):**
- [ ] ...

**From inventory:**
- [ ] ...

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
