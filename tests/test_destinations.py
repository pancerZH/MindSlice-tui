"""Destination suggestions for bake, on three slices built to reproduce the cases that went wrong on real
memory: a folder other slices share outweighing links, and a big slice whose many weak search hits outvoted a
small slice's best ones."""

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from mindslice import Workspace
from mindslice_tui.store import Store, suggestion

QUESTION = ("Raft snapshot question", "When should a follower install a snapshot instead of replaying the log?")
SLICES = {
    "big": {  # more cards than fit in the top ten hits, sharing only common words with QUESTION
        f"projects/alpha-tool/step-{i}": f"# Alpha tool step {i}\n\nThe log of this step raised a question.\n"
        for i in range(8)
    },
    "small": {  # two strong hits for QUESTION, a little weaker than the card itself
        "engineering/consensus-a": "# Raft snapshot lessons\n\nA follower should install a snapshot when "
                                   "replaying the log takes too long.\n",
        "engineering/consensus-b": "# Raft follower notes\n\nInstall a snapshot instead of replaying the whole log.\n",
    },
    "other": {"projects/garden": "# Garden\n\nTomatoes and basil.\n"},  # projects/ is in two slices, not in @small
}
LINKS = "- See [[@small/engineering/consensus-a]] and [[@small/engineering/consensus-b]]."


class DestinationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        root = Path(tmp.name)
        with Workspace.init(root / "ws") as ws:
            for alias, cards in SLICES.items():
                for path, text in cards.items():
                    file = root / alias / f"{path}.md"
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_text(text, encoding="utf-8")
                ws.mount(root / alias, alias=f"@{alias}")

            def card(path: str, title: str, summary: str, body: str) -> None:
                ws.write(path, title=title, summary=summary, content=body, stage=False, reason="test")

            # Each new card sits in overlay, so search finds the card itself too. Only the first one shares
            # words with QUESTION, so the others stay out of its hits.
            card("notes/raft-question", *QUESTION, "- Open.")
            card("notes/reading", "Alpha tool steps", "Reading about alpha tool steps.", LINKS)
            card("projects/new-thing", "New thing", "Something new.", LINKS)
            card("projects/alpha-tool/extra", "Extra", "One more.", LINKS)
            card("scratch/quokka", "Quokka", "Xylophone.", "- Nothing.")
        cls.store = Store(root / "ws")
        cls.addClassCleanup(cls.store.close)
        cls.snapshot = cls.store.load()

    def suggest(self, path: str) -> tuple:
        card = self.snapshot.cards[f"@overlay/{path}"]
        entry = {"id": path, "address": card.address, "title": card.title, "summary": card.summary}
        return suggestion(self.store.destinations(self.snapshot, entry))

    def test_search_hits_count_by_rank(self) -> None:
        # A case seen on a real workspace: the card itself first, then two strong hits in the
        # small slice and the big slice's weak hits. Counted, or ranked with the card itself, @big would win.
        hits = [hit["address"] for hit in self.store.search(" ".join(QUESTION), k=10)["results"]]
        self.assertEqual(hits[0], "@overlay/notes/raft-question")
        self.assertEqual({hit.partition("/")[0] for hit in hits[1:3]}, {"@small"})
        self.assertEqual(Counter(hit.partition("/")[0] for hit in hits[3:]), {"@big": 7})
        self.assertEqual(self.suggest("notes/raft-question"), ("@small", "search"))

    def test_links_outweigh_search(self) -> None:
        self.assertEqual(self.suggest("notes/reading"), ("@small", "links"))  # its words match @big

    def test_a_folder_one_slice_has_outweighs_links(self) -> None:
        self.assertEqual(self.suggest("projects/alpha-tool/extra"), ("@big", "path"))

    def test_a_folder_several_slices_have_does_not_count(self) -> None:
        # A case seen on a real workspace: projects/, which @big and @other share but @small
        # (where its links lead) lacks, must not outweigh the links.
        self.assertEqual(self.suggest("projects/new-thing"), ("@small", "links"))

    def test_nothing_to_go_on(self) -> None:
        self.assertEqual(self.suggest("scratch/quokka"), (None, None))
        blank = {"id": "x/y", "address": "@overlay/x/y", "title": "", "summary": ""}  # blank text: no search at all
        self.assertEqual(dict(self.store.destinations(self.snapshot, blank)), {"@big": (0, 0, 0), "@small": (0, 0, 0), "@other": (0, 0, 0)})


if __name__ == "__main__":
    unittest.main()
