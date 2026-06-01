from io import BytesIO
from pathlib import Path

from pdfminer.high_level import extract_text
from pdfminer.layout import LTChar, LTTextBox, LTTextLine
from pdfminer.high_level import extract_pages

from app.core.config import settings
from app.models.pattern import Pattern, PatternSource
from app.schemas.pattern import TextSegment


def read_source_text(pattern: Pattern) -> list[TextSegment]:
    """Read the original pattern file and return one TextSegment per line with formatting."""
    path = Path(settings.STORAGE_BASE_PATH) / pattern.original_file_path.removeprefix(
        "storage/"
    )
    if pattern.source == PatternSource.PDF:
        return extract_segments_from_pdf(path)
    return [
        TextSegment(text=line, bold=False, italic=False, font_size=None)
        for line in path.read_text(encoding="utf-8").split("\n")
    ]


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
