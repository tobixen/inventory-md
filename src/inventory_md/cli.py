#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
Command-line interface for Inventory System
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import argcomplete

from . import parser, shopping_list, vocabulary
from ._version import __version__
from .config import Config


def init_inventory(directory: Path, name: str = "My Inventory") -> int:
    """Initialize a new inventory in the specified directory."""
    directory = Path(directory).resolve()

    if not directory.exists():
        directory.mkdir(parents=True)
        print(f"✅ Created directory: {directory}")
    elif any(directory.iterdir()):
        print(f"⚠️  Directory {directory} is not empty")
        response = input("Continue anyway? [y/N] ")
        if response.lower() != 'y':
            print("Aborted.")
            return 1

    # Copy template files
    templates_dir = Path(__file__).parent / 'templates'

    # Copy search.html
    search_html = templates_dir / 'search.html'
    if search_html.exists():
        shutil.copy(search_html, directory / 'search.html')
        print("✅ Created search.html")

    # Copy aliases.json template (if it exists)
    aliases_template = templates_dir / 'aliases.json.template'
    if aliases_template.exists():
        shutil.copy(aliases_template, directory / 'aliases.json')
        print("✅ Created aliases.json")

    # Create inventory.md from template or create basic one
    inventory_md = directory / 'inventory.md'
    if not inventory_md.exists():
        inventory_template = templates_dir / 'inventory.md.template'
        if inventory_template.exists():
            shutil.copy(inventory_template, inventory_md)
        else:
            # Create basic inventory.md
            with open(inventory_md, 'w', encoding='utf-8') as f:
                f.write(f"""# Intro

{name}

## Om inventarlisten

Dette er en søkbar inventarliste basert på markdown.

# Nummereringsregime

Bokser/containere kan navngis etter eget ønske. Eksempler:
* Box1, Box2, ... (numerisk)
* A1, A2, B1, B2, ... (alfabetisk)
* Garasje, Loft, Kjeller (stedsnavn)

# Oversikt

## ID:Eksempel1 (parent:RootLocation) Eksempel container

Beskrivelse av container...

* tag:eksempel,demo Dette er et eksempel på en item
* tag:demo Et annet item

![Beskrivelse](resized/bilde.jpg)

[Fotos i full oppløsning](photos/)
""")
        print("✅ Created inventory.md")

    # Create directories for images
    (directory / 'photos').mkdir(exist_ok=True)
    (directory / 'resized').mkdir(exist_ok=True)
    print("✅ Created image directories (photos/, resized/)")

    print(f"\n🎉 Inventory initialized in {directory}")
    print("\nNext steps:")
    print(f"1. Edit {directory / 'inventory.md'} to add your items")
    print(f"2. Run: inventory-system parse {directory / 'inventory.md'}")
    print(f"3. Open {directory / 'search.html'} in your browser")

    return 0


def update_template(directory: Path = None, force: bool = False) -> int:
    """Update search.html template to the latest version from the package.

    Args:
        directory: Target directory (default: current directory)
        force: Overwrite without prompting

    Returns:
        0 on success, 1 on error
    """
    if directory is None:
        directory = Path.cwd()
    else:
        directory = Path(directory).resolve()

    templates_dir = Path(__file__).parent / 'templates'
    source = templates_dir / 'search.html'
    target = directory / 'search.html'

    if not source.exists():
        print(f"❌ Template not found: {source}")
        return 1

    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        return 1

    # Check if target exists and prompt if not forcing
    if target.exists() and not force:
        print(f"⚠️  {target} already exists")
        response = input("Overwrite? [y/N] ")
        if response.lower() != 'y':
            print("Aborted.")
            return 1

    shutil.copy(source, target)
    print(f"✅ Updated {target}")
    return 0


