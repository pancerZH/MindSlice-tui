# MindSlice-tui

[English](README.md) | 中文

[MindSlice](https://github.com/pancerZH/MindSlice) 工作区的终端界面：浏览卡片、slice，以及卡片之间的关系；逐条勾选，批准 staging 中的待审变更，或把 overlay 卡片 bake 进 slice。

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
| `a` | 审批待审变更（底栏显示待审数量，当前卡片的变更会先被选中）：`space` 接受，`x` 拒绝，不标记的保持待审；`a` 先检查，确认后执行 |
| `b` | 把 overlay 卡片 bake 进 slice：每张卡片带有推荐的目标 slice（见下文），`space` 勾选；`d` 从排好序的列表里另选，或按 `tab` 输入新 alias；每次勾选后计划和受阻项随之更新；`b` 确认后执行 |
| `r` | 重新读取工作区 |
| `l` | 切换界面语言（English / 中文） |
| `q` | 退出 |

所有地方都是 `enter` 确认（选择、目标 slice、最后的执行确认），`esc` 取消或关闭。

树中的标记：`★` 常驻卡片（`load = "always"`），`!` 解析有问题，`≡` 被更高优先级的同路径卡片遮盖，置灰加删除线表示已被取代。黄色 `+` / `~` / `−` 表示有待审的 staged 变更（新建 / 修改 / 删除）；待审的新卡片以斜体列在批准后将出现的位置。卡片面板显示该变更的原因和 diff，按 `a` 打开审批并定位到这条变更。
按 `r` 刷新时如果读取失败（例如 `mounts.toml` 正写到一半），界面保留旧内容并给出提示。

界面默认是英文，用 `--lang zh` 可以直接以中文启动。只翻译界面自身的文字，卡片内容和引擎给出的信息保持原样。

## 读与写

浏览不写任何东西，也不调用会记录阅读次数的 `Workspace.read()`。
与 `mindslice` 的其他读命令一样，文件有变化时引擎会同步 `.cache/index.sqlite` 这个可重建的缓存，
并在存在未完成的日志时先做恢复；卡片、staging、历史和挂载表不会被改动（测试里有断言）。

只有审批（`a`）和 bake（`b`）界面会改动记忆，且只针对勾选的行、在确认之后：

- 审批调用引擎的 `review`（与 `mindslice review` 相同）：接受和拒绝的变更作为一个可恢复的批次执行，执行前先试运行并报告冲突，例如会导致某个链接失效。与当前卡片冲突的变更只能拒绝或保持待审。如果审批期间 staging 有变化，不会执行任何操作：列表重新加载，未变化的行保留原来的标记。
- Bake 为每张卡片推荐目标 slice，旁边注明理由：引擎认定的相关 slice（`相关`：同路径，或其 `extends`/`supersedes` 的目标所在）；否则是唯一一个在卡片最深一层目录下有卡片的 slice（`同目录`；多个 slice 都有的目录不算）；否则是卡片的出链和反链最多指向的 slice（`有链接`）；否则用标题和摘要搜索，按名次给命中加权（第 1 名记 1，第 2 名记 1/2……），得分最高的 slice（`内容相似`），这样大 slice 的大量弱命中不会压过小 slice 的最佳命中。没有任何依据的卡片显示 `?`。在一份真实工作区的副本上，把 136 张已 bake 的卡片逐张当作新卡片，136 张都推荐回了原来的 slice。
- Bake 使用引擎的工作区 bake 计划（与 `mindslice bake` 相同）：未勾选的卡片推迟，留在 overlay 中，它们本来就是生效的记忆。计划在执行时会再校验一次，期间工作区有变化就停止，不写任何东西。

所有引擎调用都在 `mindslice_tui/store.py` 里。其中 `ws.index` 和 `ws._reading()` 是引擎的内部接口，
引擎提供公开的图查询 API 后只需改这一个文件。

## 开发

```sh
git clone https://github.com/pancerZH/MindSlice-tui.git && cd MindSlice-tui
uv sync
uv run mindslice-tui -w ~/mindslice
uv run python -m unittest discover -s tests -t .
```
