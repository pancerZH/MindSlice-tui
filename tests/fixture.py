"""A small workspace that has one of everything the TUI shows."""

from __future__ import annotations

import hashlib
from pathlib import Path

from mindslice import Workspace

LEAD = "+++\ntitle = \"Team lead\"\n+++\n\nThe base slice names the lead.\n\n- Lead: Ada.\n"


def build(root: Path) -> Path:
    """Create ``root/ws``: a mounted slice ``@base`` under an overlay, with a staged change pending."""
    base = root / "base"
    (base / "team").mkdir(parents=True)
    (base / "team" / "lead.md").write_text(LEAD, encoding="utf-8")
    (base / "guide.md").write_text("# Guide\n\nPlain Markdown note in the base slice.\n", encoding="utf-8")
    with Workspace.init(root / "ws") as ws:
        ws.mount(base, alias="@base", precedence=50)

        def card(path: str, title: str, body: str, **fields) -> None:
            ws.write(path, title=title, summary=f"{title} summary.", content=body, stage=False,
                     reason=f"fixture: {path}", **fields)

        card("team/lead", "Team lead (current)", "- Lead: Grace.")  # shadows @base/team/lead
        card("notes/alpha", "Alpha", "- See [[notes/beta]] and [[missing/card]].")  # one link, one dangling
        card("notes/beta", "Beta", "- Beta fact about zebras.")
        card("notes/old", "Old rule", "- The old rule.")
        card("notes/new", "New rule", "- The new rule.", supersedes=["@overlay/notes/old"])
        card("notes/ext", "Exception", "- Except on Fridays.", extends=["@overlay/notes/old"])  # stale baseline
        card("notes/lone", "Lone", "- Nothing links here.")  # orphan
        card("prefs/language", "Reply language", "- Reply in Chinese.", load="always")
        ws.write("notes/beta", op="append", content=["- A staged statement."], stage=True, reason="fixture: staged")
    return root / "ws"


def memory_digest(workspace: Path) -> str:
    """Hash of everything except the disposable ``.cache``; unchanged means memory was not written."""
    digest = hashlib.sha256()
    for file in sorted(p for p in workspace.rglob("*") if p.is_file() and ".cache" not in p.parts):
        digest.update(str(file.relative_to(workspace)).encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()
