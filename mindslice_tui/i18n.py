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
    "pending_card": ("● Staged change: {change} · press a to review", "● 待审变更：{change} · 按 a 审批"),
    "change_create": ("new card", "新卡片"),
    "change_modify": ("modify", "修改"),
    "change_delete": ("delete", "删除"),
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
    # review of staged changes and bake: checklists that change memory once confirmed
    "review": ("Review", "审批"),
    "bake": ("Bake", "Bake"),
    "col_mark": ("✓", "✓"),
    "col_destination": ("destination", "目标切片"),
    "review_title": ("Review staged changes · {count}", "审批待审变更 · {count}"),
    "review_hint": ("space accept · x reject · a apply · esc close", "space 接受 · x 拒绝 · a 执行 · esc 关闭"),
    "review_summary": ("accept {accept} · reject {reject} · leave pending {leave}",
                       "接受 {accept} · 拒绝 {reject} · 保持待审 {leave}"),
    "review_approval": ("needs approval: {why}", "需要批准：{why}"),
    "review_affected_backlinks": ("cards linking here ({count}): {cards}", "链接到这里的卡片（{count}）：{cards}"),
    "review_affected_extensions": ("cards extending this ({count}): {cards}", "扩展它的卡片（{count}）：{cards}"),
    "review_conflict_refused": ("This change conflicts with the live card: reject it or leave it pending",
                                "该变更与当前卡片冲突：只能拒绝或保持待审"),
    "review_nothing": ("Mark changes with space or x first", "请先用 space 或 x 标记变更"),
    "review_confirm": ("Accept {accept} and reject {reject} staged change(s)? {leave} stay pending.",
                       "接受 {accept} 条、拒绝 {reject} 条待审变更？{leave} 条保持待审。"),
    "review_done": ("Accepted {applied}, rejected {discarded}", "已接受 {applied} 条，已拒绝 {discarded} 条"),
    "bake_title": ("Bake overlay cards into slices · {count}", "把 overlay 卡片 bake 进切片 · {count}"),
    "bake_hint": ("space choose · d destination · b bake · esc close", "space 勾选 · d 目标切片 · b 执行 · esc 关闭"),
    "bake_related": ("related slices: {slices}", "相关切片：{slices}"),
    "bake_empty": ("The overlay has no cards to bake", "overlay 中没有可 bake 的卡片"),
    "bake_slice": ("{alias}  {action} v{version} · {count} card(s) → {path}",
                   "{alias}  {action} v{version} · {count} 张卡片 → {path}"),
    "bake_create": ("new slice", "新切片"),
    "bake_update": ("new version", "新版本"),
    "bake_none_chosen": ("Nothing chosen: every card stays in overlay", "尚未勾选：所有卡片留在 overlay"),
    "bake_retained": ("also stays in overlay: {address} ({reason})", "同时留在 overlay：{address}（{reason}）"),
    "bake_nothing": ("Choose cards with space first", "请先用 space 勾选卡片"),
    "bake_not_ready": ("Resolve the blocked items first, or leave those cards out",
                       "请先解决受阻项，或不勾选相关卡片"),
    "bake_confirm": ("Bake {count} card(s) into {slices}? Their overlay copies are removed; earlier slice "
                     "versions stay on disk.",
                     "把 {count} 张卡片 bake 进 {slices}？它们在 overlay 中的副本会移除，旧版本切片目录保留。"),
    "bake_done": ("Baked {slices}", "已 bake：{slices}"),
    "destination_title": ("Destination of {card}", "{card} 的目标切片"),
    "destination_placeholder": ("or type a new @alias; enter confirms", "或输入新的 @alias，回车确认"),
    "destination_hint": ("↑↓ choose · enter confirm · tab new alias · esc cancel",
                         "↑↓ 选择 · enter 确认 · tab 输入新 alias · esc 取消"),
    "evidence_path": ("{count} shared folder(s)", "共享 {count} 层目录"),
    "evidence_links": ("{count} link(s)", "{count} 条链接"),
    "evidence_search": ("similar cards", "有相似卡片"),
    # why a destination was suggested
    "why_related": ("related", "相关"),
    "why_path": ("same folder", "同目录"),
    "why_links": ("linked", "有链接"),
    "why_search": ("similar", "内容相似"),
    "blocked": ("blocked: {where}: {detail}", "受阻：{where}：{detail}"),
    "skipped": ("{address} skipped: {reason}", "{address} 被跳过：{reason}"),
    "stale": ("The workspace changed meanwhile; the list was reloaded, check it again",
              "工作区已有变化，列表已重新加载，请再确认一遍"),
    "failed": ("Not done", "未执行"),
    "done": ("Done", "完成"),
    "confirm": ("Confirm", "确认"),
    "confirm_hint": ("enter confirm · esc cancel", "enter 确认 · esc 取消"),
}


def t(key: str, **values) -> str:
    return STRINGS[key][LANGUAGES.index(language)].format(**values)


def use(code: str) -> None:
    global language
    language = code


def switch() -> None:
    """Move to the next language, wrapping around."""
    use(LANGUAGES[(LANGUAGES.index(language) + 1) % len(LANGUAGES)])
