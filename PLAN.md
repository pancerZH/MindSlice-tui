# MindSlice-tui 计划（v1：只读）

## Context

MindSlice 工作区（`~/mindslice`，目前 26 张卡片，全部在 `@overlay`）靠文件浏览器检查已经不方便：
卡片之间的关系（`[[wikilink]]`、`extends`、`supersedes`、同路径 shadow、悬空引用）分散在各文件的
frontmatter 和正文里，无法一眼看出谁引用谁、哪些卡片孤立、哪些被取代。

目标：用 Textual 做一个终端界面，围绕"焦点卡片"浏览卡片、slice 和它们之间的关系，
并提供工作区状态的只读管理视图。v1 不做任何写操作。

已确认的两个决定：

- **关系视图形态**：焦点卡片 + 关系面板（三栏），另加可逐层展开的邻居树做多跳探索。不做全局节点连线图。
- **数据来源**：依赖 `mindslice` 包的 Python API，不自己解析文件、不走 CLI 子进程。

## 范围

做：

- 浏览：mount → 目录 → 卡片的树；卡片正文与元数据；按边类型分组的关系面板；跳转与回退。
- 探索：邻居树（多跳）、全文搜索（引擎的 BM25）。
- 管理（只读）：挂载与状态、待审变更及 diff、变更历史、校验问题、常驻卡片（`load="always"`）。

不做（v1）：写卡片、apply/discard、mount/unmount、bake、rollback；全局连线图；文件监听自动刷新（用 `r` 手动刷新）。

## 技术选型

- Python ≥ 3.12（与引擎一致），依赖只有 `textual` 和 `mindslice>=0.1.6`；用 `uv` 管理。
- 包名 `mindslice-tui`，模块 `mindslice_tui`，命令 `mindslice-tui [-w WORKSPACE]`。
- 工作区定位沿用引擎规则：`-w` → `$MINDSLICE_WORKSPACE` → `Workspace.discover()`（最近的含 `mounts.toml` 的目录）。
- 测试用标准库 `unittest`（`IsolatedAsyncioTestCase` + Textual 的 `App.run_test()`），与引擎仓库一致，不引入 pytest。

## 数据层：`store.py`（唯一接触引擎的模块）

一次性加载出一个不可变快照，界面只读快照；`r` 重新加载。

```python
@dataclass(frozen=True)
class Card:   # address, mount, path, title, summary, tags, aliases, load, mtime_ns, sha256, errors, warnings, file
class Edge:   # src, kind ("wikilink" | "extends" | "supersedes"), raw, dst (可为 None), resolved
class Snapshot:  # mounts, cards: dict[address, Card], out_edges, in_edges, status, issues
```

复用的引擎接口（`~/Documents/workspace/mindslice/mindslice/`）：

| 需要 | 用什么 |
| --- | --- |
| 全部卡片与挂载 | `ws.index.all_cards()`、`ws.index.mount_rows()`（`retrieval/index.py`） |
| 全部边（已按引擎规则解析） | `links` 表：`src_mount, src_path, kind, raw, dst_mount, dst_path, resolved` |
| 保证索引新鲜 | 在 `with ws._reading():` 内查询（`workspace.py`） |
| 卡片正文 | 直接读 `mount.root / path + ".md"`，用 `model/card.py` 的 `parse_card` 拆出 summary/body |
| 取代转发、extends 组合、来源解释 | `ws.explain(address)`（不记 read 遥测） |
| 搜索 | `ws.search(query, source=..., tags=...)` |
| 状态与待审 | `ws.status()`、`ws.diff("staging")`（含 unified diff） |
| 历史 | `ws.card_history(address=None | 地址)` |
| 校验 | `ws.validate()` |
| slice 名称/版本/描述 | `storage/config.py` 的 `load_slice_manifest(mount.root)` |

快照上的派生信息（纯 Python，几行即可）：反链、被扩展/被取代、同路径 shadow（同 path 多个 mount，按 precedence 取胜者）、
悬空引用（`resolved = 0`）、孤立卡片（无入边也无出边）。

只读保证：

- 不调用 `write / apply / discard / review / mount / unmount / bake / rollback / restore`。
- 不调用 `ws.read()`（它会写 `read_count` 遥测）；需要组合结果时用 `explain()`。
- 仍会发生的唯一副作用是引擎任何读命令都有的行为：索引缓存 `.cache/index.sqlite` 过期时同步，以及存在未完成日志时的恢复。README 里写明。
- `ws.index` 和 `ws._reading` 是半内部接口，全部集中在 `store.py`，引擎以后提供公开的图查询 API 时只改这一个文件。

## 界面

主界面（三栏，焦点卡片驱动中、右两栏）：

