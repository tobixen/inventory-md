"""Tests for config module."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from inventory_md import config


class TestFindConfigFile:
    """Tests for find_config_file function."""

    def test_find_config_in_cwd_json(self, tmp_path, monkeypatch):
        """Test finding config file in current directory (JSON)."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "inventory-md.json"
        config_file.write_text('{"test": true}')

        result = config.find_config_file()
        assert result == config_file

    def test_find_config_in_cwd_yaml_preferred(self, tmp_path, monkeypatch):
        """Test that YAML is preferred over JSON in same directory."""
        monkeypatch.chdir(tmp_path)
        json_file = tmp_path / "inventory-md.json"
        yaml_file = tmp_path / "inventory-md.yaml"
        json_file.write_text('{"test": "json"}')
        yaml_file.write_text('test: yaml')

        result = config.find_config_file()
        assert result == yaml_file

    def test_find_config_in_user_dir(self, tmp_path, monkeypatch):
        """Test finding config in user config directory."""
        monkeypatch.chdir(tmp_path)  # Empty cwd, no config there

        user_config_dir = tmp_path / ".config" / "inventory-md"
        user_config_dir.mkdir(parents=True)
        config_file = user_config_dir / "config.json"
        config_file.write_text('{"test": true}')

        with patch.object(config, '_get_config_dirs', return_value=[
            tmp_path,  # cwd (empty)
            user_config_dir.parent.parent / ".config" / "inventory-md",
            Path("/etc/inventory-md"),
        ]):
            # Need to mock the home path used for user config
            with patch.object(Path, 'home', return_value=tmp_path):
                result = config.find_config_file()

        assert result == config_file

    def test_find_config_returns_none_when_not_found(self, tmp_path, monkeypatch):
        """Test that None is returned when no config file exists."""
        monkeypatch.chdir(tmp_path)

        with patch.object(config, '_get_config_dirs', return_value=[tmp_path]):
            result = config.find_config_file()

        assert result is None


class TestDeepMerge:
    """Tests for _deep_merge function."""

    def test_simple_merge(self):
        """Test merging flat dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = config._deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}
        assert result is base  # Modified in place

    def test_nested_merge(self):
        """Test merging nested dictionaries."""
        base = {"api": {"host": "localhost", "port": 8000}}
        override = {"api": {"port": 9000}}
        result = config._deep_merge(base, override)

        assert result == {"api": {"host": "localhost", "port": 9000}}

    def test_deep_nested_merge(self):
        """Test deeply nested merge."""
        base = {"level1": {"level2": {"a": 1, "b": 2}}}
        override = {"level1": {"level2": {"b": 3}}}
        result = config._deep_merge(base, override)

        assert result == {"level1": {"level2": {"a": 1, "b": 3}}}


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_json_config(self, tmp_path):
        """Test loading JSON config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"inventory_file": "/path/to/inv.md", "api": {"port": 9000}}')

        result = config.load_config(config_file)

        assert result["inventory_file"] == "/path/to/inv.md"
        assert result["api"]["port"] == 9000
        assert result["api"]["host"] == "127.0.0.1"  # From defaults

    def test_load_config_with_defaults(self, tmp_path):
        """Test that defaults are applied when loading config."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        result = config.load_config(config_file)

        assert result["api"]["host"] == "127.0.0.1"
        assert result["api"]["port"] == 8765
        assert result["serve"]["host"] == "127.0.0.1"
        assert result["serve"]["port"] == 8000

    def test_load_config_no_file(self, tmp_path, monkeypatch):
        """Test loading config when no file exists."""
        monkeypatch.chdir(tmp_path)

        with patch.object(config, 'find_config_file', return_value=None):
            result = config.load_config()

        # Should return defaults
        assert result["api"]["port"] == 8765
        assert result["serve"]["port"] == 8000

    def test_load_yaml_config_raises_without_pyyaml(self, tmp_path):
        """Test that loading YAML raises ImportError without pyyaml."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("api:\n  port: 9000")

        # Mock yaml import to fail
        with patch.dict('sys.modules', {'yaml': None}):
            with pytest.raises(ImportError, match="PyYAML required"):
                config.load_config(config_file)


