# MindSlice-tui

English | [中文](README-zh.md)

A read-only terminal UI for a [MindSlice](https://github.com/pancerZH/MindSlice) workspace: browse cards, slices and the relations between cards.

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

## Run

```sh
uv run mindslice-tui -w ~/mindslice
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
| `r` | Reload the workspace |
| `l` | Switch the interface language (English / 中文) |
| `q` | Quit |

Markers in the tree: `★` an always-loaded card (`load = "always"`), `!` the card has parse problems, `≡` the card is shadowed by a card at the same path in a higher-precedence mount; a dimmed, struck-out name means the card has been superseded.
If a reload with `r` fails (for example while `mounts.toml` is half written), the UI keeps what it was showing and reports the error.

The interface starts in English; `--lang zh` starts it in Chinese. Only the interface's own text is translated: card content and the engine's messages are shown as they are.

## Read-only

The UI calls no write operation (write, apply, discard, mount, bake and so on), and it does not call `Workspace.read()`, which would count a read.
Like every other read command of `mindslice`, it lets the engine sync the rebuildable cache `.cache/index.sqlite` when files have changed,
and recover first if an unfinished journal exists. Cards, staging, history and the mount table are never modified (the tests assert this).

Every engine call lives in `mindslice_tui/store.py`. `ws.index` and `ws._reading()` used there are engine internals;
once the engine offers a public graph query API, only that file needs to change.

## Development

```sh
uv sync
uv run python -m unittest discover -s tests -t .
```
