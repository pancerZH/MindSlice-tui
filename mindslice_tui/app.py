"""The MindSlice TUI application: three panes driven by one focus card."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer

from mindslice import MindSliceError

from . import i18n
from .i18n import t
from .screens import HistoryScreen, NeighborsScreen, OverviewScreen, SearchScreen
from .store import Store
from .widgets import CardChosen, CardView, RelationsPanel, SliceTree


class MindSliceApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "MindSlice"
    # (key, action, key shown in the footer). The label is t(action), set in relabel().
    KEYS = (("slash", "search", "/"), ("g", "neighbors", None), ("o", "overview", None), ("h", "history", None),
            ("r", "refresh", None), ("backspace", "back", None), ("l", "language", None), ("q", "quit", None))

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
        self.relabel()
        tree = self.query_one(SliceTree)
        tree.load(self.snapshot)
        tree.focus()
        self.show(tree.first_card(), remember=False)

    def relabel(self) -> None:
        """Put the current language on the key hints and pane titles."""
        for key, action, display in self.KEYS:
            # Textual cannot relabel a binding, so swap it where the footer reads bindings from.
            self._bindings.key_to_bindings[key] = [Binding(key, action, t(action), key_display=display)]
        self.refresh_bindings()
        for pane in ("slices", "card", "relations"):
            self.query_one(f"#{pane}").border_title = t(pane)

    def action_language(self) -> None:
        i18n.switch()
        self.relabel()
        address, self.address = self.address, None  # draw the focus card again, in the new language
        self.show(address, jump=False)

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
            self.notify(str(error), title=t("refresh_failed"), severity="error", markup=False)
            return
        tree = self.query_one(SliceTree)
        tree.load(self.snapshot)
        # The focus card may be gone (deleted or renamed outside); fall back to the first one.
        address = self.address if self.address in self.snapshot.cards else tree.first_card()
        self.address = None
        self.show(address, remember=False)
        self.notify(t("card_count", count=len(self.snapshot.cards)), title=t("refreshed"))

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
