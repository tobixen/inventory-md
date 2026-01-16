# Inventory System

This is a flexible "vibe-coded" inventory management system.

It started out with the inventory kept as simple hand-written markdown files, then I started taking some photos, then I asked Claude for suggestions on how to improve the searchability and user interface - and it has grown from there.

## Problems

I **hate throwing things**.  My wife also don't like to throw things.  The weirdest thing will suddenly become useful at some point - but only if you know what you have and where to find it!  We've ended up with so much thrash that whatever we need, it's way easier to buy it in the shop than to find the thing we need.  Only by having a searchable database, the thrash is converted to useful stash!

We also hate throwing food.  I now take notes of the expiry date of all the food I'm buying and stuffing it into the fridge and food storages.  This way I can keep an overview of what food is expiring.  I've started asking Claude for suggestions on how to use the outdated food - some of the recipes it has come up with has been delicious!

I've also added a shopping list generator.

## Yet Another Inventory System?

Other systems exist - see [docs/comparison-with-other-systems.md](docs/comparison-with-other-systems.md) for a detailed comparison.

### Database in MarkDown format!

Yes, you heard right!  The biggest difference between this system and other systems is that the **database is a git-backed MarkWown file** - because that's what I started with.  At some point I sat down and wondered - "does this still make sense?" - and actually, for me it does!  I added the possibility to edit the inventory through the web interface, **but I never used it**.  Most of the time I use "Claude Code" to update it for me, except for that I still prefer editing the database from my text editor.  Even though the MarkDown may end up beeing quite cluttered with metadata, I still prefer to work with the markdown as compared to working with yaml or json in the text editor.

Of course this does not come without problems.  It doesn't scale very well, neither when it comes to the number of users of the system nor when it comes to the size of the database.  For an inventory system for a person or a family I still think it works out pretty well.

### Modularity and flexibility

