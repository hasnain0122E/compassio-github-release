"""Auditable, meaning-preserving text cleaning (specification: docs/data/research_cleaning_spec.md).

Each step is recorded only if it changed the text, so every cleaned value can be traced
back to its source. No step truncates, rewrites, translates, lower-cases or summarises text.
"""

import html
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser

# Explicit missing-value sentinels (compared case-insensitively after stripping).
SENTINELS = frozenset({"", "nan", "null", "none", "n/a", "na", "-"})

_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^<>]*)?/?>")
_ENTITY = re.compile(r"&(?:[a-zA-Z]{2,8}|#\d{1,6}|#x[0-9a-fA-F]{1,6});")
_ZERO_WIDTH = re.compile("[" + "".join(map(chr, (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF))) + "]")
# NBSP, figure space, narrow NBSP, tab, CR, LF, vertical tab, form feed
_SPACE_LIKE = re.compile(
    "[" + "".join(map(chr, (0x00A0, 0x2007, 0x202F, 0x09, 0x0D, 0x0A, 0x0B, 0x0C))) + "]"
)
_MULTI_SPACE = re.compile(r" {2,}")
_BLOCK_TAGS = frozenset(
    {
        "p",
        "br",
        "div",
        "li",
        "ul",
        "ol",
        "tr",
        "td",
        "th",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "table",
    }
)
_SKIP_TAGS = frozenset({"script", "style"})

STEP_SENTINEL = "sentinel_to_null"
STEP_NFC = "unicode_nfc"
STEP_HTML = "html_markup_removed"
STEP_ENTITIES = "html_entities_unescaped"
STEP_ZERO_WIDTH = "zero_width_removed"
STEP_WHITESPACE = "whitespace_normalized"
ALL_STEPS = (STEP_SENTINEL, STEP_NFC, STEP_HTML, STEP_ENTITIES, STEP_ZERO_WIDTH, STEP_WHITESPACE)


@dataclass(frozen=True, slots=True)
class CleanedText:
    value: str | None
    steps: tuple[str, ...]


class _TextExtractor(HTMLParser):
    """Collects text nodes only. Never fetches, executes or resolves anything."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def strip_html(text: str) -> str:
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    return "".join(parser.parts)


def clean_text(raw: str | None) -> CleanedText:
    """Apply the documented cleaning steps in a fixed order."""
    if raw is None or raw.strip().lower() in SENTINELS:
        return CleanedText(None, (STEP_SENTINEL,) if raw is not None else ())
    steps: list[str] = []
    text = raw

    def apply(step: str, new: str) -> None:
        nonlocal text
        if new != text:
            steps.append(step)
            text = new

    apply(STEP_NFC, unicodedata.normalize("NFC", text))
    if _TAG.search(text):
        apply(STEP_HTML, strip_html(text))
    elif _ENTITY.search(text):
        apply(STEP_ENTITIES, html.unescape(text))
    apply(STEP_ZERO_WIDTH, _ZERO_WIDTH.sub("", text))
    apply(STEP_WHITESPACE, _MULTI_SPACE.sub(" ", _SPACE_LIKE.sub(" ", text)).strip())
    if text.strip().lower() in SENTINELS:
        return CleanedText(None, (*steps, STEP_SENTINEL))
    return CleanedText(text, tuple(steps))


def word_count(text: str | None) -> int:
    return len(text.split()) if text else 0
