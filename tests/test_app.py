import asyncio
import tempfile
import unittest
from pathlib import Path

from mindslice import Workspace
from textual.widgets import Markdown, TabbedContent

from mindslice_tui import i18n
from mindslice_tui.app import MindSliceApp
from mindslice_tui.review import BakeScreen, ConfirmScreen, DestinationScreen, ReviewScreen
from mindslice_tui.screens import HistoryScreen, NeighborsScreen, OverviewScreen, SearchScreen
from mindslice_tui.store import Store
from textual.widgets import OptionList
from mindslice_tui.widgets import SliceTree, Table

from tests.fixture import build, memory_digest
from tests.screen import screen_text

ALPHA, BETA = "@overlay/notes/alpha", "@overlay/notes/beta"


class AppTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        i18n.use("en")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = build(Path(tmp.name))
        self.store = Store(self.root)
        self.addCleanup(self.store.close)
        self.app = MindSliceApp(self.store)

    async def asyncSetUp(self) -> None:
        asyncio.get_running_loop().set_debug(False)  # unittest's debug loop makes Textual about 10x slower

    def run_app(self):
        return self.app.run_test(size=(140, 40))

    async def test_starts_on_the_first_card(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            self.assertEqual(self.app.address, ALPHA)
            text = screen_text(self.app)
            self.assertIn("Alpha summary.", text)
            self.assertIn("→ links out (1)", text)
            self.assertIn("✗ dangling (1)", text)
            self.assertIn("language ★", text)

    async def test_tree_cursor_previews_without_history(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(self.app.address, BETA)
            self.assertEqual(self.app.trail, [])

    async def test_relation_jump_and_back(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            self.app.query_one("#relations Tree").focus()
            await pilot.press("down", "down")  # group header, then the Beta link
            await pilot.pause()
            self.assertIn("Beta summary.", screen_text(self.app))  # previewed before jumping
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(self.app.address, BETA)
            self.assertEqual(self.app.trail, [ALPHA])
            self.assertEqual(self.app.query_one(SliceTree).cursor_node.data, BETA)
            self.assertIn("← backlinks (1)", screen_text(self.app))
            await pilot.press("backspace")
            await pilot.pause()
            self.assertEqual(self.app.address, ALPHA)
            self.assertEqual(self.app.trail, [])

    async def test_body_link_jumps(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            markdown = self.app.query_one(Markdown)
            markdown.post_message(Markdown.LinkClicked(markdown, BETA))
            await pilot.pause()
            self.assertEqual(self.app.address, BETA)

    async def test_search(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("slash", *"zebras")
            await pilot.pause(0.3)  # the search runs once typing pauses
            self.assertIsInstance(self.app.screen, SearchScreen)
            self.assertIn("1 found", screen_text(self.app))
            await pilot.press("enter", "enter")
            await pilot.pause()
            self.assertEqual(self.app.address, BETA)

    async def test_neighbor_tree(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("g")
            await pilot.pause()
            self.assertIsInstance(self.app.screen, NeighborsScreen)
            await pilot.press("down", "space")  # open Beta: its only neighbour is the root again
            await pilot.pause()
            self.assertIn("↺", screen_text(self.app))
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(self.app.address, BETA)

    async def test_overview(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("o")
            await pilot.pause()
            self.assertIsInstance(self.app.screen, OverviewScreen)
            text = screen_text(self.app)
            self.assertIn("Pending review (1)", text)
            self.assertIn("+- A staged statement.", text)
            tabs = self.app.screen.query_one(TabbedContent)
            for pane, expected in (("history", "fixture: notes/lone"), ("always", "Reply language"),
                                   ("issues", "[[missing/card]] does not resolve")):
                tabs.active = pane
                await pilot.pause()
                self.assertIn(expected, screen_text(self.app))
            table = self.app.screen.query_one("#issues Table", Table)
            table.table.focus()
            table.table.move_cursor(row=next(i for i, row in enumerate(self.app.snapshot.issues()) if row[0] == "orphan"))
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(self.app.address, "@overlay/notes/lone")

    async def test_card_history(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("h")
            await pilot.pause()
            self.assertIsInstance(self.app.screen, HistoryScreen)
            self.assertIn("fixture: notes/alpha", screen_text(self.app))
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(self.app.address, ALPHA)

    async def test_refresh_picks_up_new_files(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            (self.root / "overlay" / "notes" / "gamma.md").write_text("# Gamma\n\nAdded outside.\n", encoding="utf-8")
            await pilot.press("r")
            await pilot.pause()
            self.assertIn("@overlay/notes/gamma", self.app.snapshot.cards)
            self.assertIn("@overlay/notes/gamma", self.app.query_one(SliceTree).nodes)
            self.assertEqual(self.app.address, ALPHA)

    async def test_search_opens_a_card_newer_than_the_snapshot(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            (self.root / "overlay" / "notes" / "gamma.md").write_text("# Gamma\n\nAbout quokkas.\n", encoding="utf-8")
            await pilot.press("slash", *"quokkas")
            await pilot.pause(0.3)
            await pilot.press("enter", "enter")
            await pilot.pause()
            self.assertEqual(self.app.address, "@overlay/notes/gamma")

    async def test_focus_card_deleted_outside(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            self.app.show("@overlay/notes/lone")  # trail: alpha
            await pilot.pause()
            (self.root / "overlay" / "notes" / "lone.md").unlink()
            await pilot.press("r")
            await pilot.pause()
            self.assertEqual(self.app.address, ALPHA)  # fell back to the first card
            self.assertNotIn("Lone summary.", screen_text(self.app))
            await pilot.press("backspace", "backspace")  # nothing sensible to go back to: no crash
            await pilot.pause()
            self.assertEqual((self.app.address, self.app.trail), (ALPHA, []))

    async def test_failed_refresh_keeps_the_old_snapshot(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            mounts = self.root / "mounts.toml"
            good = mounts.read_text(encoding="utf-8")
            mounts.write_text("this is not toml [", encoding="utf-8")
            await pilot.press("r")
            await pilot.pause()
            self.assertEqual(len(self.app.snapshot.cards), 10)
            # Toasts are not part of the exported screen, so look at the app's notifications.
            self.assertIn("invalid TOML", [note.message for note in self.app._notifications][-1])
            mounts.write_text(good, encoding="utf-8")
            await pilot.press("r")
            await pilot.pause()
            self.assertEqual(self.app.address, ALPHA)

    async def test_language_key_switches_english_and_chinese(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            text = screen_text(self.app)
            for english in ("Search", "Relations", "→ links out (1)", "modified "):
                self.assertIn(english, text)
            await pilot.press("l")
            await pilot.pause()
            text = screen_text(self.app)
            for chinese in ("搜索", "关系", "→ 出链 (1)", "修改于 ", "English"):
                self.assertIn(chinese, text)
            self.assertNotIn("Search", text)
            self.assertEqual(self.app.address, ALPHA)  # same card, no history entry
            self.assertEqual(self.app.trail, [])
            await pilot.press("o")
            await pilot.pause()
            self.assertIn("待审变更（1）", screen_text(self.app))
            await pilot.press("escape", "a")
            await pilot.pause()
            self.assertIn("接受 0 · 拒绝 0 · 保持待审 1", screen_text(self.app))
            await pilot.press("escape", "l")
            await pilot.pause()
            self.assertIn("Search", screen_text(self.app))

    async def test_a_session_writes_no_memory(self) -> None:
        before = memory_digest(self.root)
        async with self.run_app() as pilot:
            for keys in (["down", "down"], ["slash", *"rule"], ["escape"], ["g", "escape"], ["o", "escape"],
                         ["h", "escape"], ["r"],
                         ["a", "space", "a", "escape", "escape"],  # review: ticked and asked, then declined
                         ["b", "space", "tab", *"notes", "enter", "b", "escape"],  # bake: blocked plan, closed
                         ["b", *["down"] * 7, "space", "b", "escape", "escape"]):  # bake: ready plan, declined
                await pilot.press(*keys)
                await pilot.pause()
        self.assertEqual(memory_digest(self.root), before)

    def notes(self) -> list[str]:
        return [note.message for note in self.app._notifications]

    async def test_review_accepts_a_ticked_change(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            self.assertIn("Review (1)", screen_text(self.app))  # the footer counts staged changes
            await pilot.press("a")
            await pilot.pause()
            self.assertIsInstance(self.app.screen, ReviewScreen)
            text = screen_text(self.app)
            self.assertIn("reason: fixture: staged", text)
            self.assertIn("+- A staged statement.", text)
            await pilot.press("a")  # nothing ticked yet: nothing to apply
            await pilot.pause()
            self.assertIsInstance(self.app.screen, ReviewScreen)
            self.assertIn("Mark changes with space or x first", self.notes())
            await pilot.press("space", "a")
            await pilot.pause()
            self.assertIsInstance(self.app.screen, ConfirmScreen)
            self.assertIn("Accept 1 and reject 0 staged change(s)? 0 stay pending.", screen_text(self.app))
            await pilot.press("enter")
            await pilot.pause()
            self.assertNotIsInstance(self.app.screen, (ReviewScreen, ConfirmScreen))
            self.assertIn("Accepted 1, rejected 0", self.notes())
        self.assertEqual(self.store.staged()["items"], [])
        self.assertIn("A staged statement.", (self.root / "overlay/notes/beta.md").read_text(encoding="utf-8"))

    async def test_staged_changes_show_in_tree_and_card(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            text = screen_text(self.app)
            self.assertIn("beta ~", text)  # the tree marks the card with a staged change
            self.assertIn("● Staged change: modify · press a to review", text)
            self.assertIn("+- A staged statement.", text)
            self.assertIn("reason: fixture: staged", text)

    async def test_staged_create_sits_in_the_tree_and_opens_the_review_on_it(self) -> None:
        with Workspace(self.root) as ws:
            ws.write("prefs/tone", title="Reply tone", summary="Be brief.", content="- Short answers.",
                     load="always", stage=True, reason="fixture: staged create")
        self.app = MindSliceApp(self.store)
        tone = "@overlay/prefs/tone"
        async with self.run_app() as pilot:
            await pilot.pause()
            self.assertIn("Review (2)", screen_text(self.app))
            self.app.query_one(SliceTree).reveal(tone)
            await pilot.pause()
            self.assertEqual(self.app.address, tone)
            text = screen_text(self.app)
            self.assertIn("tone ★ +", text)
            self.assertIn("Reply tone", text)
            self.assertIn("● Staged change: new card", text)
            self.assertIn("+- Short answers.", text)
            await pilot.press("a")
            await pilot.pause()
            screen = self.app.screen
            self.assertIsInstance(screen, ReviewScreen)
            self.assertEqual(screen.current(), "prefs/tone")  # the focus card's change is highlighted
            await pilot.press("space", "a", "enter")
            await pilot.pause()
            self.assertIn(tone, self.app.snapshot.cards)
            self.assertNotIn(tone, self.app.snapshot.pending)
            self.assertEqual(self.app.address, tone)

    async def test_review_rejects_a_change(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("a", "x", "a", "enter")
            await pilot.pause()
            self.assertIn("Accepted 0, rejected 1", self.notes())
            self.assertNotIn("Review (1)", screen_text(self.app))
        self.assertEqual(self.store.staged()["items"], [])
        self.assertNotIn("A staged statement.", (self.root / "overlay/notes/beta.md").read_text(encoding="utf-8"))

    async def test_review_refuses_to_accept_a_conflict(self) -> None:
        beta = self.root / "overlay/notes/beta.md"
        beta.write_text(beta.read_text(encoding="utf-8") + "- Changed outside.\n", encoding="utf-8")
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("a", "space")
            await pilot.pause()
            self.assertIn("conflicts with the live card", self.notes()[-1])
            self.assertEqual(self.app.screen.marks, {})
            await pilot.press("x")  # rejecting it is fine
            await pilot.pause()
            self.assertEqual(self.app.screen.marks, {"notes/beta": "reject"})

    async def test_review_reloads_when_staging_changes_meanwhile(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("a", "space")
            await pilot.pause()
            with Workspace(self.root) as ws:
                ws.write("notes/lone", op="append", content=["- Staged later."], stage=True, reason="later")
            await pilot.press("a")
            await pilot.pause()
            screen = self.app.screen
            self.assertIsInstance(screen, ReviewScreen)  # nothing was asked or executed
            self.assertIn("The workspace changed meanwhile", self.notes()[-1])
            self.assertEqual(list(screen.items), ["notes/beta", "notes/lone"])
            self.assertEqual(screen.marks, {"notes/beta": "accept"})  # unchanged, so still ticked
            await pilot.press("a", "enter")
            await pilot.pause()
        self.assertEqual([item["id"] for item in self.store.staged()["items"]], ["notes/lone"])

    async def test_bake_a_ticked_card_into_a_new_slice(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("b")
            await pilot.pause()
            screen = self.app.screen
            self.assertIsInstance(screen, BakeScreen)
            self.assertIn("Nothing chosen: every card stays in overlay", screen_text(self.app))
            await pilot.press("down", "down", "down")  # alpha, beta, ext, lone
            await pilot.press("space")  # lone has no destination yet: space asks for one
            await pilot.pause()
            self.assertIsInstance(self.app.screen, DestinationScreen)
            await pilot.press("tab", *"notes", "enter")
            await pilot.pause()
            self.assertEqual((screen.ticked, screen.dest["notes/lone"]), ({"notes/lone"}, "@notes"))
            self.assertEqual(screen.current(), "notes/lone")  # the cursor stays on the row
            self.assertIn("@notes  new slice v0.1.0 · 1 card(s)", screen_text(self.app))
            await pilot.press("b")
            await pilot.pause()
            self.assertIsInstance(self.app.screen, ConfirmScreen)
            await pilot.press("enter")
            await pilot.pause()
            self.assertIn("Baked @notes v0.1.0", self.notes())
            self.assertIn("@notes/notes/lone", self.app.snapshot.cards)
            self.assertNotIn("@overlay/notes/lone", self.app.snapshot.cards)
            self.assertIn("@overlay/notes/alpha", self.app.snapshot.cards)  # unticked cards stay in overlay
        self.assertEqual(len(self.store.staged()["items"]), 1)  # staging is untouched

    async def test_bake_refresh_removes_a_card_another_session_already_baked(self) -> None:
        async with self.run_app() as pilot:
            await pilot.press("b")
            await pilot.pause()
            screen = self.app.screen
            screen.choose("notes/lone", True, "@notes")
            with Workspace(self.root) as other:
                other.bake(plan=screen.plan)
            screen.replan()
            self.assertNotIn("notes/lone", screen.cards)
            self.assertNotIn("notes/lone", screen.ticked)
            self.assertIn("notes/alpha", screen.cards)

    async def test_bake_suggests_a_destination(self) -> None:
        with Workspace(self.root) as ws:  # a new card in a folder only @base has
            ws.write("team/oncall", title="On call", summary="Who is on call.", content="- Linus.", stage=False,
                     reason="test")
        self.app.snapshot = self.store.load()
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("b")
            await pilot.pause()
            screen = self.app.screen
            self.assertEqual(screen.suggested["team/oncall"], ("@base", "path"))
            self.assertEqual(screen.suggested["notes/lone"], (None, None))  # nothing points anywhere
            self.assertEqual(screen.suggested["team/lead"], ("@base", "related"))  # the engine's relation comes first
            self.assertIn("@base  same folder", screen_text(self.app))
            await pilot.press(*["down"] * 8, "space")  # team/oncall: space ticks it straight away
            await pilot.pause()
            self.assertEqual(screen.ticked, {"team/oncall"})
            await pilot.press("d")  # the picker lists the slices with what speaks for each
            await pilot.pause()
            self.assertIsInstance(self.app.screen, DestinationScreen)
            self.assertIsInstance(self.app.screen.focused, OptionList)
            self.assertIn("@base  1 shared folder(s)", screen_text(self.app))
            await pilot.press("escape", "up", "d", "tab", *"@notes", "enter")  # team/lead: a new slice
            await pilot.pause()
            self.assertEqual(screen.dest["team/lead"], "@notes")
            self.assertNotIn("@notes  related", screen_text(self.app))  # no longer the suggested slice
            await pilot.press("down", "d")  # a new slice chosen meanwhile is offered for the next card too
            await pilot.pause()
            self.assertIn("@notes  new slice", screen_text(self.app))

    async def test_bake_shows_blockers_and_refuses(self) -> None:
        async with self.run_app() as pilot:
            await pilot.pause()
            await pilot.press("b", "space", "tab", *"notes", "enter")  # alpha links to beta, which stays in overlay
            await pilot.pause()
            text = screen_text(self.app)
            self.assertEqual(text.count("blocked:"), 2)  # one line per problem, though the engine reports each twice
            self.assertIn("referenced overlay card needs a destination (notes/beta)", text)
            await pilot.press("b")
            await pilot.pause()
            self.assertIsInstance(self.app.screen, BakeScreen)
            self.assertIn("Resolve the blocked items first", self.notes()[-1])
            await pilot.press("space")  # untick: the plan is empty again
            await pilot.pause()
            self.assertNotIn("blocked:", screen_text(self.app))
            await pilot.press(*["down"] * 7, "space")  # team/lead has one related slice: space ticks it at once
            await pilot.pause()
            self.assertEqual(self.app.screen.ticked, {"team/lead"})
            self.assertIn("@base  new version v0.1.0 · 1 card(s)", screen_text(self.app))


if __name__ == "__main__":
    unittest.main()
