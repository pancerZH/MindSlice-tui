"""The screens that change memory: review of staged changes, and bake of overlay cards into slices.

Both are checklists: one row per change, ticked by hand, and nothing is written until the user
presses the screen's key (``a`` or ``b``) and confirms with enter. Every engine call goes through ``Store``.
"""

from __future__ import annotations

from rich.markup import escape
from rich.text import Text
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, OptionList, Static
from textual.widgets.option_list import Option

from mindslice import MindSliceError

from .i18n import t
from .store import SIGNALS, Snapshot, Store, suggestion
from .widgets import diff_text, home_short

MARKS = {"accept": Text("[✓]", style="bold green"), "reject": Text("[✗]", style="bold red"), None: Text("[ ]", style="dim")}
REFERENCES = {"extends": "extends", "supersedes": "supersedes", "wikilinks": "links_out"}  # engine key -> label


class ConfirmScreen(ModalScreen[bool]):
    """A yes/no question before memory changes: enter confirms, esc cancels, as everywhere else."""

    BINDINGS = [("enter", "dismiss(True)", "Confirm"), ("escape", "dismiss(False)", "Cancel")]

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self):
        box = Static(Text.assemble(self.question, "\n\n", (t("confirm_hint"), "dim")), classes="prompt")
        box.border_title = t("confirm")
        yield box


