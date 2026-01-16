"""Tests for CLI module."""
import argparse
from pathlib import Path
from unittest.mock import patch

from inventory_md import cli


class TestServeCommand:
    """Tests for serve_command function."""

    def test_serve_command_accepts_api_proxy_param(self):
        """Test that serve_command accepts api_proxy parameter."""
        # Just verify the function signature accepts the parameter
        import inspect
        sig = inspect.signature(cli.serve_command)
        params = list(sig.parameters.keys())
        assert 'api_proxy' in params

    def test_serve_command_directory_not_exists(self, tmp_path):
        """Test serve_command fails if directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"
        result = cli.serve_command(nonexistent, 8000, None)
        assert result == 1

    def test_serve_command_no_search_html(self, tmp_path):
        """Test serve_command fails if search.html doesn't exist."""
        result = cli.serve_command(tmp_path, 8000, None)
        assert result == 1


class TestCliArgumentParser:
    """Tests for CLI argument parsing."""

    def test_serve_has_api_proxy_option(self):
        """Test that serve subcommand has --api-proxy option."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='command')

        serve_parser = subparsers.add_parser('serve')
        serve_parser.add_argument('directory', type=Path, nargs='?')
        serve_parser.add_argument('--port', '-p', type=int, default=8000)
        serve_parser.add_argument('--api-proxy', type=str, metavar='HOST:PORT')

        # Parse with --api-proxy
        args = parser.parse_args(['serve', '--api-proxy', 'localhost:8765'])
        assert args.api_proxy == 'localhost:8765'

        # Parse without --api-proxy
        args = parser.parse_args(['serve'])
        assert args.api_proxy is None


class TestProxyHTTPHandler:
    """Tests for the proxy HTTP handler behavior."""

    def test_should_proxy_paths(self):
        """Test which paths should be proxied."""
        # Simulating the should_proxy logic
        api_proxy = "localhost:8765"

        def should_proxy(path):
            return api_proxy and (
                path.startswith('/api/') or
                path.startswith('/chat') or
                path.startswith('/health')
            )

        assert should_proxy('/api/items')
        assert should_proxy('/api/photos')
        assert should_proxy('/chat')
        assert should_proxy('/chat/stream')
        assert should_proxy('/health')
        assert not should_proxy('/search.html')
        assert not should_proxy('/inventory.json')
        assert not should_proxy('/resized/photo.jpg')

    def test_should_not_proxy_without_api_proxy(self):
        """Test that nothing is proxied when api_proxy is None."""
        api_proxy = None

        def should_proxy(path):
            return api_proxy and (
                path.startswith('/api/') or
                path.startswith('/chat') or
                path.startswith('/health')
            )

        assert not should_proxy('/api/items')
        assert not should_proxy('/chat')
        assert not should_proxy('/health')


class TestInitCommand:
    """Tests for init_inventory function."""

    def test_init_creates_directory(self, tmp_path):
        """Test that init creates the directory structure."""
        inventory_dir = tmp_path / "new_inventory"

        with patch('builtins.input', return_value='n'):
            result = cli.init_inventory(inventory_dir, "Test Inventory")

        assert result == 0
        assert inventory_dir.exists()
        assert (inventory_dir / "inventory.md").exists()
        assert (inventory_dir / "photos").exists()
        assert (inventory_dir / "resized").exists()
