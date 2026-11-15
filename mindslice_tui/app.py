"""The MindSlice TUI application: three panes driven by one focus card."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer

from mindslice import MindSliceError

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
        self.show(tree.first_card(), remember=False)

    def show(self, address: str | None, jump: bool = True, remember: bool = True) -> None:
        """Make ``address`` the focus card. A jump moves the tree cursor and, unless told otherwise,
        remembers the previous focus card for 'back'."""
        if address not in self.snapshot.cards or address == self.address:
            return
        if jump:
            if remember and self.address:
                self.trail.append(self.address)
            self.query_one(SliceTree).reveal(address)
        self.address = address
        self.query_one(CardView).show(self.snapshot, address, self.store.markdown(self.snapshot, address))
        self.query_one(RelationsPanel).show(self.snapshot, address)

    def on_card_chosen(self, event: CardChosen) -> None:
        self.show(event.address, event.jump)

    def open(self, address: str | None) -> None:
        """Jump to a card picked in a modal. Search sees the live workspace, so the card may be newer
        than the snapshot: reload first in that case."""
        if address and address not in self.snapshot.cards:
            self.action_refresh()
        self.show(address)

    def action_back(self) -> None:
        while self.trail:
            address = self.trail.pop()
            if address in self.snapshot.cards and address != self.address:
                self.show(address, remember=False)
                return

    def action_refresh(self) -> None:
        try:
            self.snapshot = self.store.load()
        except MindSliceError as error:
            self.notify(str(error), title="刷新失败，仍显示旧内容", severity="error", markup=False)
            return
        tree = self.query_one(SliceTree)
        tree.load(self.snapshot)
        # The focus card may be gone (deleted or renamed outside); fall back to the first one.
        address = self.address if self.address in self.snapshot.cards else tree.first_card()
        self.address = None
        self.show(address, remember=False)
        self.notify(f"{len(self.snapshot.cards)} cards", title="已刷新")

    def action_search(self) -> None:
        self.push_screen(SearchScreen(self.store), self.open)

    def action_overview(self) -> None:
        self.push_screen(OverviewScreen(self.store, self.snapshot), self.open)

    def action_neighbors(self) -> None:
        if self.address:
            self.push_screen(NeighborsScreen(self.snapshot, self.address), self.open)

    def action_history(self) -> None:
        if self.address:
            self.push_screen(HistoryScreen(self.store, self.address), self.open)
