#!/usr/bin/env python3
"""
Command-line interface for Inventory System
"""
import argparse
import shutil
import sys
from pathlib import Path

from . import parser, shopping_list


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


def parse_command(md_file: Path, output: Path = None, validate_only: bool = False, wanted_items: Path = None, include_dated: bool = True) -> int:
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
                with urllib.request.urlopen(req, timeout=30) as response:
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
    with socketserver.TCPServer((host, port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped")
            return 0


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


def main() -> int:
    """Main entry point for the CLI."""
    parser_cli = argparse.ArgumentParser(
        description="Inventory System - Manage markdown-based inventories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize a new inventory
  inventory-system init ~/my-inventory --name "Home Storage"

  # Parse inventory and generate JSON
  inventory-system parse ~/my-inventory/inventory.md

  # Validate inventory without generating JSON
  inventory-system parse ~/my-inventory/inventory.md --validate

  # Start a local web server
  inventory-system serve ~/my-inventory

  # Start API server for chat, photos, and item management (requires ANTHROPIC_API_KEY)
  inventory-system api ~/my-inventory
        """
    )

    subparsers = parser_cli.add_subparsers(dest='command', help='Command to run')

    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new inventory')
    init_parser.add_argument('directory', type=Path, help='Directory to initialize')
    init_parser.add_argument('--name', type=str, default='My Inventory', help='Name of the inventory')

    # Parse command
    parse_parser = subparsers.add_parser('parse', help='Parse inventory markdown file')
    parse_parser.add_argument('file', type=Path, nargs='?', help='Inventory markdown file to parse (default: inventory.md with --auto)')
    parse_parser.add_argument('--output', '-o', type=Path, help='Output JSON file (default: inventory.json)')
    parse_parser.add_argument('--validate', action='store_true', help='Validate only, do not generate JSON')
    parse_parser.add_argument('--wanted-items', '-w', type=Path, help='Wanted items file to generate shopping list')
    parse_parser.add_argument('--no-dated', action='store_true', help='Exclude dated wanted-items files (wanted-items-YYYY-MM-DD.md)')
    parse_parser.add_argument('--auto', '-a', action='store_true',
                              help='Auto-detect files: inventory.md and wanted-items.md in current directory')

    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Start local web server')
    serve_parser.add_argument('directory', type=Path, nargs='?', help='Directory to serve (default: current directory)')
    serve_parser.add_argument('--port', '-p', type=int, default=8000, help='Port number (default: 8000)')
    serve_parser.add_argument('--host', type=str, default='127.0.0.1',
                              help='Host to bind to (default: 127.0.0.1, use 0.0.0.0 for all interfaces)')
    serve_parser.add_argument('--api-proxy', type=str, metavar='HOST:PORT',
                              help='Proxy /api/* and /chat requests to backend (e.g., localhost:8765)')

    # API command
    api_parser = subparsers.add_parser('api', help='Start API server (chat, photos, item management)')
    api_parser.add_argument('directory', type=Path, nargs='?', help='Directory with inventory.json (default: current directory)')
    api_parser.add_argument('--port', '-p', type=int, default=8765, help='Port number (default: 8765)')
    api_parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')

    # Chat command (backwards compatibility alias for 'api')
    chat_parser = subparsers.add_parser('chat', help='[Deprecated] Use "api" instead')
    chat_parser.add_argument('directory', type=Path, nargs='?', help='Directory with inventory.json (default: current directory)')
    chat_parser.add_argument('--port', '-p', type=int, default=8765, help='Port number (default: 8765)')
    chat_parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')

    args = parser_cli.parse_args()

    if args.command == 'init':
        return init_inventory(args.directory, args.name)
    elif args.command == 'parse':
        include_dated = not getattr(args, 'no_dated', False)
        auto_mode = getattr(args, 'auto', False)

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
        else:
            md_file = args.file
            wanted_items = getattr(args, 'wanted_items', None)
            if md_file is None:
                print("Error: inventory file required (or use --auto)", file=sys.stderr)
                return 1

        return parse_command(md_file, args.output, args.validate, wanted_items, include_dated)
    elif args.command == 'serve':
        return serve_command(args.directory, args.port, args.host, getattr(args, 'api_proxy', None))
    elif args.command == 'api' or args.command == 'chat':
        return api_command(args.directory, args.port, args.host)
    else:
        parser_cli.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
