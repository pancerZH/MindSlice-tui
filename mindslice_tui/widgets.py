"""The three panes of the main screen: slice tree, card view and relations panel."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Markdown, Static, Tree

from .store import Snapshot


class CardChosen(Message):
    """Ask the app to make ``address`` the focus card. ``jump`` records the previous one for 'back'."""

    def __init__(self, address: str, jump: bool = True) -> None:
        super().__init__()
        self.address = address
        self.jump = jump


def card_label(snapshot: Snapshot, address: str, text: str) -> Text:
    """``text`` with the card's markers: ★ always-loaded, ! problems, ≡ shadowed, struck out when superseded."""
    card = snapshot.cards[address]
    label = Text(text, style="dim strike" if snapshot.is_superseded(address) else "")
    if card.always:
        label.append(" ★", style="yellow")
    if card.problems:
        label.append(" !", style="bold red")
    if address in snapshot.shadowed:
        label.append(" ≡", style="dim")
    return label


class SliceTree(Tree[str]):
    """mount → folders → cards. A card that also has children (``a`` and ``a/b``) is one expandable node."""

    def __init__(self, **kwargs) -> None:
        super().__init__("workspace", **kwargs)
        self.show_root = False
        self.guide_depth = 3
        self.nodes = {}

    def load(self, snapshot: Snapshot) -> None:
        self.clear()
        self.nodes = {}
        for mount in snapshot.mounts:
            cards = [card for card in snapshot.cards.values() if card.mount == mount.alias]
            label = Text.assemble((mount.alias, "bold"), (f" {mount.version}".rstrip() + f"  {len(cards)}", "dim"))
            self.nodes[mount.alias] = self.root.add(label, expand=True)
            for card in sorted(cards, key=lambda card: card.path.split("/")):
                node, prefix = self.nodes[mount.alias], mount.alias
                for part in card.path.split("/"):
                    prefix = f"{prefix}/{part}"  # for the last part this is the card's address
                    if prefix not in self.nodes:
                        node.allow_expand = True
                        self.nodes[prefix] = node.add(Text(part), expand=True, allow_expand=False)
                    node = self.nodes[prefix]
                node.data = card.address
                node.set_label(card_label(snapshot, card.address, card.path.rsplit("/", 1)[-1]))

    def first_card(self) -> str | None:
        return next((node.data for node in self.nodes.values() if node.data), None)

    def reveal(self, address: str) -> None:
        """Move the cursor to a card, opening the folders above it."""
        node = self.nodes.get(address)
        if node is None:
            return
        parent = node.parent
        while parent is not None:
            parent.expand()
            parent = parent.parent
        self.call_after_refresh(self.move_cursor, node)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[str]) -> None:
        if event.node.data:
            self.post_message(CardChosen(event.node.data, jump=False))


class CardView(VerticalScroll):
    """Metadata and rendered body of the focus card."""

    def compose(self):
        yield Static(id="card-meta")
        yield Markdown(open_links=False)

    def show(self, snapshot: Snapshot, address: str, markdown: str) -> None:
        card = snapshot.cards[address]
        meta = Text.assemble((card.title, "bold"), "\n", (address, "cyan"))
        if card.always:
            meta.append("  ★ always loaded", style="yellow")
        if snapshot.is_superseded(address):
            meta.append("  superseded", style="red")
        if address in snapshot.shadowed:
            meta.append("  shadowed", style="red")
        if card.tags:
            meta.append(f"\ntags: {', '.join(card.tags)}")
        if card.aliases:
            meta.append(f"\naliases: {', '.join(card.aliases)}", style="dim")
        modified = datetime.fromtimestamp(card.mtime_ns / 1e9).strftime("%Y-%m-%d %H:%M")
        file = str(card.file).replace(str(Path.home()), "~", 1)
        meta.append(f"\nmodified {modified} · read {card.read_count}×\n{file}", style="dim")
        for problem in card.problems:
            meta.append(f"\n! {problem}", style="red")
        self.query_one("#card-meta", Static).update(meta)
        self.query_one(Markdown).update(markdown)
        self.scroll_home(animate=False)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        if event.href.startswith("@"):
            self.post_message(CardChosen(event.href))
        else:
            self.app.open_url(event.href)


class RelationsPanel(Vertical):
    """The focus card's neighbours grouped by edge kind, with a preview of the highlighted one. Enter jumps."""

    snapshot: Snapshot | None = None

    def compose(self):
        tree = Tree("relations")
        tree.show_root = False
        tree.guide_depth = 3
        yield tree
        yield Static(id="preview")

    def show(self, snapshot: Snapshot, address: str) -> None:
        self.snapshot = snapshot
        tree = self.query_one(Tree)
        tree.clear()

        def group(label: str, count: int):
            return tree.root.add(Text(f"{label} ({count})", style="bold" if count else "dim"),
                                 expand=True, allow_expand=bool(count))

        here = snapshot.cards[address].mount
        for label, targets in snapshot.relations(address):
            node = group(label, len(targets))
            for target in targets:
                # Name first, folder after: the part that tells neighbours apart survives a narrow pane.
                # The mount is named only when it differs from the focus card's.
                folder, _, name = target.removeprefix(f"{here}/").rpartition("/")
                node.add_leaf(card_label(snapshot, target, name).append(f"  {folder}", style="dim"), data=target)
        dangling = snapshot.dangling(address)
        node = group("✗ dangling", len(dangling))
        for edge in dangling:
            node.add_leaf(Text.assemble((edge.raw, "red"), (f"  {edge.kind}", "dim")))
        self.query_one("#preview", Static).update("")

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[str]) -> None:
        card = self.snapshot.cards.get(event.node.data) if self.snapshot else None
        preview = Text.assemble((card.title, "bold"), "\n", (card.summary, "dim")) if card else ""
        self.query_one("#preview", Static).update(preview)

    def on_tree_node_selected(self, event: Tree.NodeSelected[str]) -> None:
        if event.node.data:
            self.post_message(CardChosen(event.node.data))


class Table(Vertical):
    """A row-cursor table. Its last column holds the long text, shown in full under the table for the
    highlighted row. Row keys, when set, are card addresses."""

    def __init__(self, *columns: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.table = DataTable(cursor_type="row", zebra_stripes=True)
        self.table.add_columns(*columns)
        self.detail = Static(classes="detail")

    def compose(self):
        yield self.table
        yield self.detail

    def fill(self, rows: list[tuple], addresses: list[str | None] | None = None) -> None:
        self.table.clear()
        for i, row in enumerate(rows):
            self.table.add_row(*(Text("" if cell is None else str(cell)) for cell in row),
                               key=f"{i}\t{addresses[i] or ''}" if addresses else None)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.detail.update(self.table.get_row(event.row_key)[-1])

    @staticmethod
    def address_of(event: DataTable.RowSelected) -> str | None:
        return (event.row_key.value or "").partition("\t")[2] or None


def history_rows(events: list[dict]) -> list[tuple]:
    """Change events as (local time, change, address, reason) rows."""
    def local(stamp: str) -> str:
        return datetime.fromisoformat(stamp).astimezone().strftime("%Y-%m-%d %H:%M:%S") if stamp else ""

    return [(local(e.get("timestamp", "")), f"{e.get('event', '')} {e.get('op', '')}".strip(),
             e.get("address"), e.get("reason")) for e in events]
