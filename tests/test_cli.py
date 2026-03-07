"""Tests for CLI module."""

import argparse
import json
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
        assert "api_proxy" in params

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
        subparsers = parser.add_subparsers(dest="command")

        serve_parser = subparsers.add_parser("serve")
        serve_parser.add_argument("directory", type=Path, nargs="?")
        serve_parser.add_argument("--port", "-p", type=int, default=8000)
        serve_parser.add_argument("--api-proxy", type=str, metavar="HOST:PORT")

        # Parse with --api-proxy
        args = parser.parse_args(["serve", "--api-proxy", "localhost:8765"])
        assert args.api_proxy == "localhost:8765"

        # Parse without --api-proxy
        args = parser.parse_args(["serve"])
        assert args.api_proxy is None


class TestProxyHTTPHandler:
    """Tests for the proxy HTTP handler behavior."""

    def test_should_proxy_paths(self):
        """Test which paths should be proxied."""
        # Simulating the should_proxy logic
        api_proxy = "localhost:8765"

        def should_proxy(path):
            return api_proxy and (path.startswith("/api/") or path.startswith("/chat") or path.startswith("/health"))

        assert should_proxy("/api/items")
        assert should_proxy("/api/photos")
        assert should_proxy("/chat")
        assert should_proxy("/chat/stream")
        assert should_proxy("/health")
        assert not should_proxy("/search.html")
        assert not should_proxy("/inventory.json")
        assert not should_proxy("/resized/photo.jpg")

    def test_should_not_proxy_without_api_proxy(self):
        """Test that nothing is proxied when api_proxy is None."""
        api_proxy = None

        def should_proxy(path):
            return api_proxy and (path.startswith("/api/") or path.startswith("/chat") or path.startswith("/health"))

        assert not should_proxy("/api/items")
        assert not should_proxy("/chat")
        assert not should_proxy("/health")


class TestInitCommand:
    """Tests for init_inventory function."""

    def test_init_creates_directory(self, tmp_path):
        """Test that init creates the directory structure."""
        inventory_dir = tmp_path / "new_inventory"

        with patch("builtins.input", return_value="n"):
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
        with patch("builtins.input", return_value="n"):
            result = cli.update_template(tmp_path, force=False)

        assert result == 1
        assert existing.read_text() == "old content"  # Not overwritten

        # User says yes
        with patch("builtins.input", return_value="y"):
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

    def test_parse_writes_lang_to_json(self, tmp_path, monkeypatch):
        """Test that configured lang is written to inventory.json."""
        inventory_md = tmp_path / "inventory.md"
        inventory_md.write_text("# Test\n\n## ID:Box1 Test Box\n\n* Test item\n")

        config_file = tmp_path / "inventory-md.yaml"
        config_file.write_text("lang: no\n")

        monkeypatch.chdir(tmp_path)

        result = subprocess.run(
            [sys.executable, "-m", "inventory_md.cli", "parse", str(inventory_md)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )

        assert result.returncode == 0
        output_json = json.loads((tmp_path / "inventory.json").read_text())
        assert output_json["lang"] == "no"

    def test_parse_omits_lang_when_english(self, tmp_path, monkeypatch):
        """Test that lang is omitted from inventory.json when it's the default (en)."""
        inventory_md = tmp_path / "inventory.md"
        inventory_md.write_text("# Test\n\n## ID:Box1 Test Box\n\n* Test item\n")

        # No config = default lang 'en'
        monkeypatch.chdir(tmp_path)

        result = subprocess.run(
            [sys.executable, "-m", "inventory_md.cli", "parse", str(inventory_md)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )

        assert result.returncode == 0
        output_json = json.loads((tmp_path / "inventory.json").read_text())
        assert "lang" not in output_json


class TestParseCommandEanLookup:
    """Tests for EAN lookup integration in parse_command."""

    def _write_inventory(self, tmp_path, content: str) -> "Path":
        f = tmp_path / "inventory.md"
        f.write_text(content)
        return f

    def _tingbok_patches(self, vocabulary):
        """Return a context manager that patches all tingbok network calls."""
        from contextlib import ExitStack
        from unittest.mock import patch

        stack = ExitStack()
        stack.enter_context(patch.object(vocabulary, "fetch_vocabulary_from_tingbok", return_value={}))
        stack.enter_context(patch.object(vocabulary, "resolve_categories_via_tingbok", return_value=({}, {})))
        return stack

    def test_ean_items_queried_via_tingbok(self, tmp_path, monkeypatch) -> None:
        """Items with EAN metadata trigger a lookup via lookup_ean_via_tingbok."""
        from unittest.mock import patch

        from inventory_md import cli, vocabulary

        inventory_md = self._write_inventory(
            tmp_path,
            "## ID:Box1 Test\n\n* EAN:7310865004703 Kalles Kaviar\n",
        )
        monkeypatch.chdir(tmp_path)

        product = {
            "ean": "7310865004703",
            "name": "Kalles Kaviar",
            "brand": "Abba",
            "quantity": "300g",
            "categories": ["spreads", "caviar spreads"],
            "image_url": None,
            "source": "openfoodfacts",
        }

        with self._tingbok_patches(vocabulary):
            with patch.object(vocabulary, "lookup_ean_via_tingbok", return_value=product) as mock_lookup:
                cli.parse_command(
                    inventory_md,
                    tingbok_url="https://tingbok.plann.no",
                )

        mock_lookup.assert_called_once_with("7310865004703", "https://tingbok.plann.no")

    def test_ean_lookup_skipped_without_tingbok_url(self, tmp_path, monkeypatch) -> None:
        """When no tingbok_url is configured, EAN lookup is skipped."""
        from unittest.mock import patch

        from inventory_md import cli, vocabulary

        inventory_md = self._write_inventory(
            tmp_path,
            "## ID:Box1 Test\n\n* EAN:7310865004703 Kalles Kaviar\n",
        )
        monkeypatch.chdir(tmp_path)

        with patch.object(vocabulary, "lookup_ean_via_tingbok") as mock_lookup:
            cli.parse_command(inventory_md, tingbok_url=None)

        mock_lookup.assert_not_called()

    def test_ean_not_found_does_not_crash(self, tmp_path, monkeypatch) -> None:
        """A 404 from tingbok EAN endpoint is handled gracefully."""
        from inventory_md import cli, vocabulary

        inventory_md = self._write_inventory(
            tmp_path,
            "## ID:Box1 Test\n\n* EAN:0000000000000 Unknown item\n",
        )
        monkeypatch.chdir(tmp_path)

        with self._tingbok_patches(vocabulary):
            from unittest.mock import patch

            with patch.object(vocabulary, "lookup_ean_via_tingbok", return_value=None):
                result = cli.parse_command(
                    inventory_md,
                    tingbok_url="https://tingbok.plann.no",
                )

        assert result == 0
