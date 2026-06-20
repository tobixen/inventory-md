"""extract_barcodes must be importable even when pyzbar/PIL are missing.

Importing the module must never kill the interpreter (a module-level sys.exit
turns into a SystemExit during pytest collection, aborting the whole session).
This runs in a subprocess with pyzbar blocked, so it exercises the
missing-dependency path regardless of whether pyzbar is installed in the test
environment.
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )


def test_importable_without_pyzbar():
    """Importing the module with pyzbar absent succeeds (no SystemExit)."""
    code = (
        "import sys;"
        "sys.modules['pyzbar'] = None;"
        "sys.modules['pyzbar.pyzbar'] = None;"
        f"sys.path.insert(0, {str(SCRIPTS)!r});"
        "import extract_barcodes as eb;"
        "assert eb.HAS_BARCODE_DEPS is False;"
        "print('OK')"
    )
    result = _run(code)
    assert result.returncode == 0, f"import failed: {result.stderr}"
    assert "OK" in result.stdout


def test_extract_barcodes_raises_without_pyzbar():
    """Calling extract_barcodes without the deps gives a clear error, not a crash."""
    code = (
        "import sys;"
        "sys.modules['pyzbar'] = None;"
        "sys.modules['pyzbar.pyzbar'] = None;"
        f"sys.path.insert(0, {str(SCRIPTS)!r});"
        "import extract_barcodes as eb;"
        "from pathlib import Path;"
        "\ntry:\n"
        "    eb.extract_barcodes(Path('x.jpg'));\n"
        "    print('NO_ERROR')\n"
        "except RuntimeError as e:\n"
        "    print('RUNTIME_ERROR' if 'pyzbar' in str(e).lower() else 'WRONG_MSG')\n"
    )
    result = _run(code)
    assert result.returncode == 0, f"subprocess crashed: {result.stderr}"
    assert "RUNTIME_ERROR" in result.stdout, result.stdout
