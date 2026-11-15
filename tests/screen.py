"""Test helper: the visible screen of a running app as plain text."""

import html
import re

_TEXT = re.compile(r'<text[^>]*\bx="([\d.]+)"[^>]*\by="([\d.]+)"[^>]*>(.*?)</text>')


def screen_text(app) -> str:
    rows: dict[float, list[tuple[float, str]]] = {}
    for x, y, text in _TEXT.findall(app.export_screenshot()):
        rows.setdefault(float(y), []).append((float(x), html.unescape(text).replace("\xa0", " ")))
    return "\n".join("".join(text for _, text in sorted(parts)).rstrip() for _, parts in sorted(rows.items()))
