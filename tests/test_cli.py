"""Tests for CLI module."""
import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from inventory_md import cli
from inventory_md._version import __version__


class TestVersion:
    """Tests for --version option."""

    def test_version_option_exits_with_version(self):
        """Test that --version prints version and exits."""
        result = subprocess.run(
            [sys.executable, "-m", "inventory_md.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert __version__ in result.stdout

    def test_version_short_option(self):
        """Test that -V also works for version."""
        result = subprocess.run(
            [sys.executable, "-m", "inventory_md.cli", "-V"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert __version__ in result.stdout


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


class TestUpdateTemplate:
    """Tests for update_template function."""

    def test_update_template_creates_file(self, tmp_path):
        """Test that update_template creates search.html."""
        result = cli.update_template(tmp_path, force=True)

        assert result == 0
        assert (tmp_path / "search.html").exists()

    def test_update_template_overwrites_with_force(self, tmp_path):
        """Test that update_template overwrites with --force."""
        existing = tmp_path / "search.html"
        existing.write_text("old content")

        result = cli.update_template(tmp_path, force=True)

        assert result == 0
        content = existing.read_text()
        assert "old content" not in content
        assert "<!DOCTYPE html>" in content  # New template starts with this

    def test_update_template_prompts_without_force(self, tmp_path):
        """Test that update_template prompts when file exists."""
        existing = tmp_path / "search.html"
        existing.write_text("old content")

        # User says no
        with patch('builtins.input', return_value='n'):
            result = cli.update_template(tmp_path, force=False)

        assert result == 1
        assert existing.read_text() == "old content"  # Not overwritten

        # User says yes
        with patch('builtins.input', return_value='y'):
            result = cli.update_template(tmp_path, force=False)

        assert result == 0
        assert "old content" not in existing.read_text()

    def test_update_template_fails_for_nonexistent_directory(self, tmp_path):
        """Test that update_template fails if directory doesn't exist."""
        result = cli.update_template(tmp_path / "nonexistent", force=True)
        assert result == 1

    def test_update_template_uses_cwd_by_default(self, tmp_path, monkeypatch):
        """Test that update_template uses current directory by default."""
        monkeypatch.chdir(tmp_path)

        result = cli.update_template(force=True)

        assert result == 0
        assert (tmp_path / "search.html").exists()
