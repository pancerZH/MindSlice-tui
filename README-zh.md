# MindSlice-tui

[English](README.md) | 中文

[MindSlice](https://github.com/pancerZH/MindSlice) 工作区的只读终端界面：浏览卡片、slice，以及卡片之间的关系。

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
│              │                         │ 所选邻居的标题与摘要 │
└──────────────┴─────────────────────────┴──────────────────────┘
```

## 安装

需要 Python 3.12+ 和 [pipx](https://pipx.pypa.io/)（或 [uv](https://docs.astral.sh/uv/)）：

```sh
pipx install mindslice-tui   # 或者：uv tool install mindslice-tui
```

MindSlice 引擎会作为依赖一并安装。

## 运行

```sh
mindslice-tui -w ~/mindslice
```

工作区的定位规则与 `mindslice` 命令相同：`-w`，否则 `$MINDSLICE_WORKSPACE`，否则向上找最近的含 `mounts.toml` 的目录。

## 按键

| 键 | 作用 |
| --- | --- |
| `↑` `↓` | 在左侧树中移动，中间和右侧随之更新 |
| `tab` | 在三栏之间切换 |
| `enter` | 在关系面板中跳到所选卡片；光标停在某个邻居上时，面板下方先预览它的标题和摘要（正文里的链接可用鼠标点击） |
| `backspace` | 回到上一张跳转前的卡片 |
| `/` | 全文搜索（引擎的 BM25；被取代的卡片会指向它的替代者） |
| `g` | 邻居树：从当前卡片逐层展开邻居（`space` 展开，`enter` 跳转） |
| `o` | 概览：状态与待审变更、问题、变更历史、常驻卡片；表格下方显示所选行的完整内容，`enter` 跳到该行的卡片 |
| `h` | 当前卡片的变更历史 |
| `r` | 重新读取工作区 |
| `l` | 切换界面语言（English / 中文） |
| `q` | 退出 |

树中的标记：`★` 常驻卡片（`load = "always"`），`!` 解析有问题，`≡` 被更高优先级的同路径卡片遮盖，置灰加删除线表示已被取代。
按 `r` 刷新时如果读取失败（例如 `mounts.toml` 正写到一半），界面保留旧内容并给出提示。

界面默认是英文，用 `--lang zh` 可以直接以中文启动。只翻译界面自身的文字，卡片内容和引擎给出的信息保持原样。

## 只读

界面不调用任何写操作（write、apply、discard、mount、bake 等），也不调用会记录阅读次数的 `Workspace.read()`。
与 `mindslice` 的其他读命令一样，文件有变化时引擎会同步 `.cache/index.sqlite` 这个可重建的缓存，
并在存在未完成的日志时先做恢复；卡片、staging、历史和挂载表不会被改动（测试里有断言）。

所有引擎调用都在 `mindslice_tui/store.py` 里。其中 `ws.index` 和 `ws._reading()` 是引擎的内部接口，
引擎提供公开的图查询 API 后只需改这一个文件。

## 开发

```sh
git clone https://github.com/pancerZH/MindSlice-tui.git && cd MindSlice-tui
uv sync
uv run mindslice-tui -w ~/mindslice
uv run python -m unittest discover -s tests -t .
```