```
┌ Slices ──────┬ Card ───────────────────┬ Relations ───────────┐
│ ▼ @overlay 26│ MindSlice engine repo   │ → links out (9)      │
│  ▼ projects  │ @overlay/projects/      │   architecture       │
│   ▶ mindslice│   mindslice             │   dev-workflow  ...  │
│   ▶ forge    │ tags: mindslice project │ ← backlinks (4)      │
│  ▶ prefs  ★2 │ ─────────────────────── │ ⇡ extends (0)        │
│  ▶ tools     │ MindSlice (github.com/  │ ⇣ extended by (0)    │
│              │ pancerZH/MindSlice ...) │ ⤳ supersedes (0)     │
│              │ - The user authors ...  │ ⤺ superseded by (0)  │
│              │                         │ ≡ shadows (0)        │
│              │                         │ ✗ dangling (0)       │
└──────────────┴─────────────────────────┴──────────────────────┘
 / 搜索  g 邻居树  o 概览  h 历史  r 刷新  enter 跳转  backspace 回退  q 退出
```

- **Slices 树**（`Tree`）：mount（别名、precedence、role、卡片数）→ 目录 → 卡片。标记：`★` 常驻、`⚠` 有校验问题、被取代的卡片置灰、被 shadow 的卡片标 `≡`。
- **Card**：标题、地址、tags、aliases、load、修改时间、文件路径；正文用 `Markdown` 组件渲染，`[[ref]]` 预处理成链接，点击或回车即跳转。
- **Relations**（`Tree`）：按上图分组，每项显示目标标题和所在 mount；回车把它设为焦点卡片。悬空引用显示原始 `raw` 文本。
- **导航历史**：焦点卡片栈，`backspace` 回退。

其他屏幕：

- **邻居树**（`g`）：以焦点卡片为根的 `Tree`，节点懒展开为其邻居，标注边的类型和方向；已在当前路径上的节点标记为环，不再展开。
- **搜索**（`/`）：输入框 + 结果列表（标题、地址、summary、coverage），回车跳转；`unmatched_terms` 显示在底部。
- **概览**（`o`，`TabbedContent`）：
  - 状态：mount 表、卡片数、未 bake 的 overlay 卡片、待审变更列表及 diff。
  - 问题：校验 errors/warnings、悬空引用、孤立卡片、未 rebase 的扩展、取代链。每行可跳到对应卡片。
  - 历史：`.history/changes.jsonl` 时间线（时间、事件、op、地址、reason）。
  - 常驻：`load="always"` 的卡片列表。
- **卡片历史**（`h`）：当前卡片的变更记录及 reason。

## 文件结构

```
PLAN.md
README.md
pyproject.toml
mindslice_tui/
  __init__.py
  __main__.py     # 参数解析，定位工作区，启动 App
  store.py        # Snapshot / Card / Edge 与全部引擎调用
  app.py          # App、按键绑定、焦点卡片与导航历史
  widgets.py      # SliceTree、CardView、RelationsPanel
  screens.py      # SearchScreen、NeighborTreeScreen、OverviewScreen、HistoryScreen
  app.tcss
tests/
  fixture.py      # 用引擎 API 生成临时工作区
  test_store.py
  test_app.py
```

同步加载即可（当前规模毫秒级，且 sqlite 连接留在主线程）；只有实测卡顿时才改成后台 worker。

## 里程碑

状态（2026-11-15）：M1–M3 已实现并通过测试。与上文的出入：卡片正文显示的是文件本身，
没有用 `ws.explain()` 做 extends 组合视图；悬空引用由引擎的 `validate()` 报告，问题页不再重复列出。

1. **M1 骨架与浏览**：`pyproject.toml`、`store.py` 快照加载、三栏主界面、树选择 → 正文与关系面板、`r` 刷新。
2. **M2 关系导航**：关系面板跳转、正文内 `[[链接]]` 跳转、回退栈、邻居树、搜索。
3. **M3 管理视图**：概览四个标签页、卡片历史。
4. **之后再议**：写模式（编辑、apply/discard）、全局连线图、文件监听。

## 验证

- 测试夹具：`Workspace.init(tmp)` 后用 `ws.write` 造卡片，覆盖 wikilink、`extends`、`supersedes`、悬空引用、`load="always"`，再挂一个只读 slice 目录制造 shadow。
- `test_store.py`：快照的卡片数、每类边、反链、shadow、悬空、孤立与预期一致；并与 `ws.explain` / `mindslice read --json` 的 links/backlinks 交叉核对。
- `test_app.py`：`App.run_test()` 驱动按键——选树节点后正文和关系面板更新、回车跳转、`backspace` 回退、`/` 搜索跳转、`o` 概览打开。
- 只读检查（测试里断言）：运行前后 `overlay/`、`staging/`、`.history/`、`mounts.toml` 的文件哈希不变，遥测 `read_count` 不变。
- 手动：`uv run mindslice-tui -w ~/mindslice`，打开 `@overlay/projects/mindslice`，关系面板应显示 9 条出链；
  `uv run python -m unittest discover -s tests -t .` 全部通过。