class DestinationScreen(ModalScreen[str | None]):
    """Pick the slice a card is baked into: the slices best first, each with what speaks for it
    (``scores`` for ``SIGNALS``, or None for a new slice already chosen for another card), or type a new alias."""

    BINDINGS = [("escape", "dismiss(None)", "Close")]

    def __init__(self, card_id: str, choices: list[tuple[str, tuple[int, int, float] | None]], current: str | None) -> None:
        super().__init__()
        self.card_id = card_id
        self.choices = choices
        self.current = current

    def compose(self):
        with Vertical(classes="prompt") as box:
            box.border_title = escape(t("destination_title", card=self.card_id))
            box.border_subtitle = t("destination_hint")
            yield OptionList(*(Option(self.label(alias, scores), id=alias) for alias, scores in self.choices))
            yield Input(placeholder=t("destination_placeholder"))

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        aliases = [alias for alias, _ in self.choices]
        options.highlighted = aliases.index(self.current) if self.current in aliases else 0
        options.focus()

    @staticmethod
    def label(alias: str, scores: tuple[int, int, float] | None) -> Text:
        evidence = [t(f"evidence_{name}", count=n) for name, n in zip(SIGNALS, scores) if n] if scores else [t("bake_create")]
        return Text.assemble((alias, "bold"), ("  " + " · ".join(evidence), "dim"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)


class Checklist(ModalScreen[None]):
    """One row per change on the left, the highlighted one in full on the right, the outcome below.
    Subclasses provide ``heading()``, ``rows()`` (``(key, cells)`` pairs), ``detail(key)`` and ``outcome()``."""

    BINDINGS = [("escape", "dismiss", "Close")]
    COLUMNS: tuple[str, ...] = ()  # i18n keys of the column headers
    HINT = ""  # i18n key of the key hints

    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store

    def compose(self):
        with Vertical(classes="dialog") as dialog:
            dialog.border_subtitle = t(self.HINT)
            with Horizontal(classes="checklist"):
                yield DataTable(cursor_type="row", zebra_stripes=True)
                yield VerticalScroll(Static(id="change"))
            yield Static(id="outcome")

    def on_mount(self) -> None:
        self.query_one(DataTable).add_columns(*(t(column) for column in self.COLUMNS))
        self.redraw()

    def redraw(self) -> None:
        """Fill the rows again, keeping the cursor where it was."""
        table = self.query_one(DataTable)
        row = table.cursor_row
        table.clear()
        for key, cells in self.rows():
            table.add_row(*cells, key=key)
        if table.row_count:
            table.move_cursor(row=min(row, table.row_count - 1))
        self.query_one(".dialog").border_title = escape(self.heading())
        key = self.current()
        self.query_one("#change", Static).update(self.detail(key) if key else "")
        self.query_one("#outcome", Static).update(self.outcome())

    def current(self) -> str | None:
        table = self.query_one(DataTable)
        return table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value if table.row_count else None

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.query_one("#change", Static).update(self.detail(event.row_key.value))

    def failed(self, error: MindSliceError, stale: bool) -> None:
        self.notify(t("stale") if stale else str(error), title=t("failed"), severity="error", markup=False)

    def done(self, message: str) -> None:
        """Memory changed: report it, show the new state in the main screen and close."""
        self.app.notify(message, title=t("done"), markup=False)
        self.app.reload()
        self.dismiss()


class ReviewScreen(Checklist):
    """Staged changes: accept (✓), reject (✗) or leave each one pending, then execute the choices as one batch."""

    BINDINGS = [("space", "mark('accept')", "Accept"), ("x", "mark('reject')", "Reject"), ("a", "apply", "Apply")]
    COLUMNS = ("col_mark", "col_change", "col_card")
    HINT = "review_hint"

    def __init__(self, store: Store) -> None:
        super().__init__(store)
        self.items: dict[str, dict] = {}
        self.marks: dict[str, str] = {}  # staging id -> "accept" | "reject"; an unmarked change stays pending
        self.blocked: list[dict] = []  # conflicts found by the last check
        self.load()

    def load(self) -> None:
        staged = self.store.staged()
        old, self.items = self.items, {item["id"]: item for item in staged["items"]}
        self.revision = staged["revision"]
        # A mark survives a reload only for a change that is still exactly as it was.
        self.marks = {key: mark for key, mark in self.marks.items() if self.items.get(key) == old.get(key)}

    def chosen(self, mark: str) -> list[str]:
        return [key for key, value in self.marks.items() if value == mark]

    def heading(self) -> str:
        return t("review_title", count=len(self.items))

    def rows(self):
        for key, item in self.items.items():
            change = Text(item["change"] + (" !" if item["conflict"] else ""), style="red" if item["conflict"] else "")
            yield key, (MARKS[self.marks.get(key)], change, Text(item["address"]))

    def detail(self, key: str) -> Text:
        item = self.items[key]
        text = Text.assemble((item["address"], "bold cyan"), f"  {item['change']}\n")
        for change in item.get("changes", []):
            text.append(t("pending_reason", reason=change.get("reason") or "") + "\n", style="dim")
        if item.get("requires_approval"):
            text.append(t("review_approval", why=item["requires_approval"]) + "\n", style="yellow")
        if item["conflict"]:
            text.append(t("pending_conflict", conflict=item["conflict"]) + "\n", style="red")
        for kind, refs in item.get("references", {}).items():
            if refs:
                text.append(f"{t(REFERENCES.get(kind, kind))}: {', '.join(refs)}\n", style="dim")
        impact = item.get("impact", {})
        for field in ("affected_backlinks", "affected_extensions"):
            if impact.get(field):
                cards = ", ".join(card["address"] for card in impact[field])
                text.append(t(f"review_{field}", count=impact[f"total_{field}"], cards=cards) + "\n", style="yellow")
        return text.append("\n").append(diff_text(item["diff"]))

    def outcome(self) -> Text:
        if not self.items:
            return Text(t("pending_none"), style="dim")
        accept, reject = len(self.chosen("accept")), len(self.chosen("reject"))
        text = Text(t("review_summary", accept=accept, reject=reject, leave=len(self.items) - accept - reject))
        for conflict in self.blocked:
            text.append("\n" + t("blocked", where=conflict.get("address", ""),
                                 detail=conflict.get("detail") or conflict["reason"]), style="red")
        return text

    def action_mark(self, mark: str) -> None:
        key = self.current()
        if key is None:
            return
        if mark == "accept" and self.items[key]["conflict"]:
            self.notify(t("review_conflict_refused"), severity="warning")
            return
        if self.marks.get(key) == mark:
            del self.marks[key]
        else:
            self.marks[key] = mark
        self.blocked = []
        self.redraw()

    def action_apply(self) -> None:
        """Check the choices with a dry run, then ask before executing them."""
        accept, reject = self.chosen("accept"), self.chosen("reject")
        if not accept and not reject:
            self.notify(t("review_nothing"), severity="warning")
            return
        try:
            self.blocked = self.store.review(accept, reject, self.revision, dry_run=True)["conflicts"]
        except MindSliceError as error:
            return self.refused(error)
        self.redraw()
        if not self.blocked:
            question = t("review_confirm", accept=len(accept), reject=len(reject),
                         leave=len(self.items) - len(accept) - len(reject))
            self.app.push_screen(ConfirmScreen(question), self.execute)

    def execute(self, confirmed: bool) -> None:
        if not confirmed:
            return
        try:
            result = self.store.review(self.chosen("accept"), self.chosen("reject"), self.revision)
        except MindSliceError as error:
            return self.refused(error)
        for skipped in result["skipped"]:
            self.app.notify(t("skipped", address=skipped["address"], reason=skipped["reason"]),
                            severity="warning", markup=False)
        self.done(t("review_done", applied=result["applied"], discarded=result.get("discarded", 0)))

    def refused(self, error: MindSliceError) -> None:
        """The engine refused, most likely because staging changed meanwhile: reload the list."""
        self.failed(error, stale=any(c.get("reason") == "stale_review" for c in error.details.get("conflicts", [])))
        try:
            self.load()
        except MindSliceError:
            pass
        self.redraw()


class BakeScreen(Checklist):
    """Overlay cards: tick the ones to bake, each with its destination slice. The plan below follows every
    tick; unticked cards stay in overlay (they are live memory already)."""

    BINDINGS = [("space", "tick", "Choose"), ("d", "destination", "Destination"), ("b", "bake", "Bake")]
    COLUMNS = ("col_mark", "col_card", "col_destination", "col_kind")
    HINT = "bake_hint"

    def __init__(self, store: Store, snapshot: Snapshot) -> None:
        super().__init__(store)
        self.snapshot = snapshot  # what the destinations are ranked against
        self.ticked: set[str] = set()
        self.dest: dict[str, str | None] = {}  # every overlay card's destination, ticked or not
        self.suggested: dict[str, tuple[str | None, str | None]] = {}  # card -> (destination, why) offered at first
        self.replan()

    def suggest(self, card: dict) -> tuple[str | None, str | None]:
        """The slice the engine relates the card to (same path, extends or supersedes), else the best one
        of ``Store.destinations``; with the reason, or ``(None, None)`` when nothing tells slices apart."""
        related = card["destination"] or next(iter(card["candidates"]), None)
        return (related, "related") if related else suggestion(self.store.destinations(self.snapshot, card))

    def replan(self) -> None:
        """Plan with every unticked card kept in overlay. A card the plan shows for the first time gets a
        suggested destination (``suggest``), and is planned again unticked."""
        while True:
            plan = self.store.plan_bake({key: dest if key in self.ticked else None for key, dest in self.dest.items()})
            new = {card["id"]: self.suggest(card) for card in plan["cards"] if card["id"] not in self.dest}
            if not new:
                break
            self.suggested.update(new)
            self.dest.update({key: dest for key, (dest, _) in new.items()})
        self.plan = plan
        self.cards = {card["id"]: card for card in plan["cards"]}
        for key in self.ticked:
            self.dest[key] = self.cards[key]["destination"]  # as the engine spells it: "notes" -> "@notes"

    def choose(self, key: str, ticked: bool, dest: str | None) -> None:
        """Tick or untick one card with a destination and plan again; undone if the engine refuses it."""
        before = set(self.ticked), dict(self.dest)
        self.dest[key] = dest
        if ticked:
            self.ticked.add(key)
        else:
            self.ticked.discard(key)
        try:
            self.replan()
        except MindSliceError as error:
            self.ticked, self.dest = before
            self.failed(error, stale=False)
        self.redraw()

    def heading(self) -> str:
        return t("bake_title", count=len(self.cards))

    def rows(self):
        for key, card in self.cards.items():
            ticked = key in self.ticked
            dest = Text(self.dest.get(key) or "?", style="bold" if ticked else "")
            suggested, why = self.suggested.get(key, (None, None))
            if why and dest.plain == suggested:  # say why, as long as it is still the suggested slice
                dest.append(f"  {t(f'why_{why}')}", style="dim")
            yield key, (MARKS["accept" if ticked else None], Text(key), dest, Text(card.get("kind", ""), style="dim"))

    def detail(self, key: str) -> Text:
        card = self.cards[key]
        text = Text.assemble((card.get("title") or key, "bold"), "\n", (card["address"], "cyan"), "\n",
                             (card["summary"], "dim"), "\n")
        if card["candidates"]:
            text.append(t("bake_related", slices=", ".join(card["candidates"])) + "\n")
        for change in card.get("changes", []):
            text.append(t("pending_reason", reason=change.get("reason") or "") + "\n", style="dim")
        return text.append("\n").append(diff_text(card.get("diff", "")))

    def outcome(self) -> Text:
        if not self.cards:
            return Text(t("bake_empty"), style="dim")
        lines = [(t("bake_slice", alias=s["alias"], action=t(f"bake_{s['action']}"), version=s["version"],
                    count=len(s["cards"]), path=home_short(s["path"])), "green") for s in self.plan["slices"]]
        if not lines:
            lines.append((t("bake_none_chosen"), "dim"))
        lines += [(t("bake_retained", address=r["address"], reason=r["reason"]), "yellow")
                  for r in self.plan["retained_overlay_cards"]]
        seen = set()
        for blocker in self.plan["blockers"]:
            where = blocker.get("address") or blocker.get("alias") or ", ".join(blocker.get("cards", []))
            # One broken reference is reported twice (input and output), and a derived blocker goes away
            # with the one it follows from: show each problem once, as the CLI does.
            key = (where, blocker.get("ref") or blocker["reason"])
            if blocker.get("derived") or key in seen:
                continue
            seen.add(key)
            detail = blocker["reason"] + (f" ({blocker['ref']})" if blocker.get("ref") else "")
            lines.append((t("blocked", where=where, detail=detail), "red"))
        return Text("\n").join(Text(line, style=style) for line, style in lines)

    def action_tick(self) -> None:
        key = self.current()
        if key is None:
            return
        if key in self.ticked:
            self.choose(key, False, self.dest[key])
        elif self.dest.get(key):
            self.choose(key, True, self.dest[key])
        else:
            self.action_destination()  # no destination yet: ask for one first

    def action_destination(self) -> None:
        """Ask for the card's destination; choosing one ticks the card."""
        key = self.current()
        if key is None:
            return

        def chosen(dest: str | None) -> None:
            if dest:
                self.choose(key, True, dest)

        ranked = self.store.destinations(self.snapshot, self.cards[key])
        # New slices chosen for other cards in this screen are not mounted yet: offer them too.
        new = sorted({dest for dest in self.dest.values() if dest} - {alias for alias, _ in ranked})
        choices = [*ranked, *((alias, None) for alias in new)]
        self.app.push_screen(DestinationScreen(key, choices, self.dest.get(key)), chosen)

    def action_bake(self) -> None:
        if not self.ticked:
            self.notify(t("bake_nothing"), severity="warning")
        elif not self.plan["ready"]:
            self.notify(t("bake_not_ready"), severity="warning")
        else:
            slices = ", ".join(f"{s['alias']} v{s['version']}" for s in self.plan["slices"])
            self.app.push_screen(ConfirmScreen(t("bake_confirm", count=len(self.ticked), slices=slices)), self.execute)

    def execute(self, confirmed: bool) -> None:
        if not confirmed:
            return
        try:
            result = self.store.bake(self.plan)
        except MindSliceError as error:
            self.failed(error, stale=error.details.get("code") == "stale_bake_plan")
            try:
                self.replan()
            except MindSliceError:
                pass
            self.redraw()
            return
        self.done(t("bake_done", slices=", ".join(f"{b['alias']} v{b['version']}" for b in result["baked"])))
