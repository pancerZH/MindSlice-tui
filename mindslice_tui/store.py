"""Access to a MindSlice workspace. The only module that touches the engine.

``Store.load()`` returns an immutable ``Snapshot`` of every card and edge; the UI renders
from it. Browsing writes no memory, and never calls ``Workspace.read()`` (which would bump
read telemetry). Only ``review()`` and ``bake()`` change memory, and the UI calls them only
after the user has ticked the changes and confirmed. ``ws.index`` and ``ws._reading`` are
engine internals; if the engine grows a public graph API, only this file changes.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mindslice import Workspace
from mindslice.model.addressing import extract_wikilinks, format_address
from mindslice.model.card import parse_card
from mindslice.storage.card_io import read_card_file
from mindslice.storage.config import load_slice_manifest


@dataclass(frozen=True)
class Mount:
    alias: str
    path: str
    precedence: int
    role: str
    kind: str  # "overlay" | "slice"
    version: str
    description: str


@dataclass(frozen=True)
class Card:
    address: str
    mount: str
    path: str
    title: str
    summary: str
    tags: tuple[str, ...]
    aliases: tuple[str, ...]
    always: bool
    mtime_ns: int
    sha256: str
    problems: tuple[str, ...]  # parse errors and warnings
    file: Path
    read_count: int


@dataclass(frozen=True)
class Edge:
    src: str
    kind: str  # "wikilink" | "extends" | "supersedes"
    raw: str  # the reference as written in the card
    dst: str | None  # None when the reference does not resolve


# What ranks a slice as the destination of a new card, strongest first (see Store.destinations).
SIGNALS = ("path", "links", "search")

# (name, edge kind, direction) of the relation groups shown for a focus card. The UI words them (i18n.py).
EDGE_GROUPS = (
    ("links_out", "wikilink", "out"),
    ("backlinks", "wikilink", "in"),
    ("extends", "extends", "out"),
    ("extended_by", "extends", "in"),
    ("supersedes", "supersedes", "out"),
    ("superseded_by", "supersedes", "in"),
)


@dataclass(frozen=True)
class Snapshot:
    root: Path
    mounts: tuple[Mount, ...]  # highest precedence first
    cards: dict[str, Card]
    out_edges: dict[str, list[Edge]] = field(repr=False)
    in_edges: dict[str, list[Edge]] = field(repr=False)
    shadowed: frozenset[str] = field(repr=False)  # cards hidden by a same-path card in a mount that wins
    status: dict[str, Any] = field(repr=False)
    validation: dict[str, Any] = field(repr=False)
    # Staged changes by card address: ``ws.diff("staging")`` items plus the staged card's ``title`` and
    # ``always``. A staged create has no entry in ``cards``.
    pending: dict[str, dict[str, Any]] = field(repr=False, default_factory=dict)

    def has(self, address: str | None) -> bool:
        """A live card, or a card that exists only as a staged create."""
        return address in self.cards or address in self.pending

    def neighbors(self, address: str, kind: str, direction: str) -> list[str]:
        """Addresses joined to ``address`` by resolved ``kind`` edges, in card order, without repeats."""
        if direction == "out":
            found = [e.dst for e in self.out_edges.get(address, []) if e.kind == kind and e.dst]
        else:
            found = [e.src for e in self.in_edges.get(address, []) if e.kind == kind]
        return list(dict.fromkeys(found))

    def dangling(self, address: str) -> list[Edge]:
        return [e for e in self.out_edges.get(address, []) if e.dst is None]

    def same_path(self, address: str) -> list[str]:
        """Cards at the same path in other mounts (they shadow, or are shadowed by, this one)."""
        path = address.partition("/")[2]  # also for a staged create, which has no Card
        twins = (format_address(m.alias, path) for m in self.mounts)
        return [twin for twin in twins if twin in self.cards and twin != address]

    def is_superseded(self, address: str) -> bool:
        return bool(self.neighbors(address, "supersedes", "in"))

    def is_orphan(self, address: str) -> bool:
        return not any(e.dst for e in self.out_edges.get(address, [])) and not self.in_edges.get(address)

    def relations(self, address: str) -> list[tuple[str, list[str]]]:
        """Every relation group of a card as ``(name, [target address])``; dangling references are separate."""
        groups = [(name, self.neighbors(address, kind, direction)) for name, kind, direction in EDGE_GROUPS]
        return [*groups, ("same_path", self.same_path(address))]

    def issues(self) -> list[tuple[str, str | None, str]]:
        """Things worth a look, as ``(kind, card address or None, detail)``.

        First the engine's validation report (kind ``error`` / ``warning``, detail its message; it covers
        broken references), then what only the graph shows: ``stale_extends`` and ``supersedes`` (detail
        is the other card's address), ``shadowed`` and ``orphan`` (no detail).
        """
        rows = [(i["severity"], i.get("address"), f"{i['code']}: {i['message']}")
                for i in self.validation["errors"] + self.validation["warnings"]]
        for address, card in self.cards.items():
            rows += [("stale_extends", address, base) for base in self.neighbors(address, "extends", "out")
                     if self.is_superseded(base)]
            rows += [("supersedes", address, old) for old in self.neighbors(address, "supersedes", "out")]
            if address in self.shadowed:
                rows.append(("shadowed", address, ""))
            if self.is_orphan(address) and not card.always:
                rows.append(("orphan", address, ""))
        return rows


class Store:
    def __init__(self, root: str | Path | None = None) -> None:
        self.ws = Workspace(root) if root else Workspace.discover()

    def close(self) -> None:
        self.ws.close()

    def load(self) -> Snapshot:
        ws = self.ws
        with ws._reading() as table:  # syncs the index cache if files changed
            roots = {m.alias: m for m in table.all()}
            mounts = []
            for m in table.all():
                manifest = load_slice_manifest(m.root)
                mounts.append(Mount(m.alias, m.path, m.precedence, m.role, m.kind, manifest.version, manifest.description))
            reads = {format_address(r[0], r[1]): r[2]
                     for r in ws.index.conn.execute("SELECT mount, path, read_count FROM telemetry")}
            cards, winners = {}, {}
            for row in ws.index.all_cards():  # highest precedence first: the first card at a path wins it
                address = format_address(row["mount"], row["path"])
                cards[address] = Card(
                    address=address, mount=row["mount"], path=row["path"], title=row["title"], summary=row["summary"],
                    tags=tuple(json.loads(row["tags"])), aliases=tuple(json.loads(row["aliases"])),
                    always=row["load"] == "always", mtime_ns=row["mtime_ns"], sha256=row["sha256"],
                    problems=tuple(json.loads(row["errors"]) + json.loads(row["warnings"])),
                    file=roots[row["mount"]].root / f"{row['path']}.md", read_count=reads.get(address, 0),
                )
                winners.setdefault(row["path"], address)
            out_edges, in_edges = defaultdict(list), defaultdict(list)
            links = ws.index.conn.execute(
                "SELECT src_mount, src_path, kind, raw, dst_mount, dst_path, resolved FROM links"
                " ORDER BY src_mount, src_path, kind, ord")
            for row in links:
                src = format_address(row["src_mount"], row["src_path"])
                dst = format_address(row["dst_mount"], row["dst_path"]) if row["resolved"] else None
                if dst == src:
                    continue
                edge = Edge(src, row["kind"], row["raw"], dst)
                out_edges[src].append(edge)
                if dst:
                    in_edges[dst].append(edge)
        pending = {}
        for item in self.staged()["items"]:
            text = None if item["op"] == "delete" else read_card_file(ws.staging.file(item["id"]))[0]
            front = parse_card(text).frontmatter if text else {}
            live = cards.get(item["address"])
            item["title"] = front.get("title") or (live.title if live else "")
            item["always"] = front.get("load") == "always" if text else bool(live and live.always)
            pending[item["address"]] = item
        return Snapshot(ws.root, tuple(mounts), cards, dict(out_edges), dict(in_edges),
                        frozenset(cards.keys() - winners.values()), ws.status(), ws.validate(), pending)

    def markdown(self, snapshot: Snapshot, address: str) -> str | None:
        """The card's summary and body, with resolved ``[[links]]`` turned into Markdown links to addresses.
        None when the file has gone since the snapshot was taken."""
        text, _ = read_card_file(snapshot.cards[address].file)
        if text is None:
            return None
        after = parse_card(text).after
        targets = {e.raw: e.dst for e in snapshot.out_edges.get(address, []) if e.kind == "wikilink" and e.dst}
        for link in reversed(extract_wikilinks(after)):
            if link.target in targets:
                after = f"{after[:link.start]}[{link.label or link.target}](<{targets[link.target]}>){after[link.end:]}"
        return after

    def search(self, query: str, k: int = 30) -> dict[str, Any]:
        return self.ws.search(query, k=k, max_neighbors=0)

    def destinations(self, snapshot: Snapshot, card: dict[str, Any]) -> list[tuple[str, tuple[int, int, float]]]:
        """The mounted slices ranked as the destination of an overlay ``card`` (a bake plan entry), best first,
        each with its scores for ``SIGNALS``: how many folders of the card's path its deepest card shares,
        how many of the card's links and backlinks lead into it, and its search hits for the card's title and
        summary, weighted by rank. Folders outweigh links, links outweigh search hits. Folders count only
        when a single slice goes deepest: a folder several slices have (``projects/``) tells them apart no
        better than none."""
        slices = [m.alias for m in snapshot.mounts if m.kind != "overlay"]
        folders = card["id"].split("/")[:-1]
        path = dict.fromkeys(slices, 0)
        for other in snapshot.cards.values():
            if other.mount in path and other.address != card["address"]:
                shared = len(os.path.commonprefix([folders, other.path.split("/")[:-1]]))
                path[other.mount] = max(path[other.mount], shared)
        if list(path.values()).count(max(path.values(), default=0)) > 1:
            path = dict.fromkeys(slices, 0)
        neighbors = [e.dst for e in snapshot.out_edges.get(card["address"], []) if e.dst]
        neighbors += [e.src for e in snapshot.in_edges.get(card["address"], [])]
        links = Counter(snapshot.cards[a].mount for a in neighbors if a in snapshot.cards)
        text = f"{card.get('title') or ''} {card['summary']}".strip()
        hits = [hit for hit in self.search(text, k=10)["results"] if hit["address"] != card["address"]] if text else []
        search = Counter()
        for rank, hit in enumerate(hits, 1):  # the best hits count most, so a big slice's many weak hits do not win
            search[hit["address"].partition("/")[0]] += 1 / rank
        scores = {alias: (path[alias], links[alias], search[alias]) for alias in slices}
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)  # stable: ties keep mount order

    def history(self, address: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        """Recorded change events, newest first, for one card or the whole workspace."""
        return self.ws.card_history(address, limit=limit)["events"]

    def staged(self) -> dict[str, Any]:
        """Staged changes awaiting approval: ``items`` (each with a unified ``diff``) and the ``revision``
        a review is checked against."""
        return self.ws.diff("staging")

    def review(self, accept: list[str], reject: list[str], revision: str, dry_run: bool = False) -> dict[str, Any]:
        """Accept and reject staged changes (by staging id) in one batch; the others stay pending.
        ``dry_run`` only reports ``conflicts``. Raises ``ApplyConflictError`` if staging changed since ``revision``."""
        return self.ws.review(accept, reject, revision=revision, dry_run=dry_run)

    def plan_bake(self, assignments: dict[str, str | None]) -> dict[str, Any]:
        """A bake plan for the overlay cards: an alias sends a card to that slice, None keeps it in overlay.
        Writes nothing; a card left out of ``assignments`` gets the engine's own choice."""
        return self.ws.plan_bake(assignments, resume=False)

    def bake(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute a plan from ``plan_bake``. Raises ``BakeConflictError`` if the workspace changed since."""
        return self.ws.bake(plan=plan)


def suggestion(ranked: list[tuple[str, tuple[int, int, float]]]) -> tuple[str | None, str | None]:
    """The best destination of ``Store.destinations`` and the signal that puts it ahead of the next one,
    or ``(None, None)`` when no signal tells it apart."""
    if not ranked:
        return None, None
    best = ranked[0][1]
    runner_up = ranked[1][1] if len(ranked) > 1 else (0, 0, 0)
    signal = next((name for name, a, b in zip(SIGNALS, best, runner_up) if a != b), None)
    return (ranked[0][0], signal) if signal else (None, None)
