"""The UI's own text in each language. Textual has no built-in localisation, so this is a plain table.

``t("search")`` returns the string in the current language; ``{name}`` placeholders are filled from
keyword arguments. Card content and the engine's own messages are shown as they are.
To add a language: add its code to ``LANGUAGES`` and one more string to every entry.
"""

from __future__ import annotations

LANGUAGES = ("en", "zh")
language = LANGUAGES[0]

STRINGS = {
    # key hints in the footer (the key is the action's name)
    "search": ("Search", "搜索"),
    "neighbors": ("Neighbours", "邻居树"),
    "overview": ("Overview", "概览"),
    "history": ("History", "历史"),
    "refresh": ("Reload", "刷新"),
    "back": ("Back", "回退"),
    "language": ("中文", "English"),  # names the language the key switches to
    "quit": ("Quit", "退出"),
    # panes
    "slices": ("Slices", "切片"),
    "card": ("Card", "卡片"),
    "relations": ("Relations", "关系"),
    # relation groups; the symbols are ones common terminal fonts have (rarer arrows render as boxes)
    "links_out": ("→ links out", "→ 出链"),
    "backlinks": ("← backlinks", "← 反链"),
    "extends": ("↑ extends", "↑ 扩展"),
    "extended_by": ("↓ extended by", "↓ 被扩展"),
    "supersedes": ("⇒ supersedes", "⇒ 取代"),
    "superseded_by": ("⇐ superseded by", "⇐ 被取代"),
    "same_path": ("≡ same path", "≡ 同路径"),
    "dangling": ("✗ dangling", "✗ 悬空引用"),
    # card header
    "always_loaded": ("always loaded", "常驻"),
    "superseded": ("superseded", "已被取代"),
    "shadowed": ("shadowed", "被遮盖"),
    "tags": ("tags: {tags}", "标签：{tags}"),
    "aliases": ("aliases: {aliases}", "别名：{aliases}"),
    "modified": ("modified {time} · read {count}×", "修改于 {time} · 已读 {count} 次"),
    "file_gone": ("*The file is gone; press `r` to reload.*", "*文件已不存在，按 `r` 刷新。*"),
    # notifications
    "refreshed": ("Reloaded", "已刷新"),
    "card_count": ("{count} cards", "{count} 张卡片"),
    "refresh_failed": ("Reload failed; still showing the old content", "刷新失败，仍显示旧内容"),
    # search
    "search_placeholder": ("Type to search; enter moves to the results", "输入关键词，回车进入结果列表"),
    "search_found": ("{count} found", "找到 {count} 条"),
    "search_unmatched": ("no card contains: {terms}", "没有卡片包含：{terms}"),
    # neighbour tree
    "neighbor_hint": ("space open · enter jump · esc close", "space 展开 · enter 跳转 · esc 关闭"),
    # table columns
    "col_time": ("time", "时间"),
    "col_change": ("change", "变更"),
    "col_card": ("card", "卡片"),
    "col_reason": ("reason", "原因"),
    "col_kind": ("kind", "类型"),
    "col_detail": ("detail", "详情"),
    "col_title": ("title", "标题"),
    "col_summary": ("summary", "摘要"),
    # overview
    "tab_status": ("Status", "状态"),
    "tab_issues": ("Issues", "问题"),
    "tab_always": ("Always loaded", "常驻"),
    "mounts": ("Mounts", "挂载"),
    "mount_row": ("{alias:<16} {count:>5} cards  precedence {precedence:<4} {role:<10} {path}",
                  "{alias:<16} {count:>5} 张卡片  优先级 {precedence:<4} {role:<10} {path}"),
    "mount_missing": ("missing", "目录缺失"),
    "mount_dirty": ("unbaked changes", "有未 bake 的改动"),
    "memory": ("Memory", "记忆"),
    "memory_row": ("overlay cards {overlay} · mounted cards {mounted} · not assigned to a slice {unassigned}",
                   "overlay 卡片 {overlay} · 挂载卡片 {mounted} · 未归入 slice {unassigned}"),
    "validation_row": ("validation: {errors} errors, {warnings} warnings", "校验：{errors} 个错误，{warnings} 个警告"),
    "pending": ("Pending review ({count})", "待审变更（{count}）"),
    "pending_none": ("nothing is waiting for approval", "没有等待批准的变更"),
    "pending_conflict": ("conflict: {conflict}", "冲突：{conflict}"),
    "pending_reason": ("reason: {reason}", "原因：{reason}"),
    # issues: the kind, and for the ones derived from the graph a detail naming the other card
    "issue_error": ("error", "错误"),
    "issue_warning": ("warning", "警告"),
    "issue_stale_extends": ("stale extends", "扩展已过期"),
    "issue_stale_extends_detail": ("baseline {target} has been superseded", "基线 {target} 已被取代"),
    "issue_supersedes": ("supersedes", "取代"),
    "issue_supersedes_detail": ("replaces {target}", "取代了 {target}"),
    "issue_shadowed": ("shadowed", "被遮盖"),
    "issue_shadowed_detail": ("a higher-precedence mount has the same path", "更高优先级的挂载中有同路径卡片"),
    "issue_orphan": ("orphan", "孤立"),
    "issue_orphan_detail": ("no links in or out", "没有出链也没有反链"),
}


def t(key: str, **values) -> str:
    return STRINGS[key][LANGUAGES.index(language)].format(**values)


def use(code: str) -> None:
    global language
    language = code


def switch() -> None:
    """Move to the next language, wrapping around."""
    use(LANGUAGES[(LANGUAGES.index(language) + 1) % len(LANGUAGES)])
