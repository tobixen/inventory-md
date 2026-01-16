"""Tests for api_server modifications functions."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if fastapi is not available
fastapi = pytest.importorskip("fastapi", reason="fastapi not installed (install with pip install inventory-md[chat])")

# Mock python-multipart before importing FastAPI-based modules
# Need to set __version__ to pass FastAPI's version check
mock_multipart = MagicMock()
mock_multipart.__version__ = "0.0.20"
mock_multipart_multipart = MagicMock()
mock_multipart_multipart.parse_options_header = MagicMock()

sys.modules['python_multipart'] = mock_multipart
sys.modules['multipart'] = mock_multipart
sys.modules['multipart.multipart'] = mock_multipart_multipart


@pytest.fixture
def temp_inventory():
    """Create a temporary inventory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create inventory.md
        inventory_md = tmppath / "inventory.md"
        inventory_md.write_text("""# Box A1 ID:A1

* Hammer
* Screwdriver set with 10 bits
* Wrench

# Box B2 ID:B2

* Empty box
""")

        # Create inventory.json (minimal)
        inventory_json = tmppath / "inventory.json"
        inventory_json.write_text("""{
    "containers": [
        {"id": "A1", "heading": "Box A1", "items": ["Hammer", "Screwdriver set with 10 bits", "Wrench"]},
        {"id": "B2", "heading": "Box B2", "items": ["Empty box"]}
    ]
}""")

        yield tmppath


class TestRemoveItemFromContainer:
    """Tests for remove_item_from_container function."""

    def test_returns_removed_item_text(self, temp_inventory):
        """Test that remove_item_from_container returns the actual removed item text."""
        from inventory_md import api_server

        # Set up the module state
        api_server.inventory_path = temp_inventory / "inventory.json"
        api_server.inventory_data = {
            "containers": [
                {"id": "A1", "heading": "Box A1", "items": ["Hammer", "Screwdriver set with 10 bits", "Wrench"]},
            ]
        }

        with patch.object(api_server, 'git_commit') as mock_git:
            with patch.object(api_server, 'reload_inventory'):
                result = api_server.remove_item_from_container("A1", "Screwdriver")

        assert result.get("success") is True
        assert "removed_item" in result
        assert result["removed_item"] == "Screwdriver set with 10 bits"
        mock_git.assert_called_once()

    def test_partial_match_returns_full_item(self, temp_inventory):
        """Test that a partial match returns the full item text."""
        from inventory_md import api_server

        api_server.inventory_path = temp_inventory / "inventory.json"
        api_server.inventory_data = {
            "containers": [
                {"id": "A1", "heading": "Box A1", "items": ["Hammer"]},
            ]
        }

        with patch.object(api_server, 'git_commit'):
            with patch.object(api_server, 'reload_inventory'):
                result = api_server.remove_item_from_container("A1", "Ham")

        assert result.get("success") is True
        assert result["removed_item"] == "Hammer"


class TestAddTodo:
    """Tests for add_todo function."""

    def test_add_todo_commits_to_git(self, temp_inventory):
        """Test that add_todo calls git_commit."""
        from inventory_md import api_server

        api_server.inventory_path = temp_inventory / "inventory.json"

        with patch.object(api_server, 'git_commit') as mock_git:
            result = api_server.add_todo("Test task description", "high")

        assert result.get("success") is True
        mock_git.assert_called_once()
        # Check the commit message includes "TODO"
        call_args = mock_git.call_args[0][0]
        assert "TODO" in call_args

    def test_add_todo_truncates_long_descriptions_in_commit(self, temp_inventory):
        """Test that long task descriptions are truncated in commit message."""
        from inventory_md import api_server

        api_server.inventory_path = temp_inventory / "inventory.json"

        long_description = "A" * 100  # 100 characters

        with patch.object(api_server, 'git_commit') as mock_git:
            api_server.add_todo(long_description, "medium")

        call_args = mock_git.call_args[0][0]
        # Should be truncated to 50 chars + "..."
        assert len(call_args) < 100
        assert "..." in call_args

    def test_add_todo_writes_to_file(self, temp_inventory):
        """Test that add_todo actually writes to TODO.md."""
        from inventory_md import api_server

        api_server.inventory_path = temp_inventory / "inventory.json"

        with patch.object(api_server, 'git_commit'):
            api_server.add_todo("My test task", "low")

        todo_path = temp_inventory / "TODO.md"
        assert todo_path.exists()
        content = todo_path.read_text()
        assert "My test task" in content
        assert "🟢" in content  # low priority marker


