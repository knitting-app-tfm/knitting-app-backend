import re

from sqlalchemy.orm import Session

from app.repositories.abbreviation import abbreviation_repository
from app.schemas.pattern import TextSegment

# ---------------------------------------------------------------------------
# Tokenizer constants
# ---------------------------------------------------------------------------

# Size group: optional leading bare number, then one or more bracket groups
# (parentheses or square brackets with comma-separated values), each optionally
# followed by a bare number. Handles decimals throughout.
# Examples: "23 (24, 25, 27)", "35 (41) 47", "(4, 4, 4)[2, 2, 4]", "1.5 (1.5) 2 (2)"
_SIZE_GROUP_RE = re.compile(
    r"(?:\d+(?:\.\d+)?\s*)?"
    r"(?:(?:\([\d\s,.]+\)|\[[\d\s,.]+\])\s*(?:\d+(?:\.\d+)?\s*)?)+"
)

_SCALABLE_UNITS: frozenset[str] = frozenset(
    {
        "rounds",
        "round",
        "rows",
        "row",
        "stitches",
        "stitch",
        "sts",
        "st",
    }
)
_NON_SCALABLE_UNITS: frozenset[str] = frozenset(
    {
        "mm",
        "cm",
        "g",
        "oz",
        "in",
        "inch",
    }
)
_ALL_UNITS: frozenset[str] = _SCALABLE_UNITS | _NON_SCALABLE_UNITS

_NUMBER_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(''|\"|(?:stitch(?:es)?|rounds?|rows?|sts?|inch|in|mm|cm|oz|g)\b)",
    re.IGNORECASE,
)

_BARE_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]*")

_UNIT_PEEK_RE = re.compile(r"\s*([a-zA-Z][a-zA-Z0-9]*)")

# Matches " or '' (both mean inches) optionally preceded by whitespace.
_INCH_MARK_RE = re.compile(r'\s*(?:"|\'\')')

