# Inventory System - Human thoughts on it

This is a flexible "vibe-coded" Markdown-based inventory management system with web UI and Claude-backed AI chat-bot.  My "roadmap" is to ensure it works well for two actual inventories, then make a demo and release a v1.0.

## Problem

I hate throwing things.  My wife also don't like to throw things.  For the last decades we're been living in a place/period of plenty (Norway, 2000-2026), so we've ended up with the garage, attics and other storage spaces filld up with thrash.  Whenever we need something it's way easier to buy it in the shop than to find it in the our thrash - but this certainly only makes the problem bigger.

With a good inventory system the useless thrash becomes valuable stash, as we easily can find something when we need it.

## Yet Another Inventory System?

Other systems exists.  I should definitively have looked into this before starting with my own system.  The background why I ended up with Yet Another System is that I started out with maintaining a very simple markdown file.  I asked the AI how to improve the system, it suggested to have a use a local static javascript ... and then things grew organically and escalated from there.

## Claude maintenance

Keeping an inventory database up-to-date may require a lot of work.  Luckily Claude can help with it.  There is a maintenance guide and I also have stored "process photos" as a "skill", this skill will also be added to the project at some point.  It makes things much easier - just take good photos of the inventory and ask Claude to process it.  As of 2026-01, manual human verification of the work still seems very much needed, but in general Claude can easily categorize items, look up identifiers like the EAN, translate foreign languages with foreign scripts into a language the user understands, categorize items with correct tags, etc.

Claude can even check what food articles are expiring and suggest recipes based on it

## Web interface

Some of my family members should be able to search for things in the markdown file, browse photos on their laptop and and maintain things - but in practice it didn't work out, so I needed a web interface.

With the help of Claude I also organized tagging, categories, aliases and more - at the end of the day the web interface makes it easy to find whatever I'm searching for, while it's difficult by doing simple text searches in the markdown while browsing photo albums on the laptop.

## Chatbot

I got Claude to help me maintain the markdown file from the terminal window on the laptop, so I thought the inventory should be maintainable by a chatbot.  The current implementation uses the Claude API.  I believe the problem is that for every API call, the AI-thinking starts with blank sheets.  As of 2025-12 the Chatbot is almost useless - it's even unable to find things that can easily be found through the search bar.

## Markdown as a database

The database is in Markdown format ... and then a script was introduced to convert the markdown into JSON.  Now it's also possible to edit the inventory through the web UI, but the markdown gets horrible when doing this.

When all I did was to maintain and search for things using my editor, markdown made great sense. I've considered to scrap the markdown file and let the JSON be the "single source of truth" - or to even push this into a SQL database.  At the end of the day it all boils down to this: for me it's a lot easier to take up the markdown file in an editor and maintain it there than to do things through a web interface.  Claude also seems pretty good at editing markdown files.  So I've decided to stick to it.

# Inventory System - Artificial Intelligence documentation

## Features

- **Markdown-based**: Edit your inventory in plain text markdown files
- **Hierarchical organization**: Support for parent-child relationships between containers
- **Metadata tags**: Add searchable tags to items
- **Image support**: Include photos with automatic thumbnail generation
- **Web interface**: Searchable, filterable web UI with lightbox image viewer
- **Multi-tag filtering**: Filter by multiple tags with AND logic
- **Alias search**: Define search aliases for better discoverability
- **Gallery view**: Browse all images across containers

## Installation

```bash
# Install in development mode
cd inventory-system
pip install -e .
```

## Quick Start

```bash
# Initialize a new inventory
inventory-system init ~/my-inventory --name "Home Storage"

# Edit the inventory.md file
cd ~/my-inventory
editor inventory.md

# Parse and generate JSON
inventory-system parse inventory.md

# Start local web server
inventory-system serve
```

Then open http://localhost:8000/search.html in your browser.

## Markdown Format

### Basic Structure

```markdown
# Intro

Description of your inventory...

## About

More information...

# Nummereringsregime

Explanation of your numbering/naming scheme...

# Oversikt

## ID:Box1 (parent:Garage) Storage Box 1

Items in this box:

* tag:tools,workshop Screwdriver set
* tag:tools Hammer
* ID:SubBox1 Small parts container

![Thumbnail description](resized/box1.jpg)

[Fotos i full oppløsning](photos/box1/)
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

## CLI Commands

### `init` - Initialize a new inventory

```bash
inventory-system init <directory> [--name <name>]
```

Creates a new inventory with template files.

### `parse` - Parse inventory markdown

```bash
inventory-system parse <file.md> [--output <output.json>] [--validate]
```

Parses the markdown file and generates JSON. Use `--validate` to check for errors without generating output.

### `serve` - Start web server

```bash
inventory-system serve [directory] [--port <port>]
```

Starts a local web server to view the inventory. Default port is 8000.

## License

MIT
