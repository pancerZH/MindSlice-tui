"""The three panes of the main screen: slice tree, card view and relations panel."""

from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.containers import VerticalScroll
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
    """``text`` with the card's markers: ★ always-loaded, ⚠ problems, ≡ shadowed, dim when superseded."""
    card = snapshot.cards[address]
    label = Text(text, style="dim strike" if snapshot.is_superseded(address) else "")
    if card.always:
        label.append(" ★", style="yellow")
    if card.problems:
        label.append(" ⚠", style="red")
    if snapshot.is_shadowed(address):
        label.append(" ≡", style="dim")
    return label


class SliceTree(Tree[str]):
    """mount → folders → cards. A card that also has children (``a`` and ``a/b``) is one expandable node."""

    def __init__(self, **kwargs) -> None:
        super().__init__("workspace", **kwargs)
        self.show_root = False
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
        if snapshot.is_shadowed(address):
            meta.append("  shadowed", style="red")
        if card.tags:
            meta.append(f"\ntags: {', '.join(card.tags)}")
        if card.aliases:
            meta.append(f"\naliases: {', '.join(card.aliases)}", style="dim")
        modified = datetime.fromtimestamp(card.mtime_ns / 1e9).strftime("%Y-%m-%d %H:%M")
        meta.append(f"\nmodified {modified} · read {card.read_count}× · {card.file}", style="dim")
        for problem in card.problems:
            meta.append(f"\n⚠ {problem}", style="red")
        self.query_one("#card-meta", Static).update(meta)
        self.query_one(Markdown).update(markdown)
        self.scroll_home(animate=False)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        if event.href.startswith("@"):
            self.post_message(CardChosen(event.href))
        else:
            self.app.open_url(event.href)


class RelationsPanel(Tree[str]):
    """The focus card's neighbours, grouped by edge kind. Enter jumps to one."""

    def __init__(self, **kwargs) -> None:
        super().__init__("relations", **kwargs)
        self.show_root = False

    def show(self, snapshot: Snapshot, address: str) -> None:
        self.clear()
        for label, items in snapshot.relations(address):
            group = self.root.add(Text(f"{label} ({len(items)})", style="bold" if items else "dim"),
                                  expand=True, allow_expand=bool(items))
            for target, text in items:
                group.add_leaf(card_label(snapshot, target, text) if target else Text(text, style="red"), data=target)

    def on_tree_node_selected(self, event: Tree.NodeSelected[str]) -> None:
        if event.node.data:
            self.post_message(CardChosen(event.node.data))


class Table(DataTable):
    """A row-cursor table whose row keys, when set, are card addresses."""

    def __init__(self, *columns: str, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, **kwargs)
        self.add_columns(*columns)

    def fill(self, rows: list[tuple], addresses: list[str | None] | None = None) -> None:
        self.clear()
        for i, row in enumerate(rows):
            self.add_row(*(Text(str(cell)) for cell in row), key=f"{i}\t{addresses[i] or ''}" if addresses else None)

    @staticmethod
    def address_of(event: DataTable.RowSelected) -> str | None:
        return (event.row_key.value or "").partition("\t")[2] or None


def history_rows(events: list[dict]) -> list[tuple]:
    """Change events as (time, event, op, address, reason) rows."""
    return [(e.get("timestamp", "")[:19].replace("T", " "), e.get("event", ""), e.get("op", ""),
             e.get("address", ""), e.get("reason", "")) for e in events]
