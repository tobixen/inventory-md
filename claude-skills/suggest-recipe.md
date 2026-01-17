# Skill: Suggest a Recipe

Suggest recipes that prioritize using items from inventory, especially expired items that should be used soon.

## Trigger
- User asks for recipe suggestions
- User asks "what can I make with..."
- User wants to use up expired items
- `/suggest-recipe` command

## Rules

1. **Prioritize expired items**: Always check inventory for EXPIRED items first and try to incorporate them into the recipe.

2. **Ingredient list format**: Every recipe must start with an ingredient list in this format:
   ```
   ## Ingredients

   **From inventory (use first - expired):**
   - [ ] 💧 200g dried beans `ID:pinto-beans-usa` (F-12, pantry-foodbox, EXPIRED 2024-04)

   **From inventory:**
   - [ ] 1 tsp cumin `ID:cumin-mykouzina` (F-13, pantry-foodbox)

   **Needs shopping:**
   - [ ] 🛒 500g ground beef

   **Preparation needed:**
   - [ ] 💧 Beans need overnight soaking
   ```

3. **Include location and expiry**: For inventory items, always include:
   - The item ID (e.g., `ID:cardamom-aladham`)
   - Container AND parent location (e.g., F-13, pantry-foodbox)
   - Expiry date if known, with EXPIRED marker if past date

4. **Shopping mode**:
   - Default: Assume extra ingredients can be purchased (mark with 🛒)
   - If user says "no shopping": Only use items in inventory, suggest alternative recipes if needed

5. **Highlight preparation needs**:
   - 🛒 = needs to be purchased
   - 💧 = needs soaking (beans, legumes, dried mushrooms)
   - ❄️ = needs thawing
   - ⏰ = needs advance prep (marinating, etc.)

6. **Save recipes**: Save completed recipes to:
   - Solveig: `~/solveig-inventory/recipes/`
   - Furuset: `~/furusetalle9-inventory/recipes/`

7. **Mark deviations**: Note when recipe differs from traditional/original version:
   ```
   > **Note:** Traditional Greek fava uses no garlic, but it adds depth - omit if you prefer authentic.
   ```

## Location-specific Equipment

### Solveig (boat)
- **Pressure cooker**: Use for anything requiring long boiling (beans, legumes, tough meats)
- **Small gas oven**: Available but limited space, only underheat, and hard to regulate temperature
- **NO microwave**
- **NO mixer/food processor**
- **NO stick blender**
- Adapt recipes accordingly (e.g., mash by hand, use pressure cooker for beans)

### Furuset (apartment)
- Full kitchen with standard appliances
- Electric oven
- Microwave available
- Food processor/blender available

## Searching Inventory

### Using inventory.json (preferred)
The inventory.json has structured data with tags, IDs, and metadata. Generate locally if needed:

```bash
# Generate/update inventory.json from markdown
cd ~/solveig-inventory  # or ~/furusetalle9-inventory
~/inventory-system/venv/bin/inventory-system parse inventory.md
```

### Find food items sorted by expiry date
Use the `find_expiring_food.py` script to find items that should be used first (sorted by `bb:` date):

```bash
cd ~/solveig-inventory
~/inventory-system/scripts/find_expiring_food.py inventory.json          # Show expired items
~/inventory-system/scripts/find_expiring_food.py inventory.json --limit 10  # Top 10 by expiry
~/inventory-system/scripts/find_expiring_food.py inventory.json --before 2026-06  # Before date
~/inventory-system/scripts/find_expiring_food.py inventory.json --all     # All food with dates
```

### Tag hierarchy for food
- `food/legumes/beans` - dried beans, lentils
- `food/legumes/chickpeas` - chickpeas
- `food/condiment/spice` - spices
- `food/condiment/bouillon` - stock cubes
- `food/canned` - canned goods
- `food/cereal` - grains, rice, pasta
- `food/oil` - cooking oils

### Using grep (fallback)
```bash
# Find expired items
grep -n "EXPIRED" inventory.md

# Find by tag
grep -n "tag:food/legumes" inventory.md

# Find specific ingredient
grep -in "beans\|cumin\|rice" inventory.md
```

### Aliases
Check `aliases.json` for ingredient synonyms (e.g., "coriander" = "cilantro" = "koriander").

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

**Solveig galley:** Note any adaptations for boat kitchen.

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

## Workflow

### Step 1: Suggest recipes
1. Search inventory.json for EXPIRED food items
2. Identify 2-3 recipes that use those items
3. Present brief summaries with key expired items each uses
4. **Ask user which recipe(s) they want to make** using AskUserQuestion

### Step 2: After user approval
1. Save full recipe to `recipes/` directory
2. Create dated wanted-items file for shopping needs:
   ```
   ~/solveig-inventory/wanted-items-YYYY-MM-DD.md
   ```
3. include all items in wanted-items
4. Use proper tag format for shopping list integration

### Dated wanted-items format
```markdown
# Temporary Shopping Items - YYYY-MM-DD

Items needed for [recipe name].

## For [recipe name]

* tag:food/dairy/yogurt - Yogurt (for curry topping)
* tag:food/herb/coriander - Fresh coriander/cilantro
```

### Shopping list integration
After creating the dated file, remind user:
```bash
# Generate shopping list including temporary items
~/inventory-system/scripts/generate_shopping_list.py wanted-items.md inventory.md --include-dated
```

## Example Process

1. User asks for recipe
2. Search inventory.json for EXPIRED food items
3. Identify 2-3 recipes that use those items
4. **Ask user to choose** which recipe(s) to make
5. For approved recipes:
   - Search for other needed ingredients in inventory
   - Build ingredient list with full location info
   - Write instructions adapted for available equipment
   - Note any deviations from traditional recipes
   - Save to recipes/ directory
   - Create dated wanted-items file with shopping needs
6. Show shopping list command
