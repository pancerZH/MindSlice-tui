"""Browse a MindSlice workspace in the terminal, read-only."""

from __future__ import annotations

import argparse
import os
import sys

from mindslice import MindSliceError

from .app import MindSliceApp
from .store import Store


def main() -> None:
    parser = argparse.ArgumentParser(prog="mindslice-tui", description=__doc__)
    parser.add_argument("-w", "--workspace", default=os.environ.get("MINDSLICE_WORKSPACE"),
                        help="workspace root (default: $MINDSLICE_WORKSPACE or nearest dir with mounts.toml)")
    args = parser.parse_args()
    try:
        store = Store(args.workspace)
        app = MindSliceApp(store)  # loads the workspace
    except MindSliceError as error:
        sys.exit(f"mindslice-tui: {error}")
    try:
        app.run()
    finally:
        store.close()


if __name__ == "__main__":
    main()
