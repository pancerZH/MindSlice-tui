"""Modal screens. Each dismisses with a card address to jump to, or None."""

from __future__ import annotations

from rich.cells import cell_len
from rich.markup import escape
from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, OptionList, Static, TabbedContent, TabPane, Tree
from textual.widgets.option_list import Option

from .i18n import t
from .store import EDGE_GROUPS, Snapshot, Store
from .widgets import Table, card_label, history_rows


def history_columns() -> list[str]:
    return [t(f"col_{name}") for name in ("time", "change", "card", "reason")]


class Modal(ModalScreen[str | None]):
    BINDINGS = [("escape", "dismiss(None)", "Close")]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        address = Table.address_of(event)
        if address:
            self.dismiss(address)


class SearchScreen(Modal):
    """Full-text search through the engine (BM25); results follow supersedes like agent searches do."""

    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store
        self.timer = None

    def compose(self):
        with Vertical(classes="dialog") as dialog:
            dialog.border_title = t("search")
            yield Input(placeholder=t("search_placeholder"))
            yield OptionList()
            yield Static(id="search-note")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Search once typing pauses, not on every keystroke."""
        if self.timer:
            self.timer.stop()
        self.timer = self.set_timer(0.15, lambda: self.search(event.value))

    def search(self, query: str) -> None:
        results = self.query_one(OptionList)
        results.clear_options()
        note = ""
        if query.strip():
            found = self.store.search(query)
            for hit in found["results"]:
                text = Text.assemble((hit["title"], "bold"), "  ", (hit["address"], "cyan"),
                                     (f"  {hit['coverage']:.0%}\n", "dim"), (hit["summary"], "dim"))
                results.add_options([Option(text, id=hit["address"]), None])  # None draws a separator
            note = t("search_found", count=found["total_matches"])
            if found["unmatched_terms"]:
                note += " · " + t("search_unmatched", terms=", ".join(found["unmatched_terms"]))
        self.query_one("#search-note", Static).update(note)

    def on_input_submitted(self) -> None:
        results = self.query_one(OptionList)
        if results.option_count:
            results.focus()
            results.highlighted = 0

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class NeighborsScreen(Modal):
    """Multi-hop exploration: a tree rooted at the focus card, each node opening into its neighbours."""

    def __init__(self, snapshot: Snapshot, address: str) -> None:
        super().__init__()
        self.snapshot = snapshot
        self.address = address

    def compose(self):
        tree = Tree(card_label(self.snapshot, self.address, self.snapshot.cards[self.address].title),
                    data=self.address, classes="dialog")
        tree.auto_expand = False  # enter jumps; space opens a node
        tree.border_title = t("neighbors")
        tree.border_subtitle = t("neighbor_hint")
        yield tree

    def on_mount(self) -> None:
        self.query_one(Tree).root.expand()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[str]) -> None:
        node = event.node
        if node.children:
            return
        path = set()  # addresses from the root down to this node
        walker = node
        while walker is not None:
            path.add(walker.data)
            walker = walker.parent
        width = max(cell_len(t(name)) for name, _, _ in EDGE_GROUPS)  # cells, not characters: CJK is double width
        for name, kind, direction in EDGE_GROUPS:
            label = t(name) + " " * (width - cell_len(t(name)) + 2)
            for neighbor in self.snapshot.neighbors(node.data, kind, direction):
                text = card_label(self.snapshot, neighbor, self.snapshot.cards[neighbor].title)
                text = Text.assemble((label, "dim"), text)
                if neighbor in path:  # a leaf has no toggle arrow: pad so the columns still line up
                    node.add_leaf(Text.assemble("  ", text, ("  ↺", "dim")), data=neighbor)
                else:
                    node.add(text, data=neighbor)
        if not node.children:
            node.allow_expand = False

    def on_tree_node_selected(self, event: Tree.NodeSelected[str]) -> None:
        self.dismiss(event.node.data)


class HistoryScreen(Modal):
    """Recorded changes of one card, newest first."""

    def __init__(self, store: Store, address: str) -> None:
        super().__init__()
        self.events = store.history(address)
        self.address = address

    def compose(self):
        table = Table(*history_columns(), classes="dialog")
        table.border_title = escape(f"{t('history')} · {self.address}")
        table.fill(history_rows(self.events))
        yield table


class OverviewScreen(Modal):
    """Workspace-wide read-only views: status, issues, history, always-loaded cards."""

    def __init__(self, store: Store, snapshot: Snapshot) -> None:
        super().__init__()
        self.store = store
        self.snapshot = snapshot

    def compose(self):
        snapshot = self.snapshot
        with TabbedContent(classes="dialog") as tabs:
            tabs.border_title = escape(f"{t('overview')} · {snapshot.root}")
            with TabPane(t("tab_status"), id="status"):
                yield VerticalScroll(Static(self.status_text()))
            with TabPane(t("tab_issues"), id="issues"):
                issues = snapshot.issues()
                table = Table(t("col_kind"), t("col_card"), t("col_detail"))
                table.fill([self.issue_row(*issue) for issue in issues],
                           [address if address in snapshot.cards else None for _, address, _ in issues])
                yield table
            with TabPane(t("history"), id="history"):
                events = self.store.history()
                table = Table(*history_columns())
                table.fill(history_rows(events), [e.get("address") if e.get("address") in snapshot.cards else None
                                                  for e in events])
                yield table
            with TabPane(t("tab_always"), id="always"):
                always = [card for card in snapshot.cards.values() if card.always]
                table = Table(t("col_card"), t("col_title"), t("col_summary"))
                table.fill([(c.address, c.title, c.summary) for c in always], [c.address for c in always])
                yield table

    @staticmethod
    def issue_row(kind: str, address: str | None, detail: str) -> tuple:
        """Word one of ``Snapshot.issues()``: the engine's messages pass through, ours are translated."""
        if kind not in ("error", "warning"):
            detail = t(f"issue_{kind}_detail", target=detail)
        return t(f"issue_{kind}"), address, detail

    def status_text(self) -> Text:
        status = self.snapshot.status
        text = Text()
        text.append(f"{t('mounts')}\n", style="bold")
        for mount in status["mounts"]:
            text.append("  " + t("mount_row", alias=mount["alias"], count=mount["card_count"],
                                 precedence=mount["precedence"], role=mount["role"], path=mount["path"]))
            flags = "".join(f"  {t(f'mount_{name}')}" for name in ("missing", "dirty") if mount[name])
            text.append(f"{flags}\n", style="red")
        state = status["memory_state"]
        text.append(f"\n{t('memory')}\n", style="bold")
        text.append("  " + t("memory_row", overlay=state["saved_overlay_cards"], mounted=state["mounted_cards"],
                             unassigned=state["unassigned_cards"]) + "\n")
        text.append("  " + t("validation_row", **self.snapshot.validation["stats"]) + "\n")
        pending = self.store.pending()
        text.append(f"\n{t('pending', count=len(pending))}\n", style="bold")
        for item in pending:
            text.append(f"  {item['change']} {item['address']}", style="yellow")
            text.append(f"  {t('pending_conflict', conflict=item['conflict'])}\n" if item["conflict"] else "\n", style="red")
            for change in item.get("changes", []):
                text.append(f"    {t('pending_reason', reason=change.get('reason', ''))}\n", style="dim")
            for line in item["diff"].splitlines():
                style = "green" if line.startswith("+") else "red" if line.startswith("-") else "dim"
                text.append(f"    {line}\n", style=style)
        if not pending:
            text.append(f"  {t('pending_none')}\n", style="dim")
        return text
