import tempfile
import unittest
from pathlib import Path

from mindslice import Workspace
from mindslice_tui.store import Store

from tests.fixture import build, memory_digest


class StoreTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = build(Path(tmp.name))
        self.store = Store(self.root)
        self.addCleanup(self.store.close)
        self.snapshot = self.store.load()

    def relations(self, address: str) -> dict[str, list[str]]:
        return dict(self.snapshot.relations(address))

    def test_cards_and_mounts(self) -> None:
        self.assertEqual([m.alias for m in self.snapshot.mounts], ["@overlay", "@base"])
        self.assertEqual(len(self.snapshot.cards), 10)
        card = self.snapshot.cards["@overlay/prefs/language"]
        self.assertTrue(card.always)
        self.assertEqual(card.title, "Reply language")
        self.assertTrue(card.file.is_file())

    def test_links_and_dangling(self) -> None:
        alpha = self.relations("@overlay/notes/alpha")
        self.assertEqual(alpha["links_out"], ["@overlay/notes/beta"])
        self.assertEqual(self.snapshot.dangling("@overlay/notes/alpha")[0].raw, "missing/card")
        self.assertEqual(self.relations("@overlay/notes/beta")["backlinks"], ["@overlay/notes/alpha"])

    def test_lineage(self) -> None:
        old = self.relations("@overlay/notes/old")
        self.assertEqual(old["superseded_by"], ["@overlay/notes/new"])
        self.assertEqual(old["extended_by"], ["@overlay/notes/ext"])
        self.assertEqual(self.relations("@overlay/notes/new")["supersedes"], ["@overlay/notes/old"])
        self.assertEqual(self.relations("@overlay/notes/ext")["extends"], ["@overlay/notes/old"])
        self.assertTrue(self.snapshot.is_superseded("@overlay/notes/old"))
        self.assertFalse(self.snapshot.is_superseded("@overlay/notes/new"))

    def test_shadows(self) -> None:
        self.assertEqual(self.relations("@overlay/team/lead")["same_path"], ["@base/team/lead"])
        self.assertEqual(self.snapshot.shadowed, {"@base/team/lead"})

    def test_issues(self) -> None:
        issues = {(kind, address) for kind, address, _ in self.snapshot.issues()}
        self.assertIn(("warning", "@overlay/notes/alpha"), issues)  # the engine reports the broken link
        self.assertIn(("stale_extends", "@overlay/notes/ext"), issues)
        self.assertIn(("supersedes", "@overlay/notes/new"), issues)
        self.assertIn(("shadowed", "@base/team/lead"), issues)
        self.assertIn(("orphan", "@overlay/notes/lone"), issues)
        self.assertNotIn(("orphan", "@overlay/prefs/language"), issues)  # standing cards need no links

    def test_markdown_links_point_at_addresses(self) -> None:
        text = self.store.markdown(self.snapshot, "@overlay/notes/alpha")
        self.assertIn("[notes/beta](<@overlay/notes/beta>)", text)
        self.assertIn("[[missing/card]]", text)

    def test_matches_the_engine(self) -> None:
        with Workspace(self.root) as ws:
            for address in self.snapshot.cards:
                read = ws.read(address, follow_supersedes=False, max_backlinks=100)
                relations = self.relations(address)
                links = [link["address"] for link in read.get("links", []) if link.get("address")]
                backlinks = [link["address"] for link in read.get("backlinks", [])]
                self.assertEqual(sorted(relations["links_out"]), sorted(set(links)), address)
                self.assertEqual(sorted(relations["backlinks"]), sorted(backlinks), address)

    def test_search_history_pending(self) -> None:
        self.assertEqual(self.store.search("zebras")["results"][0]["address"], "@overlay/notes/beta")
        self.assertEqual(self.store.history("@overlay/notes/lone")[0]["reason"], "fixture: notes/lone")
        pending = self.store.staged()["items"]
        self.assertEqual([item["address"] for item in pending], ["@overlay/notes/beta"])
        self.assertIn("+- A staged statement.", pending[0]["diff"])

    def test_reading_writes_no_memory(self) -> None:
        def reads() -> list:
            return self.store.ws.index.conn.execute("SELECT * FROM telemetry").fetchall()

        before = memory_digest(self.root), reads()
        snapshot = self.store.load()
        for address in snapshot.cards:
            self.store.markdown(snapshot, address)
            self.store.history(address)
        snapshot.issues()
        self.store.search("rule")
        self.store.history()
        self.store.staged()
        self.assertEqual((memory_digest(self.root), reads()), before)


if __name__ == "__main__":
    unittest.main()