# Matches words like "k2", "p1", "K23" — letter prefix followed by trailing digits only.
_SUFFIXED_ABBR_RE = re.compile(r"^([a-zA-Z]+)\d+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_size_values(match_str: str) -> int:
    """Count the number of numeric values (integer or decimal) in a size group match."""
    return len(re.findall(r"\d+(?:\.\d+)?", match_str))


def _peek_unit(remaining: str) -> str | None:
    """Return the raw unit keyword from the next word in *remaining*, or None.

    Also detects " and '' as inch markers, returning '"' for both.
    """
    if _INCH_MARK_RE.match(remaining):
        return "inch"
    m = _UNIT_PEEK_RE.match(remaining)
    if m:
        word = m.group(1)
        if word.lower() in _ALL_UNITS:
            return word
    return None


def find_full_name_matches(
    line: str, known_full_names: dict[str, str]
) -> dict[int, tuple[int, str, str]]:
    """Greedy left-to-right scan for full-name matches in *line*.

    At each position, tries all known full names longest-first. A match is
    accepted only when it sits at a word boundary. Returns {start: (end, fn_key, code)}.
    """
    if not known_full_names:
        return {}
    result: dict[int, tuple[int, str, str]] = {}
    line_lower = line.lower()
    sorted_fns = sorted(known_full_names.keys(), key=len, reverse=True)
    pos = 0
    while pos < len(line_lower):
        for fn in sorted_fns:
            end = pos + len(fn)
            if line_lower.startswith(fn, pos):
                before_ok = pos == 0 or not line_lower[pos - 1].isalnum()
                after_ok = end >= len(line_lower) or not line_lower[end].isalnum()
                if before_ok and after_ok:
                    result[pos] = (end, fn, known_full_names[fn])
                    pos = end
                    break
        else:
            pos += 1
    return result


def tokenize_line(
    line: str,
    known_codes: set[str],
    known_full_names: dict[str, str],
    num_sizes: int = 0,
) -> list[dict]:
    """Tokenize a single line into a flat list of token dicts.

    Processing priority:
      0. Full-name match (pre-computed) — matched before any other rule.
      1. size_group — contains at least one bracketed group; validated against
         num_sizes when num_sizes > 0.
      2. number + unit (number-before-unit).
      3. bare number.
      4. word:
         a. Unit keyword + adjacent bare number → number token (unit-before-number).
         b. Exact match in known_codes → abbreviation token.
         c. Suffixed word (e.g. "K23"): look ahead — if the digit suffix + what
            follows forms a valid size group (value count == num_sizes when
            num_sizes > 0), split into abbreviation for the alpha prefix only and
            let the size group proceed. Otherwise emit the full word with quantity.
         d. Plain text.
    """
    full_name_at = find_full_name_matches(line, known_full_names)

    tokens: list[dict] = []
    text_buf = ""
    pos = 0

    def flush_text() -> None:
        nonlocal text_buf
        stripped = text_buf.strip()
        if stripped:
            tokens.append({"type": "text", "value": stripped})
        text_buf = ""

    while pos < len(line):
        # 0. Full-name match pre-empts all other rules
        if pos in full_name_at:
            flush_text()
            end, fn, code = full_name_at[pos]
            tokens.append(
                {
                    "type": "abbreviation",
                    "code": code,
                    "translated": False,
                    "full_name": None,
                    "quantity": None,
                }
            )
            pos = end
            continue

        if line[pos].isspace():
            text_buf += line[pos]
            pos += 1
            continue

        # 1. Size group
        m = _SIZE_GROUP_RE.match(line, pos)
        if m:
            raw_values = re.findall(r"\d+(?:\.\d+)?", m.group())
            value_count = len(raw_values)
            starts_bare = m.group()[0].isdigit()
            if (
                num_sizes == 0
                or value_count == num_sizes
                or (starts_bare and value_count == num_sizes + 1)
            ):
                flush_text()
                values = [float(v) if "." in v else int(v) for v in raw_values]
                unit = _peek_unit(line[m.end() :])
                tokens.append(
                    {
                        "type": "size_group",
                        "values": values,
                        "unit": unit,
                        "scalable": True,
                    }
                )
                pos = m.end()
                if unit == "inch":
                    # consume the inch mark so it isn't treated as stray punctuation
                    j = pos
                    while j < len(line) and line[j].isspace():
                        j += 1
                    if j < len(line) and line[j] == '"':
                        pos = j + 1
                    elif j + 1 < len(line) and line[j : j + 2] == "''":
                        pos = j + 2
                continue

        # 2. Number followed by unit keyword
        m = _NUMBER_UNIT_RE.match(line, pos)
        if m:
            flush_text()
            raw = float(m.group(1))
            value: int | float = int(raw) if raw.is_integer() else raw
            unit_str = "inch" if m.group(2) in ('"', "''") else m.group(2)
            tokens.append(
                {
                    "type": "number",
                    "value": value,
                    "unit": unit_str,
                    "scalable": unit_str.lower() in _SCALABLE_UNITS,
                }
            )
            pos = m.end()
            continue

        # 3. Bare number (no unit)
        m = _BARE_NUMBER_RE.match(line, pos)
        if m:
            flush_text()
            raw = float(m.group())
            value = int(raw) if raw.is_integer() else raw
            tokens.append(
                {"type": "number", "value": value, "unit": None, "scalable": False}
            )
            pos = m.end()
            continue

        # 4. Word (letter-starting)
        m = _WORD_RE.match(line, pos)
        if m:
            word = m.group()
            word_lower = word.lower()

            # 4a. Unit keyword followed by a bare number (unit-before-number)
            if word_lower in _ALL_UNITS:
                after_word = pos + len(word)
                while after_word < len(line) and line[after_word].isspace():
                    after_word += 1
                num_m = _BARE_NUMBER_RE.match(line, after_word)
                if num_m:
                    flush_text()
                    raw = float(num_m.group())
                    value = int(raw) if raw.is_integer() else raw
                    tokens.append(
                        {
                            "type": "number",
                            "value": value,
                            "unit": word,
                            "scalable": word_lower in _SCALABLE_UNITS,
                        }
                    )
                    pos = num_m.end()
                    continue

            # 4b. Exact match in known_codes → abbreviation
            if word_lower in known_codes:
                flush_text()
                tokens.append(
                    {
                        "type": "abbreviation",
                        "code": word,
                        "translated": False,
                        "full_name": None,
                        "quantity": None,
                    }
                )
                pos = m.end()
                continue

            # 4c. Suffixed word (e.g. "K23") — alpha prefix in known_codes
            sm = _SUFFIXED_ABBR_RE.match(word)
            if sm and sm.group(1).lower() in known_codes:
                prefix = sm.group(1)
                digits = word[len(prefix) :]
                digits_pos = pos + len(prefix)

                # Look ahead: does the digit suffix + following text form a valid size group?
                sg_m = _SIZE_GROUP_RE.match(line, digits_pos)
                if sg_m and num_sizes > 0:
                    sg_count = _count_size_values(sg_m.group())
                    sg_starts_bare = sg_m.group()[0].isdigit()
                    split_ok = sg_count == num_sizes or (
                        sg_starts_bare and sg_count == num_sizes + 1
                    )
                else:
                    split_ok = False
                if sg_m and num_sizes > 0 and split_ok:
                    # Split: emit abbreviation for alpha prefix only;
                    # the digits+brackets will be matched as a size group next iteration.
                    flush_text()
                    tokens.append(
                        {
                            "type": "abbreviation",
                            "code": prefix,
                            "translated": False,
                            "full_name": None,
                            "quantity": None,
                        }
                    )
                    pos = digits_pos
                else:
                    # Full suffixed word as abbreviation with quantity
                    flush_text()
                    quantity = int(digits)
                    tokens.append(
                        {
                            "type": "abbreviation",
                            "code": word,
                            "translated": False,
                            "full_name": None,
                            "quantity": quantity,
                        }
                    )
                    pos = m.end()
                continue

            # 4d. Plain text
            text_buf += word
            pos = m.end()
            continue

        text_buf += line[pos]  # preserve punctuation and unrecognised characters
        pos += 1

    flush_text()
    return tokens


def tokenize(
    segments: list[TextSegment],
    known_codes: set[str],
    known_full_names: dict[str, str],
    num_sizes: int = 0,
) -> list[dict]:
    """Tokenize each TextSegment independently and propagate formatting to the line dict.

    Empty segments are preserved with an empty token list to maintain visual structure.
    """
    result = []
    for i, segment in enumerate(segments, start=1):
        fmt = {
            "bold": segment.bold,
            "italic": segment.italic,
            "font_size": segment.font_size,
        }
        if not segment.text.strip():
            result.append({"line": i, **fmt, "tokens": []})
        else:
            toks = tokenize_line(segment.text, known_codes, known_full_names, num_sizes)
            result.append({"line": i, **fmt, "tokens": toks})
    return result


def enrich_abbreviations(lines: list[dict], db: Session) -> list[dict]:
    """Look up each abbreviation token in the DB and set translated/full_name in-place.

    For suffixed codes like "k2" that have no direct DB entry, falls back to the
    alpha prefix. When a quantity is present, appends it to full_name.
    """
    for line in lines:
        for token in line.get("tokens", []):
            if token["type"] == "abbreviation":
                code = token["code"]
                abbr = abbreviation_repository.get_by_code(db, code)
                if abbr is None:
                    sm = _SUFFIXED_ABBR_RE.match(code)
                    if sm:
                        abbr = abbreviation_repository.get_by_code(db, sm.group(1))
                token["translated"] = abbr is not None
                if abbr:
                    qty = token.get("quantity")
                    if qty is not None and abbr.full_name:
                        token["full_name"] = f"{abbr.full_name} {qty}"
                    else:
                        token["full_name"] = abbr.full_name
                else:
                    token["full_name"] = None
    return lines
