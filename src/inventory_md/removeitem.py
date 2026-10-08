"""Remove an existing item line from ``inventory.md``.

The deletion counterpart to :mod:`inventory_md.additem` and
:mod:`inventory_md.moveitem`.  By convention an item that is in the inventory has
not been consumed, and one that has disappeared has; the git history of
``inventory.md`` is the consumption record (purchase-pipeline's ``ledger.py
consumed`` joins on the date an ``ID:`` vanished).  So removing a line is all
there is to recording that something was used up or thrown away.

``remove_item`` locates the bullet by its ``ID:`` token and drops it together
with its deeper-indented sub-bullets, so no orphaned children are left behind.
An item with ``qty`` above one, or one that is not a plain number (``qty:4-5``),
is refused unless ``remove_all`` is given: using up one of several is
``inventory-md edit --qty``, and deleting the whole line by mistake would book
the rest as consumed.  A bullet with other ``ID:`` items nested under it is a
container and is always refused, since removing it would silently book every
one of those as consumed too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import moveitem as _moveitem
from . import parser as _parser


@dataclass
class RemoveResult:
    """Outcome of a :func:`remove_item` call.

    ``errors`` being non-empty means nothing was written.
    """

    item_id: str | None = None
    removed: list[str] = field(default_factory=list)
    from_container: str | None = None
    errors: list[str] = field(default_factory=list)
    written: bool = False


_ID_TOKEN_RE = re.compile(r"(?:^|\s)ID:(\S+)")


def _qty(line: str) -> float | str | None:
    return _parser.extract_metadata(line.lstrip()[2:])["metadata"].get("qty")


def remove_item(
    md_path: Path,
    *,
    item_id: str,
    remove_all: bool = False,
    dry_run: bool = False,
) -> RemoveResult:
    """Delete the item ``item_id`` and its sub-bullets from ``md_path``.

    On any error nothing is written and :class:`RemoveResult` carries the reason.
    With ``dry_run`` the removal is validated and the lines reported, but the
    file is left untouched (``result.written`` stays ``False``).
    """
    result = RemoveResult(item_id=item_id)

    if not md_path.exists():
        result.errors.append(f"{md_path} not found")
        return result

    text = md_path.read_text(encoding="utf-8")
    had_trailing_newline = text.endswith("\n")
    lines = text.splitlines()

    blocks = _moveitem.find_item_blocks(lines, item_id)
    if not blocks:
        result.errors.append(f"item ID:{item_id} not found as a bullet in {md_path.name}")
        return result
    if len(blocks) > 1:
        where = ", ".join(f"line {start + 1}" for start, _end in blocks)
        result.errors.append(
            f"item ID:{item_id} matches more than once in {md_path.name} ({where}) — "
            "IDs must be unique; fix the duplicate before removing"
        )
        return result

    start, end = blocks[0]
    result.removed = lines[start:end]
    result.from_container = _moveitem.container_of_line(lines, start)

    nested = [m.group(1) for line in lines[start + 1 : end] if (m := _ID_TOKEN_RE.search(line))]
    if nested:
        result.errors.append(
            f"item ID:{item_id} contains other items ({', '.join(nested)}) — move or remove those first"
        )
        return result

    qty = _qty(lines[start])
    shown = f"{qty:g}" if isinstance(qty, float) else qty
    if qty is not None and not (isinstance(qty, float) and qty <= 1) and not remove_all:
        result.errors.append(
            f"item ID:{item_id} has qty:{shown} — use 'edit --qty' to record using up part of it, "
            "or pass --all to remove the whole line"
        )
        return result

    if dry_run:
        return result

    new_text = "\n".join(lines[:start] + lines[end:])
    if had_trailing_newline:
        new_text += "\n"
    md_path.write_text(new_text, encoding="utf-8")
    result.written = True
    return result
