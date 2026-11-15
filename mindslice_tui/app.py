"""The MindSlice TUI application: three panes driven by one focus card."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer

from .screens import HistoryScreen, NeighborsScreen, OverviewScreen, SearchScreen
from .store import Store
from .widgets import CardChosen, CardView, RelationsPanel, SliceTree


class MindSliceApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "MindSlice"
    BINDINGS = [
        Binding("slash", "search", "搜索", key_display="/"),
        Binding("g", "neighbors", "邻居树"),
        Binding("o", "overview", "概览"),
        Binding("h", "history", "历史"),
        Binding("r", "refresh", "刷新"),
        Binding("backspace", "back", "回退"),
        Binding("q", "quit", "退出"),
    ]

    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store
        self.snapshot = store.load()
        self.address: str | None = None  # the focus card
        self.trail: list[str] = []  # earlier focus cards, for 'back'

    def compose(self):
        with Horizontal():
            yield SliceTree(id="slices")
            yield CardView(id="card")
            yield RelationsPanel(id="relations")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#slices").border_title = "Slices"
        self.query_one("#card").border_title = "Card"
        self.query_one("#relations").border_title = "Relations"
        tree = self.query_one(SliceTree)
        tree.load(self.snapshot)
        tree.focus()
        self.show(next((node.data for node in tree.nodes.values() if node.data), None))

    def show(self, address: str | None, jump: bool = True) -> None:
        """Make ``address`` the focus card; a jump remembers the previous one and moves the tree cursor."""
        if address not in self.snapshot.cards or address == self.address:
            return
        if jump:
            if self.address:
                self.trail.append(self.address)
            self.query_one(SliceTree).reveal(address)
        self.address = address
        self.query_one(CardView).show(self.snapshot, address, self.store.markdown(self.snapshot, address))
        self.query_one(RelationsPanel).show(self.snapshot, address)

    def on_card_chosen(self, event: CardChosen) -> None:
        self.show(event.address, event.jump)

    def action_back(self) -> None:
        while self.trail:
            address = self.trail.pop()
            if address in self.snapshot.cards and address != self.address:
                self.show(address)
                self.trail.pop()  # going back is not a step forward
                return

    def action_refresh(self) -> None:
        self.snapshot = self.store.load()
        self.query_one(SliceTree).load(self.snapshot)
        address, self.address = self.address, None
        self.show(address)
        self.notify(f"{len(self.snapshot.cards)} cards", title="已刷新")

    def action_search(self) -> None:
        self.push_screen(SearchScreen(self.store), self.show)

    def action_overview(self) -> None:
        self.push_screen(OverviewScreen(self.store, self.snapshot), self.show)

    def action_neighbors(self) -> None:
        if self.address:
            self.push_screen(NeighborsScreen(self.snapshot, self.address), self.show)

    def action_history(self) -> None:
        if self.address:
            self.push_screen(HistoryScreen(self.store, self.address), self.show)
