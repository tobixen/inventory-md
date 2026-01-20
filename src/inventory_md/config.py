"""
Configuration file system for inventory-md.

Supports loading configuration from:
1. ./inventory-md.yaml or ./inventory-md.json (current directory)
2. ~/.config/inventory-md/config.yaml or config.json
3. /etc/inventory-md/config.yaml or config.json

First found file wins. YAML is checked before JSON at each location.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_FILENAMES = ["inventory-md.yaml", "inventory-md.json"]
CONFIG_USER_FILENAMES = ["config.yaml", "config.json"]

DEFAULTS: dict[str, Any] = {
    "api": {"host": "127.0.0.1", "port": 8765},
    "serve": {"host": "127.0.0.1", "port": 8000},
    "labels": {
        "sheet_format": "48x25-40",
        "base_url": "https://inventory.example.com/search.html",
        "style": "standard",
        "show_date": True,
        "duplicate_qr": False,
    },
}


def _get_config_dirs() -> list[Path]:
    """Get list of config directories to search, in priority order."""
    return [
        Path.cwd(),
        Path.home() / ".config" / "inventory-md",
        Path("/etc/inventory-md"),
    ]


def find_config_file() -> Path | None:
    """Find first existing config file.

    Searches in order:
    1. ./inventory-md.yaml, ./inventory-md.json
    2. ~/.config/inventory-md/config.yaml, config.json
    3. /etc/inventory-md/config.yaml, config.json

    Returns the first found file, or None if no config file exists.
    """
    config_dirs = _get_config_dirs()

    for dir_path in config_dirs:
        # Use different filenames for cwd vs standard config dirs
        filenames = CONFIG_FILENAMES if dir_path == Path.cwd() else CONFIG_USER_FILENAMES
        for filename in filenames:
            path = dir_path / filename
            if path.exists():
                return path
    return None


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base dict, modifying base in place."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _deep_copy(d: dict) -> dict:
    """Create a deep copy of a nested dict structure."""
    result = {}
    for key, value in d.items():
        if isinstance(value, dict):
            result[key] = _deep_copy(value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config from file, merging with defaults.

    Args:
        path: Optional explicit path to config file. If None, searches
              standard locations.

    Returns:
        Merged configuration dictionary with defaults applied.

    Raises:
        ImportError: If YAML config is found but PyYAML is not installed.
        json.JSONDecodeError: If JSON config file is malformed.
    """
    if path is None:
        path = find_config_file()

    # Start with a deep copy of defaults
    config = _deep_copy(DEFAULTS)

    if path and path.exists():
        if path.suffix in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError as e:
                raise ImportError(
                    "PyYAML required for .yaml config files. "
                    "Install with: pip install inventory-md[yaml]"
                ) from e
            with open(path, encoding="utf-8") as f:
                file_config = yaml.safe_load(f) or {}
        else:
            with open(path, encoding="utf-8") as f:
                file_config = json.load(f)

        _deep_merge(config, file_config)

    # Apply environment variable overrides (INVENTORY_MD_*)
    _apply_env_overrides(config)

    return config


def _apply_env_overrides(config: dict[str, Any]) -> None:
    """Apply environment variable overrides to config.

    Environment variables are named INVENTORY_MD_<KEY> where nested
    keys use double underscore, e.g., INVENTORY_MD_API__PORT=9000
    """
    prefix = "INVENTORY_MD_"
    for key, value in os.environ.items():
        if key.startswith(prefix):
            config_key = key[len(prefix) :].lower()
            _set_nested_value(config, config_key, value)


def _set_nested_value(config: dict, key: str, value: str) -> None:
    """Set a nested config value using double-underscore notation.

    e.g., "api__port" sets config["api"]["port"]
    """
    parts = key.split("__")
    target = config
    for part in parts[:-1]:
        if part not in target:
            target[part] = {}
        target = target[part]

    final_key = parts[-1]
    # Try to convert to int/bool if possible
    target[final_key] = _convert_value(value)


def _convert_value(value: str) -> Any:
    """Convert string value to appropriate type."""
    # Boolean
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    # Integer
    try:
        return int(value)
    except ValueError:
        pass
    # Float
    try:
        return float(value)
    except ValueError:
        pass
    # String
    return value


def get_config_value(config: dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a config value using dot notation.

    Args:
        config: Configuration dictionary.
        key: Dot-separated key, e.g., "api.port" or "inventory_file".
        default: Default value if key not found.

    Returns:
        The config value, or default if not found.
    """
    parts = key.split(".")
    target = config
    for part in parts:
        if isinstance(target, dict) and part in target:
            target = target[part]
        else:
            return default
    return target


class Config:
    """Configuration holder with convenient access methods."""

    def __init__(self, path: Path | None = None):
        """Initialize config, loading from file if found.

        Args:
            path: Optional explicit path to config file.
        """
        self._path = path if path else find_config_file()
        self._data = load_config(self._path)

    @property
    def path(self) -> Path | None:
        """Return the path to the loaded config file, or None."""
        return self._path

    @property
    def data(self) -> dict[str, Any]:
        """Return the raw config dictionary."""
        return self._data

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation.

        Args:
            key: Dot-separated key, e.g., "api.port".
            default: Default value if key not found.

        Returns:
            The config value, or default if not found.
        """
        return get_config_value(self._data, key, default)

    # Convenience properties for common settings
    @property
    def inventory_file(self) -> Path | None:
        """Return inventory_file path if configured."""
        val = self.get("inventory_file")
        return Path(val) if val else None

    @property
    def wanted_file(self) -> Path | None:
        """Return wanted_file path if configured."""
        val = self.get("wanted_file")
        return Path(val) if val else None

    @property
    def base_url(self) -> str | None:
        """Return base_url if configured."""
        return self.get("base_url")

    @property
    def api_host(self) -> str:
        """Return API server host."""
        return self.get("api.host", "127.0.0.1")

    @property
    def api_port(self) -> int:
        """Return API server port."""
        return self.get("api.port", 8765)

    @property
    def serve_host(self) -> str:
        """Return web server host."""
        return self.get("serve.host", "127.0.0.1")

    @property
    def serve_port(self) -> int:
        """Return web server port."""
        return self.get("serve.port", 8000)

    @property
    def labels_base_url(self) -> str:
        """Return labels base URL."""
        return self.get("labels.base_url", "https://inventory.example.com/search.html")

    @property
    def labels_sheet_format(self) -> str:
        """Return default label sheet format."""
        return self.get("labels.sheet_format", "48x25-40")

    @property
    def labels_style(self) -> str:
        """Return default label style."""
        return self.get("labels.style", "standard")

    @property
    def labels_show_date(self) -> bool:
        """Return whether to show date on labels."""
        return self.get("labels.show_date", True)

    @property
    def labels_duplicate_qr(self) -> bool:
        """Return whether to duplicate QR codes on labels."""
        return self.get("labels.duplicate_qr", False)

    @property
    def labels_custom_formats(self) -> dict:
        """Return custom label sheet formats from config."""
        return self.get("labels.custom_formats", {})