class TestEnvOverrides:
    """Tests for environment variable overrides."""

    def test_simple_env_override(self, tmp_path, monkeypatch):
        """Test simple environment variable override."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        monkeypatch.setenv("INVENTORY_MD_BASE_URL", "https://example.com")

        result = config.load_config(config_file)
        assert result["base_url"] == "https://example.com"

    def test_nested_env_override(self, tmp_path, monkeypatch):
        """Test nested environment variable override with double underscore."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        monkeypatch.setenv("INVENTORY_MD_API__PORT", "9999")

        result = config.load_config(config_file)
        assert result["api"]["port"] == 9999

    def test_env_override_boolean(self, tmp_path, monkeypatch):
        """Test environment variable boolean conversion."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        monkeypatch.setenv("INVENTORY_MD_DEBUG", "true")
        result = config.load_config(config_file)
        assert result["debug"] is True

        monkeypatch.setenv("INVENTORY_MD_DEBUG", "false")
        result = config.load_config(config_file)
        assert result["debug"] is False


class TestConvertValue:
    """Tests for _convert_value function."""

    def test_convert_integer(self):
        """Test converting string to integer."""
        assert config._convert_value("123") == 123
        assert config._convert_value("-45") == -45

    def test_convert_float(self):
        """Test converting string to float."""
        assert config._convert_value("3.14") == 3.14
        assert config._convert_value("-2.5") == -2.5

    def test_convert_boolean(self):
        """Test converting string to boolean."""
        assert config._convert_value("true") is True
        assert config._convert_value("True") is True
        assert config._convert_value("yes") is True
        assert config._convert_value("1") is True

        assert config._convert_value("false") is False
        assert config._convert_value("False") is False
        assert config._convert_value("no") is False
        assert config._convert_value("0") is False

    def test_convert_string(self):
        """Test that non-numeric strings stay as strings."""
        assert config._convert_value("hello") == "hello"
        assert config._convert_value("/path/to/file") == "/path/to/file"


class TestGetConfigValue:
    """Tests for get_config_value function."""

    def test_simple_key(self):
        """Test getting simple key."""
        cfg = {"inventory_file": "/path/to/inv.md"}
        assert config.get_config_value(cfg, "inventory_file") == "/path/to/inv.md"

    def test_dot_notation(self):
        """Test getting nested value with dot notation."""
        cfg = {"api": {"host": "localhost", "port": 8000}}
        assert config.get_config_value(cfg, "api.host") == "localhost"
        assert config.get_config_value(cfg, "api.port") == 8000

    def test_missing_key_returns_default(self):
        """Test that missing key returns default."""
        cfg = {"api": {"host": "localhost"}}
        assert config.get_config_value(cfg, "nonexistent") is None
        assert config.get_config_value(cfg, "nonexistent", "default") == "default"
        assert config.get_config_value(cfg, "api.missing", 42) == 42


class TestConfigClass:
    """Tests for Config class."""

    def test_config_loads_from_file(self, tmp_path, monkeypatch):
        """Test Config class loads from file."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "inventory-md.json"
        config_file.write_text('{"inventory_file": "/custom/path.md", "api": {"port": 9999}}')

        cfg = config.Config()

        assert cfg.path == config_file
        assert cfg.inventory_file == Path("/custom/path.md")
        assert cfg.api_port == 9999
        assert cfg.api_host == "127.0.0.1"  # From defaults

    def test_config_explicit_path(self, tmp_path):
        """Test Config class with explicit path."""
        config_file = tmp_path / "my-config.json"
        config_file.write_text('{"base_url": "https://test.example.com"}')

        cfg = config.Config(config_file)

        assert cfg.path == config_file
        assert cfg.base_url == "https://test.example.com"

    def test_config_get_method(self, tmp_path, monkeypatch):
        """Test Config.get() method."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "inventory-md.json"
        config_file.write_text('{"labels": {"format": "custom"}}')

        cfg = config.Config()

        assert cfg.get("labels.format") == "custom"
        assert cfg.get("nonexistent", "fallback") == "fallback"

    def test_config_properties(self, tmp_path, monkeypatch):
        """Test Config convenience properties."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "inventory-md.json"
        config_file.write_text(json.dumps({
            "inventory_file": "/inv.md",
            "wanted_file": "/wanted.txt",
            "base_url": "https://inv.example.com",
            "api": {"host": "0.0.0.0", "port": 8888},
            "serve": {"host": "0.0.0.0", "port": 3000},
        }))

        cfg = config.Config()

        assert cfg.inventory_file == Path("/inv.md")
        assert cfg.wanted_file == Path("/wanted.txt")
        assert cfg.base_url == "https://inv.example.com"
        assert cfg.api_host == "0.0.0.0"
        assert cfg.api_port == 8888
        assert cfg.serve_host == "0.0.0.0"
        assert cfg.serve_port == 3000

    def test_config_no_file_uses_defaults(self, tmp_path, monkeypatch):
        """Test Config with no file uses defaults."""
        monkeypatch.chdir(tmp_path)

        cfg = config.Config()

        assert cfg.path is None
        assert cfg.inventory_file is None
        assert cfg.api_port == 8765
        assert cfg.serve_port == 8000
