# MindSlice-tui

English | [中文](https://github.com/pancerZH/MindSlice-tui/blob/main/README-zh.md)

A terminal UI for a [MindSlice](https://github.com/pancerZH/MindSlice) workspace: browse cards, slices and the relations between cards, approve staged changes and bake overlay cards into slices, ticking each change by hand.

```
┌ Slices ──────┬ Card ───────────────────┬ Relations ───────────┐
│ ▼ @overlay 27│ MindSlice engine repo   │ → links out (10)     │
│  ▼ projects  │ @overlay/projects/      │   architecture ...   │
│   ▼ mindslice│   mindslice             │ ← backlinks (7)      │
│  ▼ prefs     │ tags: mindslice project │ ↑ extends (0)        │
│   coding ★   │ ─────────────────────── │ ↓ extended by (0)    │
│              │ MindSlice (github.com/  │ ⇒ supersedes (0)     │
│              │ pancerZH/MindSlice ...) │ ⇐ superseded by (0)  │
│              │                         │ ≡ same path (0)      │
│              │                         │ ✗ dangling (0)       │
│              │                         │ ──────────────────── │
│              │                         │ title and summary of │
│              │                         │ the selected card    │
└──────────────┴─────────────────────────┴──────────────────────┘
```

## Install

With Python 3.12+ and [pipx](https://pipx.pypa.io/) (or [uv](https://docs.astral.sh/uv/)) installed:

```sh
pipx install mindslice-tui   # or: uv tool install mindslice-tui
```

The MindSlice engine comes with it as a dependency.

## Run

```sh
mindslice-tui -w ~/mindslice
```

The workspace is found the same way the `mindslice` command finds it: `-w`, otherwise `$MINDSLICE_WORKSPACE`, otherwise the nearest parent directory that contains `mounts.toml`.

## Keys

| Key | Action |
| --- | --- |
| `↑` `↓` | Move in the tree on the left; the card and its relations follow |
| `tab` | Switch between the three panes |
| `enter` | In the relations pane, jump to the selected card. While the cursor rests on a neighbour, its title and summary are previewed under the list. Links in the card body can be clicked with the mouse |
| `backspace` | Go back to the card you jumped from |
| `/` | Full-text search (the engine's BM25; a superseded card leads to its replacement) |
| `g` | Neighbour tree: open the neighbours of the current card level by level (`space` opens a node, `enter` jumps) |
| `o` | Overview: status and pending review, issues, change history, always-loaded cards. The full text of the selected row is shown under each table; `enter` jumps to that row's card |
| `h` | Change history of the current card |
| `a` | Review staged changes (the footer shows how many wait; the focus card's change is highlighted first): `space` accepts, `x` rejects, an unmarked change stays pending; `a` applies the marks after a check and a confirmation |
| `b` | Bake overlay cards into slices: each card comes with a suggested destination (see below) and `space` ticks it; `d` picks another slice from a ranked list, or a new alias after `tab`; the plan and anything blocking it update with every tick; `b` bakes after a confirmation |
| `r` | Reload the workspace |
| `l` | Switch the interface language (English / 中文) |
| `q` | Quit |

Everywhere, `enter` confirms (a choice, a destination, the final "apply" or "bake" question) and `esc` cancels or closes.

Markers in the tree: `★` an always-loaded card (`load = "always"`), `!` the card has parse problems, `≡` the card is shadowed by a card at the same path in a higher-precedence mount; a dimmed, struck-out name means the card has been superseded. A yellow `+` / `~` / `−` marks a staged change (create / modify / delete) awaiting review; a staged new card is listed, in italics, where it will appear once accepted. The card pane shows the change's reason and diff, and `a` opens the review with that change highlighted.
If a reload with `r` fails (for example while `mounts.toml` is half written), the UI keeps what it was showing and reports the error.

The interface starts in English; `--lang zh` starts it in Chinese. Only the interface's own text is translated: card content and the engine's messages are shown as they are.

## Reading and writing

Browsing writes nothing, and the UI never calls `Workspace.read()`, which would count a read.
Like every other read command of `mindslice`, it lets the engine sync the rebuildable cache `.cache/index.sqlite` when files have changed,
and recover first if an unfinished journal exists. Cards, staging, history and the mount table are not modified (the tests assert this).

Memory changes only in the review (`a`) and bake (`b`) screens, and only for the rows you ticked, after you confirm:

- Review runs the engine's `review` (the same as `mindslice review`): the accepted and rejected changes go in one recoverable batch, after a dry run that reports conflicts, such as a link that would stop resolving. A change that conflicts with the live card can only be rejected or left pending. If staging changed while you were reviewing, nothing is executed: the list is reloaded and the marks of unchanged rows are kept.
- Bake suggests each card's destination, with the reason next to it: the slice the engine relates it to (`related`: same path, or the target of its `extends`/`supersedes`); otherwise the only slice with cards in the card's deepest folder (`same folder`; a folder several slices have does not count); otherwise the slice most of its links and backlinks lead into (`linked`); otherwise the slice whose cards rank best when searching for its title and summary, each hit weighted by its rank so that a big slice's many weak hits do not outvote a small slice's best ones (`similar`). A card nothing points anywhere for shows `?`. On a copy of a real workspace, treating each of its 136 baked cards as new put 136 back in their own slice.
- Bake runs the engine's workspace bake plan (the same as `mindslice bake`): unticked cards are deferred and stay in overlay, where they are live memory already. The plan is checked again when it runs, so a workspace that changed meanwhile makes it stop without writing anything.

Every engine call lives in `mindslice_tui/store.py`. `ws.index` and `ws._reading()` used there are engine internals;
once the engine offers a public graph query API, only that file needs to change.

## Development

```sh
git clone https://github.com/pancerZH/MindSlice-tui.git && cd MindSlice-tui
uv sync
uv run mindslice-tui -w ~/mindslice
uv run python -m unittest discover -s tests -t .
```
