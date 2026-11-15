import asyncio
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Markdown, TabbedContent

from mindslice_tui.app import MindSliceApp
from mindslice_tui.screens import HistoryScreen, NeighborsScreen, OverviewScreen, SearchScreen
from mindslice_tui.store import Store
from mindslice_tui.widgets import SliceTree, Table

from tests.fixture import build, memory_digest
from tests.screen import screen_text

ALPHA, BETA = "@overlay/notes/alpha", "@overlay/notes/beta"


class AppTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
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
            self.assertIn("1 条结果", screen_text(self.app))
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
            self.app.show(BETA)  # trail: alpha
            await pilot.pause()
            (self.root / "overlay" / "notes" / "beta.md").unlink()
            await pilot.press("r")
            await pilot.pause()
            self.assertEqual(self.app.address, ALPHA)  # fell back to the first card
            self.assertNotIn("Beta summary.", screen_text(self.app))
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

    async def test_a_session_writes_no_memory(self) -> None:
        before = memory_digest(self.root)
        async with self.run_app() as pilot:
            for keys in (["down", "down"], ["slash", *"rule"], ["escape"], ["g", "escape"], ["o", "escape"],
                         ["h", "escape"], ["r"]):
                await pilot.press(*keys)
                await pilot.pause()
        self.assertEqual(memory_digest(self.root), before)


if __name__ == "__main__":
    unittest.main()
