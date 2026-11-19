"""Mixkit sound-effect category page parser (shared, canonical copy).

Mixkit 没有公开 API；检索靠解析分类页 HTML。这段正则是最脆弱的环节——
Mixkit 一旦改版就会失效。`sound` 与 `script-to-sfx-automator` 各存一份
相同文件，并有 parity 测试比对，避免只修一处。

改这个文件时，同步更新另一处：
  sound repo: scripts/mixkit_parse.py

只做纯解析，不发网络请求。
"""

from __future__ import annotations

import html
import re

ASSET_ROOT = "https://assets.mixkit.co/active_storage/sfx"

_BLOCK_SPLIT = re.compile(r'<div class="item-grid__item">')
_ID = re.compile(r'data-audio-player-item-id-value="(\d+)"')
_PREVIEW = re.compile(r'data-audio-player-preview-url-value="([^"]+)"')
_TITLE_SPECIFIC = re.compile(
    r'<h[23] class="item-grid-card__title">\s*(.*?)\s*</h[23]>', re.S
)
_TITLE_GENERIC = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.S)
_TAG_HREF = re.compile(r'href="/free-sound-effects/([^"/]+)/"')
_DURATION = re.compile(r"(\d+:\d+)")
_STRIP_TAGS = re.compile(r"<[^>]+>")


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_STRIP_TAGS.sub("", value))).strip()


def download_url(mixkit_id: str) -> str:
    return f"{ASSET_ROOT}/{mixkit_id}/{mixkit_id}.wav"


def parse_category_page(page_html: str, *, page_slug: str = "") -> list[dict]:
    """Return [{id, title, preview_url, download_url, duration, tags}].

    `preview_url` may be empty when the card exposes none; callers that need a
    playable preview must filter those rows themselves.
    """
    items: list[dict] = []
    for block in _BLOCK_SPLIT.split(page_html)[1:]:
        id_match = _ID.search(block)
        if not id_match:
            continue
        title_match = _TITLE_SPECIFIC.search(block) or _TITLE_GENERIC.search(block)
        if not title_match:
            continue
        preview_match = _PREVIEW.search(block)
        mixkit_id = id_match.group(1)
        duration_match = _DURATION.search(_text(block))
        tags = sorted({page_slug, *_TAG_HREF.findall(block)} - {""})
        items.append(
            {
                "id": mixkit_id,
                "title": _text(title_match.group(1)),
                "preview_url": html.unescape(preview_match.group(1)) if preview_match else "",
                "download_url": download_url(mixkit_id),
                "duration": duration_match.group(1) if duration_match else "",
                "tags": tags,
            }
        )
    return items
