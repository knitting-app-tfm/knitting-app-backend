import re
from io import BytesIO
from pathlib import Path

from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LTChar, LTTextBox, LTTextLine

from app.core.config import settings
from app.models.pattern import Pattern, PatternSource
from app.schemas.pattern import TextSegment

_UNIT_KEYWORDS: frozenset[str] = frozenset(
    {
        "stitches",
        "stitch",
        "sts",
        "st",
        "rows",
        "row",
        "rounds",
        "round",
        "mm",
        "cm",
        "g",
        "oz",
        "in",
        "inch",
    }
)

_UNIT_KEYWORD_RE = re.compile(
    r"^("
    + "|".join(sorted(_UNIT_KEYWORDS, key=len, reverse=True))
    + r")(?:[^a-zA-Z]|$)",
    re.IGNORECASE,
)


def _join_split_groups(segments: list[TextSegment]) -> list[TextSegment]:
    """Merge lines where a parenthesised size group was split by a PDF line break.

    Three conditions trigger a merge with the next line:
    - The current line has an unmatched '(' (e.g. "68 (74, 76,")
    - The current line ends with a digit and the next line starts with '(' followed
      by a digit (e.g. "CO 10" / "(10, 14, ...)"), but NOT labels like "(RS)".
    - The current line ends with ')' and the next line starts with a unit keyword
      (e.g. "Cast on 88 (98, 105)" / "stitches for back...").
    """
    result: list[TextSegment] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        text = seg.text.rstrip("\n")
        while i + 1 < len(segments):
            stripped = text.rstrip()
            next_text = segments[i + 1].text.rstrip("\n")
            unmatched_open = stripped.count("(") > stripped.count(")")
            trailing_digit = stripped and stripped[-1].isdigit()
            next_starts_size = bool(re.match(r"\s*\(\s*\d", next_text))
            ends_with_close = stripped.endswith(")")
            next_starts_unit = bool(_UNIT_KEYWORD_RE.match(next_text.lstrip()))
            if (
                unmatched_open
                or (trailing_digit and next_starts_size)
                or (ends_with_close and next_starts_unit)
            ):
                text = stripped + " " + next_text.lstrip()
                i += 1
            else:
                break
        result.append(
            TextSegment(
                text=text, bold=seg.bold, italic=seg.italic, font_size=seg.font_size
            )
        )
        i += 1
    return result


def read_source_text(pattern: Pattern) -> list[TextSegment]:
    """Read the original pattern file and return one TextSegment per line with formatting."""
    path = Path(settings.STORAGE_BASE_PATH) / pattern.original_file_path.removeprefix(
        "storage/"
    )
    if pattern.source == PatternSource.PDF:
        segments = extract_segments_from_pdf(path)
    else:
        segments = [
            TextSegment(text=line, bold=False, italic=False, font_size=None)
            for line in path.read_text(encoding="utf-8").split("\n")
        ]
    return _join_split_groups(segments)


def extract_segments_from_pdf(path: Path) -> list[TextSegment]:
    """Extract text and per-line formatting from a PDF using pdfminer layout analysis."""
    segments: list[TextSegment] = []
    for page_layout in extract_pages(path):
        for element in page_layout:
            if isinstance(element, LTTextBox):
                for line in element:
                    if isinstance(line, LTTextLine):
                        first_char = next(
                            (c for c in line if isinstance(c, LTChar)), None
                        )
                        if first_char:
                            fontname = first_char.fontname
                            font_size = first_char.size
                            bold = "Bold" in fontname or "bold" in fontname
                            italic = (
                                "Italic" in fontname
                                or "italic" in fontname
                                or "Oblique" in fontname
                            )
                        else:
                            bold, italic, font_size = False, False, None
                        text = line.get_text()
                        segments.append(
                            TextSegment(
                                text=text,
                                bold=bold,
                                italic=italic,
                                font_size=font_size,
                            )
                        )
    return segments


def extract_text_from_pdf(content: bytes) -> str:
    return extract_text(BytesIO(content))
