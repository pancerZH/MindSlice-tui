"""Modal screens. Each dismisses with a card address to jump to, or None."""

from __future__ import annotations

from rich.markup import escape
from rich.text import Text
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, OptionList, Static, TabbedContent, TabPane, Tree
from textual.widgets.option_list import Option

from .store import EDGE_GROUPS, Snapshot, Store
from .widgets import Table, card_label, history_rows

HISTORY_COLUMNS = ("time (UTC)", "event", "op", "card", "reason")


class Modal(ModalScreen[str | None]):
    BINDINGS = [("escape", "dismiss(None)", "关闭")]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        address = Table.address_of(event)
        if address:
            self.dismiss(address)


class SearchScreen(Modal):
    """Full-text search through the engine (BM25); results follow supersedes like agent searches do."""

    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store

    def compose(self):
        with Vertical(classes="dialog") as dialog:
            dialog.border_title = "搜索"
            yield Input(placeholder="输入关键词，回车进入结果列表")
            yield OptionList()
            yield Static(id="search-note")

    def on_input_changed(self, event: Input.Changed) -> None:
        results = self.query_one(OptionList)
        results.clear_options()
        note = ""
        if event.value.strip():
            found = self.store.search(event.value)
            for hit in found["results"]:
                text = Text.assemble((hit["title"], "bold"), "  ", (hit["address"], "cyan"),
                                     (f"  {hit['coverage']:.0%}\n", "dim"), (hit["summary"], "dim"))
                results.add_option(Option(text, id=hit["address"]))
            note = f"{found['total_matches']} 条结果"
            if found["unmatched_terms"]:
                note += f" · 未匹配的词: {', '.join(found['unmatched_terms'])}"
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
        tree.border_title = "邻居树"
        tree.border_subtitle = "space 展开 · enter 跳转 · esc 关闭"
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
        for label, kind, direction in EDGE_GROUPS:
            for neighbor in self.snapshot.neighbors(node.data, kind, direction):
                text = card_label(self.snapshot, neighbor, self.snapshot.cards[neighbor].title)
                text = Text.assemble((f"{label}  ", "dim"), text)
                if neighbor in path:
                    node.add_leaf(text.append("  ↺", style="dim"), data=neighbor)
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
        table = Table(*HISTORY_COLUMNS, classes="dialog")
        table.border_title = escape(f"历史 · {self.address}")
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
            tabs.border_title = escape(f"概览 · {snapshot.root}")
            with TabPane("状态", id="status"):
                yield VerticalScroll(Static(self.status_text()))
            with TabPane("问题", id="issues"):
                issues = snapshot.issues()
                table = Table("kind", "card", "detail")
                table.fill(issues, [address if address in snapshot.cards else None for _, address, _ in issues])
                yield table
            with TabPane("历史", id="history"):
                events = self.store.history()
                table = Table(*HISTORY_COLUMNS)
                table.fill(history_rows(events), [e.get("address") if e.get("address") in snapshot.cards else None
                                                  for e in events])
                yield table
            with TabPane("常驻", id="always"):
                always = [card for card in snapshot.cards.values() if card.always]
                table = Table("card", "title", "summary")
                table.fill([(c.address, c.title, c.summary) for c in always], [c.address for c in always])
                yield table

    def status_text(self) -> Text:
        status = self.snapshot.status
        text = Text()
        text.append("Mounts\n", style="bold")
        for mount in status["mounts"]:
            flags = "".join(f"  {name}" for name in ("missing", "dirty") if mount[name])
            text.append(f"  {mount['alias']:<16} {mount['card_count']:>5} cards  precedence {mount['precedence']:<4}"
                        f" {mount['role']:<10} {mount['path']}")
            text.append(f"{flags}\n", style="red")
        state = status["memory_state"]
        text.append("\nMemory\n", style="bold")
        text.append(f"  overlay cards {state['saved_overlay_cards']} · mounted cards {state['mounted_cards']}"
                    f" · not assigned to a slice {state['unassigned_cards']}\n")
        stats = self.snapshot.validation["stats"]
        text.append(f"  validation: {stats['errors']} errors, {stats['warnings']} warnings\n")
        pending = self.store.pending()
        text.append(f"\nPending review ({len(pending)})\n", style="bold")
        for item in pending:
            text.append(f"  {item['change']} {item['address']}", style="yellow")
            text.append(f"  conflict: {item['conflict']}\n" if item["conflict"] else "\n", style="red")
            for change in item.get("changes", []):
                text.append(f"    reason: {change.get('reason', '')}\n", style="dim")
            for line in item["diff"].splitlines():
                style = "green" if line.startswith("+") else "red" if line.startswith("-") else "dim"
                text.append(f"    {line}\n", style=style)
        if not pending:
            text.append("  nothing is waiting for approval\n", style="dim")
        return text