class TestMoveItem:
    """Tests for move_item function."""

    def test_move_item_success(self, temp_inventory):
        """Test successful item move between containers."""
        from inventory_md import api_server

        api_server.inventory_path = temp_inventory / "inventory.json"
        api_server.inventory_data = {
            "containers": [
                {"id": "A1", "heading": "Box A1", "items": ["Hammer", "Wrench"]},
                {"id": "B2", "heading": "Box B2", "items": ["Empty box"]},
            ]
        }

        with patch.object(api_server, 'git_commit'):
            with patch.object(api_server, 'reload_inventory'):
                result = api_server.move_item("A1", "B2", "Hammer")

        assert result.get("success") is True
        assert result["source"] == "A1"
        assert result["destination"] == "B2"
        assert result["item"] == "Hammer"
        assert "Moved" in result["message"]

    def test_move_item_source_not_found(self, temp_inventory):
        """Test move_item fails when source container doesn't exist."""
        from inventory_md import api_server

        api_server.inventory_path = temp_inventory / "inventory.json"
        api_server.inventory_data = {"containers": []}

        result = api_server.move_item("NONEXISTENT", "B2", "Hammer")

        assert "error" in result
        assert "NONEXISTENT" in result["error"]

    def test_move_item_item_not_found(self, temp_inventory):
        """Test move_item fails when item doesn't exist in source."""
        from inventory_md import api_server

        api_server.inventory_path = temp_inventory / "inventory.json"
        api_server.inventory_data = {
            "containers": [
                {"id": "A1", "heading": "Box A1", "items": ["Hammer"]},
            ]
        }

        with patch.object(api_server, 'git_commit'):
            with patch.object(api_server, 'reload_inventory'):
                result = api_server.move_item("A1", "B2", "NonexistentItem")

        assert "error" in result


class TestExecuteTool:
    """Tests for execute_tool function."""

    def test_execute_move_item_tool(self, temp_inventory):
        """Test that execute_tool correctly dispatches move_item."""
        from inventory_md import api_server

        api_server.inventory_path = temp_inventory / "inventory.json"
        api_server.inventory_data = {
            "containers": [
                {"id": "A1", "heading": "Box A1", "items": ["Hammer"]},
                {"id": "B2", "heading": "Box B2", "items": []},
            ]
        }

        with patch.object(api_server, 'git_commit'):
            with patch.object(api_server, 'reload_inventory'):
                result = api_server.execute_tool("move_item", {
                    "source_container_id": "A1",
                    "destination_container_id": "B2",
                    "item_description": "Hammer"
                })

        assert result.get("success") is True


class TestSecurityFunctions:
    """Tests for security helper functions."""

    def test_sanitize_path_component_basic(self):
        """Test basic path component sanitization."""
        from inventory_md.api_server import sanitize_path_component

        assert sanitize_path_component("photo.jpg") == "photo.jpg"
        assert sanitize_path_component("my-photo_123.png") == "my-photo_123.png"

    def test_sanitize_path_component_removes_path_separators(self):
        """Test that path separators are removed."""
        from inventory_md.api_server import sanitize_path_component

        assert sanitize_path_component("../etc/passwd") == "etcpasswd"
        assert sanitize_path_component("..\\..\\windows\\system32") == "windowssystem32"
        assert sanitize_path_component("foo/bar/baz.jpg") == "foobarbaz.jpg"

    def test_sanitize_path_component_removes_parent_refs(self):
        """Test that parent directory references are removed."""
        from inventory_md.api_server import sanitize_path_component

        assert sanitize_path_component("....test") == "test"
        assert sanitize_path_component("..photo..") == "photo"

    def test_sanitize_path_component_rejects_empty(self):
        """Test that empty strings are rejected."""
        from inventory_md.api_server import sanitize_path_component

        with pytest.raises(ValueError):
            sanitize_path_component("")

        with pytest.raises(ValueError):
            sanitize_path_component("...")

        with pytest.raises(ValueError):
            sanitize_path_component("../")

    def test_sanitize_path_component_removes_null_bytes(self):
        """Test that null bytes are removed."""
        from inventory_md.api_server import sanitize_path_component

        assert sanitize_path_component("photo\x00.jpg") == "photo.jpg"

    def test_sanitize_path_component_length_limit(self):
        """Test that long names are truncated."""
        from inventory_md.api_server import sanitize_path_component

        long_name = "a" * 200 + ".jpg"
        result = sanitize_path_component(long_name)
        assert len(result) <= 100

    def test_validate_container_id_valid(self):
        """Test valid container IDs."""
        from inventory_md.api_server import validate_container_id

        assert validate_container_id("A1") == "A1"
        assert validate_container_id("Box12") == "Box12"
        assert validate_container_id("GH-Tower-1") == "GH-Tower-1"
        assert validate_container_id("container_123") == "container_123"

    def test_validate_container_id_rejects_path_traversal(self):
        """Test that path traversal attempts are rejected."""
        from inventory_md.api_server import validate_container_id

        with pytest.raises(ValueError):
            validate_container_id("../etc")

        with pytest.raises(ValueError):
            validate_container_id("A1/../../etc")

        with pytest.raises(ValueError):
            validate_container_id("A1\\..\\..\\windows")

    def test_validate_container_id_rejects_special_chars(self):
        """Test that special characters are rejected."""
        from inventory_md.api_server import validate_container_id

        with pytest.raises(ValueError):
            validate_container_id("A1; rm -rf /")

        with pytest.raises(ValueError):
            validate_container_id("A1 && cat /etc/passwd")

        with pytest.raises(ValueError):
            validate_container_id("A1|whoami")

    def test_validate_container_id_rejects_empty(self):
        """Test that empty container IDs are rejected."""
        from inventory_md.api_server import validate_container_id

        with pytest.raises(ValueError):
            validate_container_id("")

        with pytest.raises(ValueError):
            validate_container_id(None)

    def test_validate_container_id_rejects_too_long(self):
        """Test that overly long container IDs are rejected."""
        from inventory_md.api_server import validate_container_id

        with pytest.raises(ValueError):
            validate_container_id("A" * 100)