def parse_command(md_file: Path, output: Path = None, validate_only: bool = False, wanted_items: Path = None, include_dated: bool = True, use_skos: bool = False, hierarchy_mode: bool = False, lang: str = None, languages: list[str] = None, enabled_sources: list[str] = None) -> int:
    """Parse inventory markdown file and generate JSON."""
    md_file = Path(md_file).resolve()

    if not md_file.exists():
        print(f"❌ Error: {md_file} not found!")
        return 1

    if output is None:
        output = md_file.parent / 'inventory.json'

    try:
        # Add ID: prefixes to container headers if not validating
        if not validate_only:
            print("🔍 Checking for duplicate container IDs...")
            changes, duplicates = parser.add_container_id_prefixes(md_file)

            if duplicates:
                print("⚠️  Found duplicate container IDs:")
                for orig_id, new_ids in duplicates.items():
                    print(f"   {orig_id} → {', '.join(new_ids)}")

            if changes > 0:
                print(f"✏️  Added ID: prefix to {changes} container headers")
            else:
                print("✅ All container headers already have ID: prefix")

        print(f"\n🔄 Parsing {md_file}...")
        data = parser.parse_inventory(md_file)

        print(f"✅ Found {len(data['containers'])} containers")

        # Count total images and items
        total_images = sum(len(container['images']) for container in data['containers'])
        total_items = sum(len(container['items']) for container in data['containers'])
        items_with_id = sum(1 for container in data['containers'] for item in container['items'] if item.get('id'))
        items_with_parent = sum(1 for container in data['containers'] for item in container['items'] if item.get('parent'))

        print(f"✅ Found {total_images} images and {total_items} items")
        print(f"   - {items_with_id} items with explicit IDs")
        print(f"   - {items_with_parent} items with parent references")

        # Validate and print issues
        print("\n🔍 Validating inventory...")
        issues = parser.validate_inventory(data)

        if issues:
            print(f"\n⚠️  Found {len(issues)} issue(s):")
            for issue in issues[:20]:  # Limit to first 20
                print(f"   {issue}")
            if len(issues) > 20:
                print(f"   ... and {len(issues) - 20} more")
        else:
            print("✅ No validation issues found!")

        # Save to JSON if not validating
        if not validate_only:
            parser.save_json(data, output)
            print(f"\n✅ Success! {output} has been updated.")

            # Generate photo directory listings for backup
            print("\n📸 Generating photo directory listings...")
            containers_processed, files_created = parser.generate_photo_listings(md_file.parent)
            if files_created > 0:
                print(f"✅ Created {files_created} photo listing(s) in photo-listings/")
            else:
                print("   No photos found (photo-listings/ not updated)")

            # Parse photo registry if it exists
            photo_registry_md = md_file.parent / "photo-registry.md"
            if photo_registry_md.exists():
                import json as json_module

                from . import photo_registry
                print("\n📷 Parsing photo registry...")
                registry_data = photo_registry.parse_photo_registry(photo_registry_md)
                registry_output = md_file.parent / "photo-registry.json"
                registry_output.write_text(
                    json_module.dumps(registry_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"✅ Found {len(registry_data['photos'])} photos mapped to {len(registry_data['items'])} items")
                print(f"   Saved to {registry_output}")

            # Generate vocabulary.json for category browser
            print("\n🏷️  Generating category vocabulary...")

            # Load global vocabulary from all standard locations (package, system, user)
            # Uses find_vocabulary_files() which includes the package default vocabulary
            global_vocab = {}
            for vocab_path in vocabulary.find_vocabulary_files():
                # Skip cwd entries - local vocab is handled separately based on md_file.parent
                if vocab_path.parent == Path.cwd():
                    continue
                loaded = vocabulary.load_local_vocabulary(vocab_path)
                if loaded:
                    # Merge: later files override earlier (but keep concepts from both)
                    global_vocab = vocabulary.merge_vocabularies(global_vocab, loaded)
                    print(f"   Loaded {len(loaded)} concepts from {vocab_path}")

            # Load local vocabulary if present (highest priority - overrides global)
            local_vocab_yaml = md_file.parent / "local-vocabulary.yaml"
            local_vocab_json = md_file.parent / "local-vocabulary.json"
            local_vocab = {}
            if local_vocab_yaml.exists():
                local_vocab = vocabulary.load_local_vocabulary(local_vocab_yaml)
                print(f"   Loaded {len(local_vocab)} concepts from local-vocabulary.yaml")
            elif local_vocab_json.exists():
                local_vocab = vocabulary.load_local_vocabulary(local_vocab_json)
                print(f"   Loaded {len(local_vocab)} concepts from local-vocabulary.json")

            # Merge global and local (local overrides global)
            local_vocab = vocabulary.merge_vocabularies(global_vocab, local_vocab)

            # Determine language for SKOS lookups
            skos_lang = lang or "en"

            # Build vocabulary from inventory categories
            category_mappings = None
            if use_skos or hierarchy_mode:
                lang_info = f"lang={skos_lang}"
                if languages and len(languages) > 1:
                    lang_info += f", translations={languages}"

                # Check if hierarchy mode is enabled (expand labels to full SKOS paths)
                if hierarchy_mode:
                    print(f"   Using SKOS hierarchy mode ({lang_info})...")
                    vocab, category_mappings = vocabulary.build_vocabulary_with_skos_hierarchy(
                        data, local_vocab=local_vocab, lang=skos_lang, languages=languages,
                        enabled_sources=enabled_sources,
                    )
                else:
                    print(f"   Using SKOS lookups ({lang_info})...")
                    vocab = vocabulary.build_vocabulary_from_inventory(
                        data, local_vocab=local_vocab, use_skos=use_skos, lang=skos_lang,
                        languages=languages
                    )
            else:
                vocab = vocabulary.build_vocabulary_from_inventory(
                    data, local_vocab=local_vocab, use_skos=False, lang=skos_lang,
                    languages=languages
                )
            category_counts = vocabulary.count_items_per_category(data)

            if vocab:
                vocab_output = md_file.parent / "vocabulary.json"
                vocabulary.save_vocabulary_json(vocab, vocab_output, category_mappings)
                mode_info = " (hierarchy mode)" if category_mappings else ""
                print(f"✅ Generated {vocab_output} with {len(vocab)} categories{mode_info}")
                if category_mappings:
                    # Show sample mappings
                    sample = list(category_mappings.items())[:3]
                    for label, paths in sample:
                        print(f"   {label} → {paths[0] if paths else '?'}")
                    if len(category_mappings) > 3:
                        print(f"   ... and {len(category_mappings) - 3} more mappings")
                elif category_counts:
                    top_categories = sorted(category_counts.items(), key=lambda x: -x[1])[:5]
                    print(f"   Top categories: {', '.join(f'{c}({n})' for c, n in top_categories)}")
            else:
                print("   No categories found in inventory")

            # Generate shopping list if wanted-items file specified
            if wanted_items:
                wanted_path = Path(wanted_items).resolve()
                if not wanted_path.exists():
                    print(f"\n⚠️  wanted-items file not found: {wanted_path}")
                else:
                    output_shopping = md_file.parent / "shopping-list.md"
                    result = shopping_list.generate_shopping_list(wanted_path, md_file, include_dated=include_dated)
                    output_shopping.write_text(result, encoding="utf-8")
                    dated_note = " (including dated files)" if include_dated else ""
                    print(f"\n🛒 Generated {output_shopping}{dated_note}")

            search_html = md_file.parent / 'search.html'
            print("\n📱 To view the searchable inventory, open search.html in your browser:")
            print(f"   xdg-open {search_html}")

        return 0

    except Exception as e:
        import traceback
        print(f"\n❌ Error parsing inventory: {e}")
        traceback.print_exc()
        return 1


def serve_command(directory: Path = None, port: int = 8000, host: str = "127.0.0.1", api_proxy: str = None) -> int:
    """Start a local web server to view the inventory.

    If api_proxy is specified (e.g., 'localhost:8765'), requests to /api/ and /chat
    will be proxied to that backend.
    """
    if directory is None:
        directory = Path.cwd()
    else:
        directory = Path(directory).resolve()

    if not directory.exists():
        print(f"❌ Directory {directory} does not exist")
        return 1

    search_html = directory / 'search.html'
    if not search_html.exists():
        print(f"❌ search.html not found in {directory}")
        print(f"Run 'inventory-system init {directory}' first")
        return 1

    # Display the address - show 0.0.0.0 as "all interfaces"
    display_host = "0.0.0.0 (all interfaces)" if host == "0.0.0.0" else host
    print(f"🌐 Starting web server at http://{display_host}:{port}")
    print(f"📂 Serving directory: {directory}")
    if api_proxy:
        print(f"🔄 Proxying /api/* and /chat to http://{api_proxy}")
    print("Press Ctrl+C to stop\n")

    import http.server
    import os
    import socketserver
    import urllib.error
    import urllib.request

    os.chdir(directory)

    class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        """HTTP handler that can proxy API requests to a backend server."""

        def do_proxy(self, method: str):
            """Proxy request to the API backend."""
            if not api_proxy:
                self.send_error(404, "API proxy not configured")
                return

            # Build the backend URL
            backend_url = f"http://{api_proxy}{self.path}"

            # Read request body for POST/PUT
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            # Create the proxy request
            req = urllib.request.Request(backend_url, data=body, method=method)

            # Copy relevant headers
            for header, value in self.headers.items():
                if header.lower() not in ('host', 'content-length'):
                    req.add_header(header, value)

            try:
                with urllib.request.urlopen(req, timeout=90) as response:
                    # Send response status
                    self.send_response(response.status)

                    # Copy response headers
                    for header, value in response.headers.items():
                        if header.lower() not in ('transfer-encoding', 'connection'):
                            self.send_header(header, value)
                    self.end_headers()

                    # Send response body
                    self.wfile.write(response.read())

            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                for header, value in e.headers.items():
                    if header.lower() not in ('transfer-encoding', 'connection'):
                        self.send_header(header, value)
                self.end_headers()
                self.wfile.write(e.read())
            except urllib.error.URLError as e:
                self.send_error(502, f"Backend unavailable: {e.reason}")
            except Exception as e:
                self.send_error(500, f"Proxy error: {str(e)}")

        def should_proxy(self) -> bool:
            """Check if this request should be proxied."""
            return api_proxy and (
                self.path.startswith('/api/') or
                self.path.startswith('/chat') or
                self.path.startswith('/health')
            )

        def do_GET(self):
            if self.should_proxy():
                self.do_proxy('GET')
            else:
                super().do_GET()

        def do_POST(self):
            if self.should_proxy():
                self.do_proxy('POST')
            else:
                self.send_error(405, "Method Not Allowed")

        def do_PUT(self):
            if self.should_proxy():
                self.do_proxy('PUT')
            else:
                self.send_error(405, "Method Not Allowed")

        def do_DELETE(self):
            if self.should_proxy():
                self.do_proxy('DELETE')
            else:
                self.send_error(405, "Method Not Allowed")

        def do_OPTIONS(self):
            if self.should_proxy():
                self.do_proxy('OPTIONS')
            else:
                # Handle CORS preflight for non-proxied requests
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()

    Handler = ProxyHTTPRequestHandler
    try:
        with socketserver.TCPServer((host, port), Handler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n\n👋 Server stopped")
                return 0
    except Exception as e:
        import traceback
        print(f"\n❌ Server failed to start: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return 1


def api_command(directory: Path = None, port: int = 8765, host: str = "127.0.0.1") -> int:
    """Start the inventory API server (chat, photo upload, item management)."""
    import os

    # Check for API key (optional - chat feature will be disabled if not set)
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_api_key:
        print("ℹ️  ANTHROPIC_API_KEY not set - chat feature will be disabled")
        print("   Photo upload and item management will still work")
        print("\n   To enable chat, get an API key from: https://console.anthropic.com/")
        print("   Then set it: export ANTHROPIC_API_KEY='your-key-here'\n")

    if directory is None:
        directory = Path.cwd()
    else:
        directory = Path(directory).resolve()

    if not directory.exists():
        print(f"❌ Directory {directory} does not exist")
        return 1

    inventory_json = directory / 'inventory.json'
    if not inventory_json.exists():
        print(f"❌ inventory.json not found in {directory}")
        print("Run 'inventory-system parse inventory.md' first")
        return 1

    # Change to directory so API server can find inventory.json
    os.chdir(directory)

    print("🚀 Starting Inventory API Server...")
    print(f"📂 Using inventory: {inventory_json}")
    print(f"🌐 Server will run at: http://{host}:{port}")
    print(f"💬 Chat endpoint: http://localhost:{port}/chat")
    print(f"📸 Photo upload: http://localhost:{port}/api/photos")
    print(f"➕ Add/remove items: http://localhost:{port}/api/items")
    print(f"❤️  Health check: http://localhost:{port}/health")
    print("\nOpen search.html in your browser to use the interface")
    print("Press Ctrl+C to stop\n")

    # Import and run the API server
    try:
        import uvicorn

        from .api_server import app
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("\nInstall API server dependencies:")
        print("  pip install fastapi uvicorn anthropic python-multipart")
        return 1

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        print("\n\n👋 Chat server stopped")
        return 0
    except Exception as e:
        import traceback
        print(f"\n❌ Server failed to start: {e}")
        print("\nFull traceback:")
        traceback.print_exc()
        return 1


def labels_generate(
    series: str | None = None,
    start: str | None = None,
    ids: str | None = None,
    count: int = 1,
    style: str = "standard",
    sheet_format: str = "48x25-40",
    output: Path | None = None,
    output_format: str = "pdf",
    base_url: str = "https://inventory.example.com/search.html",
    show_date: bool = True,
    custom_formats: dict | None = None,
    dupes: int | None = None,
) -> int:
    """Generate label sheet or PNG images."""
    try:
        from . import labels
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("\nInstall labels dependencies:")
        print('  pip install "inventory-md[labels]"')
        return 1

    # Determine label IDs (unique)
    try:
        if ids:
            unique_ids = [id.strip().upper() for id in ids.split(",")]
            # Validate all IDs
            for lid in unique_ids:
                if not labels.validate_label_id(lid):
                    print(f"Invalid label ID: {lid}")
                    print("Format must be: [A-Z][A-Z][0-9] (e.g., AA0, BC5)")
                    return 1
        else:
            unique_ids = labels.generate_id_sequence(series=series, start=start, count=count)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # Determine number of duplicates per label
    if dupes is None:
        # Default: 5 for standard (label each side of container), 1 for compact/duplicate
        dupes = 5 if style == "standard" else 1

    # Expand IDs with duplicates
    label_ids = []
    for lid in unique_ids:
        label_ids.extend([lid] * dupes)

    # Default output path: labels/labels-{start}-{end}.pdf
    if output is None:
        labels_dir = Path("labels")
        labels_dir.mkdir(exist_ok=True)
        if output_format == "png":
            output = labels_dir
        else:
            output = labels_dir / f"labels-{unique_ids[0]}-{unique_ids[-1]}.pdf"

    # Generate
    try:
        if output_format == "png":
            fmt = labels.get_sheet_format(sheet_format, custom_formats)
            created_files = labels.save_labels_as_png(
                label_ids,
                base_url,
                str(output),
                style=style,
                width_mm=fmt["label_width_mm"],
                height_mm=fmt["label_height_mm"],
            )
            print(f"Created {len(created_files)} PNG files in {output}/")
            for f in created_files[:5]:
                print(f"  {f}")
            if len(created_files) > 5:
                print(f"  ... and {len(created_files) - 5} more")
        else:
            pdf_bytes = labels.create_label_sheet(
                label_ids,
                base_url,
                sheet_format=sheet_format,
                style=style,
                custom_formats=custom_formats,
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(pdf_bytes)
            print(f"Created {output} with {len(label_ids)} labels ({len(unique_ids)} unique x {dupes} dupes)")
            print(f"  IDs: {unique_ids[0]} - {unique_ids[-1]}")

        return 0
    except Exception as e:
        import traceback
        print(f"Error generating labels: {e}")
        traceback.print_exc()
        return 1


def labels_formats(custom_formats: dict | None = None) -> int:
    """List available label sheet formats."""
    try:
        from . import labels
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("\nInstall labels dependencies:")
        print('  pip install "inventory-md[labels]"')
        return 1

    print("Available label sheet formats:\n")
    formats = labels.list_formats(custom_formats)
    for name, description in formats:
        print(f"  {name:15} {description}")

    print("\nUse with: inventory-md labels generate --sheet-format FORMAT")
    return 0


def labels_preview(
    series: str | None = None,
    start: str | None = None,
    count: int = 1,
) -> int:
    """Preview label IDs without generating."""
    try:
        from . import labels
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("\nInstall labels dependencies:")
        print('  pip install "inventory-md[labels]"')
        return 1

    try:
        label_ids = labels.generate_id_sequence(series=series, start=start, count=count)
        print(" ".join(label_ids))
        return 0
    except ValueError as e:
        print(f"Error: {e}")
        return 1


def config_command(show: bool = False, show_path: bool = False) -> int:
    """Show configuration information."""
    config = Config()

    if show_path:
        if config.path:
            print(config.path)
        else:
            print("No configuration file found")
        return 0

    if show or (not show_path):
        # Show merged config
        if config.path:
            print(f"# Configuration loaded from: {config.path}")
        else:
            print("# No configuration file found, showing defaults")
        print()
        print(json.dumps(config.data, indent=2))
        return 0

    return 0


def main() -> int:
    """Main entry point for the CLI."""
    # Load configuration (used for defaults)
    config = Config()

    parser_cli = argparse.ArgumentParser(
        description="Inventory System - Manage markdown-based inventories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize a new inventory
  inventory-md init ~/my-inventory --name "Home Storage"

  # Parse inventory and generate JSON
  inventory-md parse ~/my-inventory/inventory.md

  # Validate inventory without generating JSON
  inventory-md parse ~/my-inventory/inventory.md --validate

  # Start a local web server
  inventory-md serve ~/my-inventory

  # Start API server for chat, photos, and item management (requires ANTHROPIC_API_KEY)
  inventory-md api ~/my-inventory

  # Show current configuration
  inventory-md config --show
        """
    )
    parser_cli.add_argument(
        '--version', '-V',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    subparsers = parser_cli.add_subparsers(dest='command', help='Command to run')

    # Config command
    config_parser = subparsers.add_parser('config', help='Show configuration')
    config_parser.add_argument('--show', action='store_true', help='Show merged configuration')
    config_parser.add_argument('--path', action='store_true', help='Show config file path')

    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new inventory')
    init_parser.add_argument('directory', type=Path, help='Directory to initialize')
    init_parser.add_argument('--name', type=str, default='My Inventory', help='Name of the inventory')

    # Parse command
    parse_parser = subparsers.add_parser('parse', help='Parse inventory markdown file')
    parse_parser.add_argument('file', type=Path, nargs='?', help='Inventory markdown file to parse (default: from config or inventory.md with --auto)')
    parse_parser.add_argument('--output', '-o', type=Path, help='Output JSON file (default: inventory.json)')
    parse_parser.add_argument('--validate', action='store_true', help='Validate only, do not generate JSON')
    parse_parser.add_argument('--wanted-items', '-w', type=Path, help='Wanted items file to generate shopping list')
    parse_parser.add_argument('--no-dated', action='store_true', help='Exclude dated wanted-items files (wanted-items-YYYY-MM-DD.md)')
    parse_parser.add_argument('--auto', '-a', action='store_true',
                              help='Auto-detect files: inventory.md and wanted-items.md in current directory')
    parse_parser.add_argument('--skos', action='store_true',
                              help='Enrich categories with SKOS vocabulary lookups (AGROVOC/DBpedia)')
    parse_parser.add_argument('--hierarchy', action='store_true',
                              help='Expand category labels to full SKOS hierarchy paths (implies --skos)')

    # Update-template command
    update_parser = subparsers.add_parser('update-template', help='Update search.html to latest version')
    update_parser.add_argument('directory', type=Path, nargs='?', help='Target directory (default: current directory)')
    update_parser.add_argument('--force', '-f', action='store_true', help='Overwrite without prompting')

    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Start local web server')
    serve_parser.add_argument('directory', type=Path, nargs='?', help='Directory to serve (default: current directory)')
    serve_parser.add_argument('--port', '-p', type=int, default=None, help=f'Port number (default: {config.serve_port})')
    serve_parser.add_argument('--host', type=str, default=None,
                              help=f'Host to bind to (default: {config.serve_host}, use 0.0.0.0 for all interfaces)')
    serve_parser.add_argument('--api-proxy', type=str, metavar='HOST:PORT',
                              help='Proxy /api/* and /chat requests to backend (e.g., localhost:8765)')

    # API command
    api_parser = subparsers.add_parser('api', help='Start API server (chat, photos, item management)')
    api_parser.add_argument('directory', type=Path, nargs='?', help='Directory with inventory.json (default: current directory)')
    api_parser.add_argument('--port', '-p', type=int, default=None, help=f'Port number (default: {config.api_port})')
    api_parser.add_argument('--host', type=str, default=None, help=f'Host to bind to (default: {config.api_host})')

    # Chat command (backwards compatibility alias for 'api')
    chat_parser = subparsers.add_parser('chat', help='[Deprecated] Use "api" instead')
    chat_parser.add_argument('directory', type=Path, nargs='?', help='Directory with inventory.json (default: current directory)')
    chat_parser.add_argument('--port', '-p', type=int, default=None, help=f'Port number (default: {config.api_port})')
    chat_parser.add_argument('--host', type=str, default=None, help=f'Host to bind to (default: {config.api_host})')

    # Labels command with subcommands
    labels_parser = subparsers.add_parser('labels', help='Generate QR code labels for printing')
    labels_subparsers = labels_parser.add_subparsers(dest='labels_command', help='Labels subcommand')

    # labels generate
    labels_gen = labels_subparsers.add_parser(
        'generate',
        help='Generate label sheet or PNG images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Label styles:
  standard   QR code + large ID + date (default for labeling containers)
  compact    QR code only (for small labels)
  duplicate  Two identical QR codes + ID + date (for wide labels, can cut/tear)

Examples:
  inventory-md labels generate --series A --count 10
  inventory-md labels generate --start AB5 --count 5 --style compact
  inventory-md labels generate --ids AA0,AB0,AC0 --dupes 3
        """,
    )
    labels_gen.add_argument('--series', '-s', type=str, help='Series letter (A-Z), starts at {series}A0')
    labels_gen.add_argument('--start', type=str, help='Starting ID (e.g., AB5)')
    labels_gen.add_argument('--ids', type=str, help='Comma-separated list of specific IDs')
    labels_gen.add_argument('--count', '-n', type=int, default=30, help='Number of unique IDs to generate (default: 30)')
    labels_gen.add_argument('--dupes', '-d', type=int, default=None,
                            help='Duplicates per label (default: 5 for standard, 1 for compact/duplicate)')
    labels_gen.add_argument('--style', type=str, choices=['standard', 'compact', 'duplicate'],
                            default=None, help='Label style (default: from config or standard)')
    labels_gen.add_argument('--sheet-format', type=str, default=None,
                            help='Sheet format (default: from config or 48x25-40)')
    labels_gen.add_argument('--output', '-o', type=Path,
                            help='Output file (default: labels/labels-{start}-{end}.pdf)')
    labels_gen.add_argument('--format', '-f', type=str, choices=['pdf', 'png'], default='pdf',
                            help='Output format (default: pdf)')
    labels_gen.add_argument('--base-url', type=str, default=None,
                            help='Base URL for QR codes (default: from config)')

    # labels formats
    labels_subparsers.add_parser('formats', help='List available sheet formats')

    # labels preview
    labels_prev = labels_subparsers.add_parser('preview', help='Preview label IDs without generating')
    labels_prev.add_argument('--series', '-s', type=str, help='Series letter (A-Z)')
    labels_prev.add_argument('--start', type=str, help='Starting ID (e.g., AB5)')
    labels_prev.add_argument('--count', '-n', type=int, default=10, help='Number of IDs to show (default: 10)')

    # SKOS command with subcommands
    skos_parser = subparsers.add_parser('skos', help='SKOS vocabulary lookups for tag hierarchies')
    skos_subparsers = skos_parser.add_subparsers(dest='skos_command', help='SKOS subcommand')

    # skos expand
    skos_expand = skos_subparsers.add_parser(
        'expand',
        help='Expand tags to hierarchical paths using SKOS vocabularies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Queries AGROVOC and DBpedia SPARQL endpoints to find hierarchical paths
for tags. Results are cached locally for faster subsequent lookups.

Examples:
  inventory-md skos expand potatoes
  inventory-md skos expand --lang no poteter
  inventory-md skos expand screwdriver hammer wrench
        """,
    )
    skos_expand.add_argument('tags', nargs='+', help='Tags to expand')
    skos_expand.add_argument('--lang', '-l', type=str, default='en', help='Language code (default: en)')
    skos_expand.add_argument('--sources', type=str, default='agrovoc,dbpedia',
                             help='Comma-separated sources to query (default: agrovoc,dbpedia)')
    skos_expand.add_argument('--json', '-j', action='store_true', help='Output as JSON')

    # skos lookup
    skos_lookup = skos_subparsers.add_parser('lookup', help='Look up a single concept with full details')
    skos_lookup.add_argument('label', help='Label to look up')
    skos_lookup.add_argument('--lang', '-l', type=str, default='en', help='Language code (default: en)')
    skos_lookup.add_argument('--source', '-s', type=str, default='agrovoc',
                             help='Source to query (default: agrovoc)')

    # skos cache
    skos_cache = skos_subparsers.add_parser('cache', help='Manage SKOS lookup cache')
    skos_cache.add_argument('--clear', action='store_true', help='Clear all cached lookups')
    skos_cache.add_argument('--path', action='store_true', help='Show cache directory path')

    # Vocabulary command with subcommands
    vocab_parser = subparsers.add_parser('vocabulary', help='Manage local category vocabulary')
    vocab_subparsers = vocab_parser.add_subparsers(dest='vocab_command', help='Vocabulary subcommand')

    # vocabulary list
    vocab_list = vocab_subparsers.add_parser(
        'list',
        help='List all concepts in vocabulary',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Lists all concepts from the local vocabulary and inventory categories.

Examples:
  inventory-md vocabulary list
  inventory-md vocabulary list --directory ~/my-inventory
        """,
    )
    vocab_list.add_argument('--directory', '-d', type=Path, help='Inventory directory (default: current)')
    vocab_list.add_argument('--json', '-j', action='store_true', help='Output as JSON')

    # vocabulary lookup
    vocab_lookup = vocab_subparsers.add_parser('lookup', help='Look up a concept by label')
    vocab_lookup.add_argument('label', help='Label to look up (prefLabel or altLabel)')
    vocab_lookup.add_argument('--directory', '-d', type=Path, help='Inventory directory (default: current)')

    # vocabulary tree
    vocab_tree = vocab_subparsers.add_parser('tree', help='Show category hierarchy as tree')
    vocab_tree.add_argument('--directory', '-d', type=Path, help='Inventory directory (default: current)')

    # Enable shell tab completion
    argcomplete.autocomplete(parser_cli)

    args = parser_cli.parse_args()

    if args.command == 'config':
        return config_command(
            show=getattr(args, 'show', False),
            show_path=getattr(args, 'path', False)
        )
    elif args.command == 'init':
        return init_inventory(args.directory, args.name)
    elif args.command == 'parse':
        include_dated = not getattr(args, 'no_dated', False)
        auto_mode = getattr(args, 'auto', False)
        skos_flag_provided = '--skos' in sys.argv
        hierarchy_flag_provided = '--hierarchy' in sys.argv

        # Handle --auto mode
        if auto_mode:
            cwd = Path.cwd()
            md_file = args.file or cwd / 'inventory.md'
            wanted_items = getattr(args, 'wanted_items', None)
            if wanted_items is None:
                # Auto-detect wanted-items.md
                wanted_path = cwd / 'wanted-items.md'
                if wanted_path.exists():
                    wanted_items = wanted_path
            # In auto mode, use config for SKOS settings if flags not explicitly provided
            if hierarchy_flag_provided:
                hierarchy_mode = True
                use_skos = True  # --hierarchy implies --skos
            elif skos_flag_provided:
                use_skos = getattr(args, 'skos', False)
                hierarchy_mode = config.skos_hierarchy_mode
            else:
                use_skos = config.skos_enabled
                hierarchy_mode = config.skos_hierarchy_mode if use_skos else False
            lang = config.lang
            languages = config.skos_languages if use_skos or hierarchy_mode else None
        else:
            # Try config values, then CLI args
            md_file = args.file
            if md_file is None:
                md_file = config.inventory_file
            wanted_items = getattr(args, 'wanted_items', None)
            if wanted_items is None:
                wanted_items = config.wanted_file
            if md_file is None:
                print("Error: inventory file required (or use --auto, or set inventory_file in config)", file=sys.stderr)
                return 1
            # --hierarchy implies --skos, config can also enable these
            hierarchy_mode = getattr(args, 'hierarchy', False) or config.skos_hierarchy_mode
            use_skos = getattr(args, 'skos', False) or hierarchy_mode or config.skos_enabled
            lang = config.lang if use_skos else None
            languages = config.skos_languages if use_skos else None

        enabled_sources = config.get("skos.enabled_sources", ["off", "agrovoc", "dbpedia"])
        return parse_command(md_file, args.output, args.validate, wanted_items, include_dated, use_skos, hierarchy_mode, lang, languages, enabled_sources)
    elif args.command == 'update-template':
        return update_template(args.directory, args.force)
    elif args.command == 'serve':
        port = args.port if args.port is not None else config.serve_port
        host = args.host if args.host is not None else config.serve_host
        return serve_command(args.directory, port, host, getattr(args, 'api_proxy', None))
    elif args.command == 'api' or args.command == 'chat':
        port = args.port if args.port is not None else config.api_port
        host = args.host if args.host is not None else config.api_host
        return api_command(args.directory, port, host)
    elif args.command == 'labels':
        if args.labels_command == 'generate':
            style = args.style if args.style else config.labels_style
            sheet_format = args.sheet_format if args.sheet_format else config.labels_sheet_format
            base_url = args.base_url if args.base_url else config.labels_base_url
            return labels_generate(
                series=args.series,
                start=args.start,
                ids=args.ids,
                count=args.count,
                style=style,
                sheet_format=sheet_format,
                output=args.output,
                output_format=args.format,
                base_url=base_url,
                show_date=config.labels_show_date,
                custom_formats=config.labels_custom_formats,
                dupes=args.dupes,
            )
        elif args.labels_command == 'formats':
            return labels_formats(custom_formats=config.labels_custom_formats)
        elif args.labels_command == 'preview':
            return labels_preview(
                series=args.series,
                start=args.start,
                count=args.count,
            )
        else:
            labels_parser.print_help()
            return 1
    elif args.command == 'skos':
        return skos_command(args, config)
    elif args.command == 'vocabulary':
        return vocabulary_command(args, config)
    else:
        parser_cli.print_help()
        return 1


def skos_command(args, config: Config) -> int:
    """Handle SKOS subcommands."""
    try:
        from . import skos
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("\nInstall SKOS dependencies:")
        print('  pip install "inventory-md[skos]"')
        return 1

    skos_config = config.get("skos", {})
    default_lang = skos_config.get("default_lang", "en")

    if args.skos_command == 'expand':
        lang = getattr(args, 'lang', default_lang)
        sources = getattr(args, 'sources', 'agrovoc,dbpedia').split(',')
        output_json = getattr(args, 'json', False)

        client = skos.SKOSClient(enabled_sources=sources)
        result = client.expand_tags(args.tags, lang=lang)

        if output_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            for tag, paths in result.items():
                print(f"{tag}:")
                for path in paths:
                    print(f"  → {path}")

        return 0

    elif args.skos_command == 'lookup':
        lang = getattr(args, 'lang', default_lang)
        source = getattr(args, 'source', 'agrovoc')

        client = skos.SKOSClient(enabled_sources=[source])
        concept = client.lookup_concept(args.label, lang=lang, source=source)

        if concept and concept.get('uri'):
            print(json.dumps(concept, indent=2, ensure_ascii=False))
        else:
            print(f"No concept found for '{args.label}' in {source}")
            return 1

        return 0

    elif args.skos_command == 'cache':
        if getattr(args, 'clear', False):
            client = skos.SKOSClient()
            count = client.clear_cache()
            print(f"Cleared {count} cached lookups")
            return 0
        elif getattr(args, 'path', False):
            print(skos.DEFAULT_CACHE_DIR)
            return 0
        else:
            # Show cache stats
            cache_dir = skos.DEFAULT_CACHE_DIR
            if cache_dir.exists():
                cache_files = list(cache_dir.glob("*.json"))
                print(f"Cache directory: {cache_dir}")
                print(f"Cached lookups: {len(cache_files)}")
            else:
                print(f"Cache directory: {cache_dir} (not created yet)")
            return 0

    else:
        # No subcommand - show help
        print("SKOS vocabulary lookups for tag hierarchies")
        print("\nSubcommands:")
        print("  expand  Expand tags to hierarchical paths")
        print("  lookup  Look up a single concept with full details")
        print("  cache   Manage SKOS lookup cache")
        print("\nUse 'inventory-md skos <command> --help' for more info")
        return 1


def vocabulary_command(args, config: Config) -> int:
    """Handle vocabulary subcommands."""
    directory = getattr(args, 'directory', None)
    if directory is None:
        directory = Path.cwd()
    else:
        directory = Path(directory).resolve()

    # Load global vocabulary from all standard locations (package, system, user)
    # Uses find_vocabulary_files() which includes the package default vocabulary
    global_vocab = {}
    for vocab_path in vocabulary.find_vocabulary_files():
        # Skip cwd entries - local vocab is handled separately based on directory
        if vocab_path.parent == Path.cwd():
            continue
        loaded = vocabulary.load_local_vocabulary(vocab_path)
        if loaded:
            global_vocab = vocabulary.merge_vocabularies(global_vocab, loaded)

    # Load local vocabulary from directory (highest priority)
    local_vocab_yaml = directory / "local-vocabulary.yaml"
    local_vocab_json = directory / "local-vocabulary.json"
    inventory_json = directory / "inventory.json"

    local_vocab = {}
    if local_vocab_yaml.exists():
        local_vocab = vocabulary.load_local_vocabulary(local_vocab_yaml)
    elif local_vocab_json.exists():
        local_vocab = vocabulary.load_local_vocabulary(local_vocab_json)

    # Merge global and local (local overrides global)
    local_vocab = vocabulary.merge_vocabularies(global_vocab, local_vocab)

    # Also load from inventory if it exists
    if inventory_json.exists():
        with open(inventory_json, encoding="utf-8") as f:
            inventory_data = json.load(f)
        vocab = vocabulary.build_vocabulary_from_inventory(inventory_data, local_vocab=local_vocab)
    else:
        vocab = local_vocab

    if args.vocab_command == 'list':
        output_json = getattr(args, 'json', False)

        if not vocab:
            print("No vocabulary found. Create local-vocabulary.yaml or run 'inventory-md parse' first.")
            return 1

        if output_json:
            tree = vocabulary.build_category_tree(vocab)
            print(json.dumps(tree.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(f"Vocabulary: {len(vocab)} concepts\n")
            # Sort by ID
            for concept_id in sorted(vocab.keys()):
                concept = vocab[concept_id]
                alt_str = f" (aka: {', '.join(concept.altLabels)})" if concept.altLabels else ""
                print(f"  {concept_id}: {concept.prefLabel}{alt_str}")

        return 0

    elif args.vocab_command == 'lookup':
        label = args.label

        if not vocab:
            print("No vocabulary found. Create local-vocabulary.yaml or run 'inventory-md parse' first.")
            return 1

        concept = vocabulary.lookup_concept(label, vocab)

        if concept:
            print(f"Found: {concept.id}")
            print(f"  prefLabel: {concept.prefLabel}")
            if concept.altLabels:
                print(f"  altLabels: {', '.join(concept.altLabels)}")
            if concept.broader:
                print(f"  broader: {', '.join(concept.broader)}")
            if concept.narrower:
                print(f"  narrower: {', '.join(concept.narrower)}")
            print(f"  source: {concept.source}")
        else:
            print(f"No concept found for '{label}'")
            return 1

        return 0

    elif args.vocab_command == 'tree':
        if not vocab:
            print("No vocabulary found. Create local-vocabulary.yaml or run 'inventory-md parse' first.")
            return 1

        tree = vocabulary.build_category_tree(vocab)

        def print_tree(concept_id: str, indent: int = 0) -> None:
            concept = tree.concepts[concept_id]
            prefix = "  " * indent
            print(f"{prefix}{'▼' if concept.narrower else '○'} {concept.prefLabel} [{concept_id}]")
            for child_id in sorted(concept.narrower):
                if child_id in tree.concepts:
                    print_tree(child_id, indent + 1)

        print("Category Tree:\n")
        for root_id in tree.roots:
            print_tree(root_id)

        return 0

    else:
        # No subcommand - show help
        print("Local vocabulary management")
        print("\nSubcommands:")
        print("  list    List all concepts in vocabulary")
        print("  lookup  Look up a concept by label")
        print("  tree    Show category hierarchy as tree")
        print("\nUse 'inventory-md vocabulary <command> --help' for more info")
        return 1


if __name__ == '__main__':
    sys.exit(main())