The system is very **modular**, most of the system is optional.  The system can work **online or offline**, from  a laptop or a web server or a combination of those!  (No mobile app yet ... but I'll fix it one day).

The "core" is the command line script "inventory-md" that can parse the markdown and create a json file out of it, optionally also create a shopping list, and do some other maintenance tasks.

### Features

Here are some of the **fully optional** features:

* **Javascript-based search page** - makes it a bit easier to search for items, and a bit easier for some of my family members to relate to it.  The alternative is to search through the markdown file - or a json file.
* Static page built-in **web server** to serve the search page, photos and data to the end user.  This is just a simple file server, it's recommended to rather use nginx or apache.  Accessing the files directly from the browser didn't work for me due to CORS problems.
* **API server** - needed for editing the inventory through the web pages, and it's needed for adding an AI chatbot.
* **AI-based database population**.  For a long time I've been a bit of a Luddite when it comes to AI, but the AI has proven very useful in this project.  Most of the time I'm using Claude Code for updating the database, I just take photos of the inventory, tell Claude "please process inventory photos for the cupboard under the sink" and it will analyze the photos and do everything for me, even including looking up technical specifications online and translating from foreign languages.  It's still needed to manually do QA of the work, but it's really amazing me sometimes.
* **AI-based database maintenance**.  I use Claude for things like adding tags to the inventory listing and creating an aliases file (allowing multi-lingual search and allowing things like the multimeter to show up when searching for a voltmeter).
* **AI-based recipe suggestions** based on what food is expiring.
* **AI chatbot** on the web page.  Fully optional. This is cloud-based (Claude-based), needs a subscription and it may be a privacy risk.  It doesn't even work very well.
* Various scripts - like a script checking the photos for bar codes and looking up EAN-codes and ISBNs in public databases.  It may also do OCR from photos.
* **Multilinguar** support.  Usually I always stick to English - but I decided to make an exception for the house inventory database, it's in Norwegian.  My boat inventory database is however in English as I'm often have various crew and guests on board.  Both databases can be searched using both English and Norwegian though.
* Did I mention the **shopping list generator**?

This is an immature project.  The drawback is that there may be lots of sharp edges and missing features.  The advantage is that development can happen with agility and without being afraid that the big huserbase will disagree with the changes.  Pull requests will be accepted in express speed as long as they make sense to me.

## Data Design

Details are to be found in a [separate document](docs/DATA_DESIGN.md)

For me it's important to have a very **generalized** system.  I want a system that is suitable both for the milk in the fridge as well as boxes stored in a basement or a garage.  I started out with some plastic boxes stacked on top of each other in "towers", most of them located in the garage.  At first Claude made a "garage inventory system" for me with hard-coded concepts like "locations", "towers", "boxes" and "items".  That's not the design I had in mind!

Locations are organized strictly **hierarchical**.  An "inventory line" may be either a "container" or an "item", but the only difference between those two is that the container has children while the item is a leaf node!  Empty a container, and it will become an item.  Add subitems to an item and it's a container!

Classification of items is done by slapping a set of **hiearchical tags** to the item.  Inventory lines may have other data attached to them, like a **best before**-date, **quantity**, **price**, **value**, **mass**, **volume**, etc, etc.



## Installation

See the [installation guide](docs/INSTALLATION.md)

## Markdown Format

### Basic Structure

The inventory is organized in a markdown file with hierarchical headers representing containers and bullet points representing items.

```markdown
# Intro

Description of your inventory...

# Oversikt

## ID:Garage Garage

Main garage area.

### ID:Shelf1 (parent:Garage) Metal Shelf

Items on this shelf:

* tag:tools,workshop Screwdriver set
* tag:tools Hammer
* ID:Toolbox1 Red toolbox

#### ID:Toolbox1 (parent:Shelf1) Red Toolbox

* tag:electrical Multimeter
* tag:electrical Wire strippers

![Shelf overview](resized/shelf1.jpg)
```

### Metadata Syntax

Items and containers can have metadata:

- `ID:unique-id` - Unique identifier
- `parent:parent-id` - Parent container reference
- `tag:tag1,tag2,tag3` - Comma-separated tags
- `type:category` - Item type/category

Metadata can be placed anywhere in the line:
- `ID:A1 My Container`
- `My Container ID:A1`
- `ID:A1 (parent:Garage) My Container`

See also the [data design document](docs/DATA_DESIGN.md)

## CLI Commands

### `init` - Initialize a new inventory

```bash
inventory-md init <directory> [--name <name>]
```

Creates a new inventory with template files.

### `parse` - Parse inventory markdown

```bash
inventory-md parse <file.md> [--output <output.json>] [--validate] [--wanted-items <wanted.md>]
```

Parses the markdown file and generates JSON. Use `--validate` to check for errors without generating output.

Use `--wanted-items` to also generate a shopping list by comparing the wanted items file against current inventory.

### `serve` - Start web server

```bash
inventory-md serve [directory] [--port <port>]
```

Starts a local web server to view the inventory. Default port is 8000.

This is basically equivalent with `python -m http.server`, just with a bit of extra sugar.

**It's recommended to use a web server like nginx or apache for this purpose.  If you have anything secret in your inventory, it's also recommended to set up authentication**

### `api` - Start API server

```bash
inventory-md api [directory] [--port <port>]
```

This is needed for:

* Allowing edits to be done through the web
* Having an AI-bot running (requires `ANTHROPIC_API_KEY` environment variable)

It's recommended to set it up to listen only to localhost, and have all external traffic going through a web server like apache or nginx.  **It's also recommended to set up authentication** on the web server, unless you want the whole world to be able to edit your inventory and use up your Claude API credits.

## Utility Scripts

The `scripts/` directory contains various utilities:

* `find_expiring_food.py` - List items expiring soon
* `extract_barcodes.py` - Extract barcodes from photos
* `sync_eans_to_inventory.py` - Look up EAN codes and add product info
* `generate_shopping_list.py` - Generate shopping list from wanted items
* `check_quality.py` - Check inventory data quality
* `analyze_inventory.py` - Analyze inventory statistics
* `export_tags.py` / `migrate-tags.py` - Tag management tools

## Deployment

For server deployment, the system includes:

* **Systemd service templates** (`systemd/inventory-api@.service`, `systemd/inventory-web@.service`)
* **Makefile** with commands for managing instances
* **Puppet module** available at [puppet-inventory-md](https://github.com/tobixen/puppet-inventory-md)

See the [installation guide](docs/INSTALLATION.md) for details.

## License

MIT
