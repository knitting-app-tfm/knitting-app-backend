import json
import re
import uuid
from io import BytesIO
from pathlib import Path

from groq import Groq
from pdfminer.high_level import extract_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pattern import (
    CraftType,
    GaugeUnit,
    Pattern,
    PatternSource,
    PatternStatus,
    YarnWeight,
)
from app.repositories.abbreviation import abbreviation_repository
from app.repositories.pattern import pattern_repository

# ---------------------------------------------------------------------------
# Tokenizer constants
# ---------------------------------------------------------------------------

# Size group: one or more numbers where at least one is in parentheses,
# e.g. "147 (159) 174 (192)" or "10 (12) 14"
_SIZE_GROUP_RE = re.compile(r"\d+\s*(?:\(\d+\))+(?:\s+\d+(?:\s*\(\d+\))*)*")

# Closed unit lists — the raw keyword is stored in the token (no canonicalization).
# A number token is produced only when a unit keyword appears immediately before
# or after a number; a unit keyword that has no adjacent number is not consumed.
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

# Number immediately followed (optionally with spaces) by a unit keyword.
# Alternatives are ordered longest-first to prevent partial matches
# (e.g. "stitches?" before "sts?", "inch" before "in").
_NUMBER_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(stitch(?:es)?|rounds?|rows?|sts?|inch|in|mm|cm|oz|g)\b",
    re.IGNORECASE,
)

# Bare integer or decimal number with no unit
_BARE_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# Letter-starting word, may contain digits (covers abbreviations like k2, p1)
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9]*")

# Used to peek at the next word after a size group to infer its unit
_UNIT_PEEK_RE = re.compile(r"\s*([a-zA-Z][a-zA-Z0-9]*)")


class InvalidFileTypeError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


class EmptyTextError(ValueError):
    pass


class EmptyTitleError(ValueError):
    pass


class PatternNotConfirmedError(ValueError):
    pass


_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_LLM_PROMPT = """You are a knitting and crochet pattern parser.
Extract metadata from the pattern text below and return ONLY a JSON object with this exact structure (use null for unknown fields):

{
  "title": "string",
  "craft": "KNITTING" | "CROCHET" | null,
  "sizes": ["string", ...] | null,
  "gauge_stitches": number | null,
  "gauge_rows": number | null,
  "gauge_size": number | null,
  "gauge_unit": "CM" | "INCH" | null,
  "needle_size": "string" | null,
  "yarns": [
    {
      "label": "string" | null,
      "yarn_weight": "LACE" | "FINGERING" | "DK" | "ARAN" | "BULKY" | null,
      "meters_per_unit": number | null,
      "grams_per_unit": number | null,
      "grams_needed": number | null,
      "strands": integer
    }
  ]
}

Pattern text:
"""


class PatternService:
    def __init__(self) -> None:
        self._client = Groq(api_key=settings.GROQ_API_KEY)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def import_from_pdf(
        self, db: Session, content: bytes, content_type: str | None
    ) -> Pattern:
        self._validate_pdf(content, content_type)
        file_uuid = str(uuid.uuid4())
        original_path = self._save_file(content, "original", file_uuid, ".pdf")
        text = self._extract_text(content)
        _, json_str = self._get_parsed(text)
        parsed_path = self._save_file(json_str, "parsed", file_uuid, ".json")
        return self._persist_pattern(db, original_path, parsed_path, PatternSource.PDF)

    def get_by_id(self, db: Session, pattern_id: uuid.UUID) -> Pattern | None:
        return pattern_repository.get_by_id(db, pattern_id)

    def get_prefill(self, db: Session, pattern_id: uuid.UUID) -> dict | None:
        pattern = self.get_by_id(db, pattern_id)
        if pattern is None:
            return None

        base: dict = {
            "id": pattern.id,
            "user_id": pattern.user_id,
            "status": pattern.status,
            "source": pattern.source,
            "original_file_path": pattern.original_file_path,
            "parsed_json_path": pattern.parsed_json_path,
            "cover_image_path": pattern.cover_image_path,
            "created_at": pattern.created_at,
            "updated_at": pattern.updated_at,
        }

        if pattern.status == PatternStatus.IMPORTED and pattern.parsed_json_path:
            parsed = self._read_parsed_json(pattern.parsed_json_path)
            base.update(
                {
                    "title": parsed.get("title"),
                    "craft": parsed.get("craft"),
                    "gauge_stitches": parsed.get("gauge_stitches"),
                    "gauge_rows": parsed.get("gauge_rows"),
                    "gauge_size": parsed.get("gauge_size"),
                    "gauge_unit": parsed.get("gauge_unit"),
                    "needle_size": parsed.get("needle_size"),
                    "sizes": parsed.get("sizes") or [],
                    "yarns": parsed.get("yarns") or [],
                }
            )
        else:
            base.update(
                {
                    "title": pattern.title,
                    "craft": pattern.craft,
                    "gauge_stitches": pattern.gauge_stitches,
                    "gauge_rows": pattern.gauge_rows,
                    "gauge_size": pattern.gauge_size,
                    "gauge_unit": pattern.gauge_unit,
                    "needle_size": pattern.needle_size,
                    "sizes": pattern.sizes or [],
                    "yarns": [
                        {
                            "id": y.id,
                            "pattern_id": y.pattern_id,
                            "label": y.label,
                            "yarn_weight": y.yarn_weight,
                            "meters_per_unit": y.meters_per_unit,
                            "grams_per_unit": y.grams_per_unit,
                            "grams_needed": y.grams_needed,
                            "strands": y.strands,
                        }
                        for y in pattern.yarns
                    ],
                }
            )

        return base

    def confirm(
        self,
        db: Session,
        pattern: Pattern,
        title: str,
        craft: CraftType,
        gauge_stitches: float | None,
        gauge_rows: float | None,
        gauge_size: float | None,
        gauge_unit: GaugeUnit | None,
        needle_size: str | None,
        sizes: list[str],
        yarns_data: list[dict],
        cover_bytes: bytes | None,
        cover_suffix: str,
    ) -> Pattern:
        if not title or not title.strip():
            raise EmptyTitleError("Title cannot be empty")

        cover_image_path = pattern.cover_image_path
        if cover_bytes is not None:
            cover_image_path = self._save_file(
                cover_bytes, "covers", str(pattern.id), cover_suffix
            )

        return pattern_repository.update(
            db,
            pattern,
            yarns_data=self._normalize_yarns(yarns_data),
            title=title.strip(),
            craft=craft,
            gauge_stitches=gauge_stitches,
            gauge_rows=gauge_rows,
            gauge_size=gauge_size,
            gauge_unit=gauge_unit,
            needle_size=needle_size,
            sizes=sizes,
            cover_image_path=cover_image_path,
            status=PatternStatus.CONFIRMED,
        )

    def translate(self, db: Session, pattern_id: uuid.UUID) -> list[dict] | None:
        """Tokenize a pattern and translate its abbreviations.

        Returns None when the pattern does not exist.
        Raises PatternNotConfirmedError when status is IMPORTED.
        On CONFIRMED: tokenizes, saves to disk, advances status to TOKENIZED.
        On TOKENIZED: reuses the saved token file without re-tokenizing.
        In both cases, abbreviation tokens are enriched with DB data before returning.
        """
        pattern = pattern_repository.get_by_id(db, pattern_id)
        if pattern is None:
            return None

        if pattern.status == PatternStatus.IMPORTED:
            raise PatternNotConfirmedError(
                "Pattern must be confirmed before translating"
            )

        if pattern.status == PatternStatus.CONFIRMED:
            all_abbreviations = abbreviation_repository.get_all(db)
            known_codes = {abbr.abbreviation.lower() for abbr in all_abbreviations}
            text = self._read_source_text(pattern)
            lines = self._tokenize(text, known_codes)
            self._enrich_abbreviations(lines, db)
            tokens_path = self._save_file(
                json.dumps(lines, ensure_ascii=False),
                "tokens",
                str(pattern.id),
                ".json",
            )
            pattern_repository.set_tokenized(db, pattern, tokens_path)
        else:  # TOKENIZED
            lines = self._read_tokens_file(pattern.tokens_file_path)
            self._enrich_abbreviations(lines, db)

        return lines

    def import_from_text(self, db: Session, text: str) -> Pattern:
        if not text or not text.strip():
            raise EmptyTextError("Text cannot be empty")
        file_uuid = str(uuid.uuid4())
        original_path = self._save_file(text, "original", file_uuid, ".txt")
        _, json_str = self._get_parsed(text)
        parsed_path = self._save_file(json_str, "parsed", file_uuid, ".json")
        return self._persist_pattern(db, original_path, parsed_path, PatternSource.TEXT)

    # ------------------------------------------------------------------
    # Private helpers — translate
    # ------------------------------------------------------------------

    def _read_source_text(self, pattern: Pattern) -> str:
        """Read the original pattern text from storage (PDF or plain text)."""
        path = Path(
            settings.STORAGE_BASE_PATH
        ) / pattern.original_file_path.removeprefix("storage/")
        if pattern.source == PatternSource.PDF:
            return self._extract_text(path.read_bytes())
        return path.read_text(encoding="utf-8")

    def _tokenize(self, text: str, known_codes: set[str]) -> list[dict]:
        """Split text into lines and tokenize each line independently.

        Empty lines are preserved as LineTokens with an empty token list to
        maintain the visual structure of the pattern.
        """
        result = []
        for i, line in enumerate(text.split("\n"), start=1):
            if not line.strip():
                result.append({"line": i, "tokens": []})
            else:
                result.append(
                    {"line": i, "tokens": self._tokenize_line(line, known_codes)}
                )
        return result

    def _tokenize_line(self, line: str, known_codes: set[str]) -> list[dict]:
        """Tokenize a single line into a flat list of token dicts.

        Processing priority:
          1. size_group — digit-starting sequence that contains at least one
             parenthesised value; peeking at the next word assigns its unit.
          2. number + unit (number-before-unit) — unit keyword is consumed.
          3. bare number — digit-starting sequence with no adjacent unit.
          4. word:
             a. If the word is a unit keyword AND the next non-space token is a
                bare number, produce a number token (unit-before-number). The unit
                keyword is consumed; the number is consumed.
             b. Otherwise the word is an abbreviation (if in known_codes) or plain
                text. A unit keyword with no adjacent number is treated normally,
                never consumed as a unit.

        Consecutive plain-text words are accumulated and flushed as a single text
        token when a non-text token or end-of-line is encountered.
        Punctuation characters are silently dropped.
        """
        tokens: list[dict] = []
        text_words: list[str] = []
        pos = 0

        def flush_text() -> None:
            if text_words:
                tokens.append({"type": "text", "value": " ".join(text_words)})
                text_words.clear()

        while pos < len(line):
            if line[pos].isspace():
                pos += 1
                continue

            # 1. Size group
            m = _SIZE_GROUP_RE.match(line, pos)
            if m:
                flush_text()
                values = [int(n) for n in re.findall(r"\d+", m.group())]
                unit = self._peek_unit(line[m.end() :])
                tokens.append(
                    {
                        "type": "size_group",
                        "values": values,
                        "unit": unit,
                        "scalable": True,
                    }
                )
                pos = m.end()
                continue

            # 2. Number followed by unit keyword (unit is consumed)
            m = _NUMBER_UNIT_RE.match(line, pos)
            if m:
                flush_text()
                raw = float(m.group(1))
                value: int | float = int(raw) if raw.is_integer() else raw
                unit_str = m.group(2)
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

                # 4b. Abbreviation or plain text
                if word_lower in known_codes:
                    flush_text()
                    tokens.append(
                        {
                            "type": "abbreviation",
                            "code": word,
                            "translated": False,
                            "full_name": None,
                        }
                    )
                else:
                    text_words.append(word)
                pos = m.end()
                continue

            pos += 1  # skip punctuation and unrecognised characters

        flush_text()
        return tokens

    def _peek_unit(self, remaining: str) -> str | None:
        """Return the raw unit keyword from the next word in *remaining*, or None.

        Only returns a value when the next word is in _ALL_UNITS; the word is not
        consumed from the scan stream (the caller handles it as a separate token).
        """
        m = _UNIT_PEEK_RE.match(remaining)
        if m:
            word = m.group(1)
            if word.lower() in _ALL_UNITS:
                return word
        return None

    def _enrich_abbreviations(self, lines: list[dict], db: Session) -> list[dict]:
        """Look up each abbreviation token in the DB and set translated/full_name in-place."""
        for line in lines:
            for token in line.get("tokens", []):
                if token["type"] == "abbreviation":
                    abbr = abbreviation_repository.get_by_code(db, token["code"])
                    token["translated"] = abbr is not None
                    token["full_name"] = abbr.full_name if abbr else None
        return lines

    def _read_tokens_file(self, stored_path: str) -> list[dict]:
        """Load a token list from the JSON file previously saved to disk."""
        try:
            path = Path(settings.STORAGE_BASE_PATH) / stored_path.removeprefix(
                "storage/"
            )
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Private helpers — import / confirm
    # ------------------------------------------------------------------

    def _validate_pdf(self, content: bytes, content_type: str | None) -> None:
        if content_type != "application/pdf":
            raise InvalidFileTypeError("Only PDF files are allowed")
        if len(content) > _MAX_FILE_SIZE:
            raise FileTooLargeError("File size must not exceed 10MB")

    def _save_file(
        self, content: bytes | str, subdir: str, file_uuid: str, suffix: str
    ) -> str:
        path = Path(settings.STORAGE_BASE_PATH) / subdir / f"{file_uuid}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return f"storage/{subdir}/{file_uuid}{suffix}"

    def _extract_text(self, content: bytes) -> str:
        return extract_text(BytesIO(content))

    def _get_parsed(self, text: str) -> tuple[dict, str]:
        if settings.USE_MOCK_LLM:
            return self._mock_response()
        return self._call_llm(text)

    def _persist_pattern(
        self,
        db: Session,
        original_path: str,
        parsed_path: str,
        source: PatternSource,
    ) -> Pattern:
        return pattern_repository.create(
            db,
            yarns_data=[],
            source=source,
            status=PatternStatus.IMPORTED,
            original_file_path=original_path,
            parsed_json_path=parsed_path,
        )

    def _call_llm(self, text: str) -> tuple[dict, str]:
        try:
            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": _LLM_PROMPT + text}],
                response_format={"type": "json_object"},
            )
            json_str = response.choices[0].message.content
            if json_str is None:
                raise ValueError("Empty response from LLM")
            raw = json.loads(json_str)
            parsed = self._normalize(raw)
            return parsed, json.dumps(parsed, ensure_ascii=False)
        except Exception:
            # AC4: if LLM fails, return empty metadata — user fills in manually
            fallback = {"title": "Unknown", "craft": None, "yarns": []}
            return fallback, json.dumps(fallback)

    def _mock_response(self) -> tuple[dict, str]:
        mock = {
            "title": "Mock Knitting Pattern",
            "craft": "KNITTING",
            "sizes": ["S", "M", "L"],
            "gauge_stitches": 22.0,
            "gauge_rows": 30.0,
            "gauge_size": 10.0,
            "gauge_unit": "CM",
            "needle_size": "4mm",
            "yarns": [
                {
                    "label": "Main",
                    "yarn_weight": "DK",
                    "meters_per_unit": 200.0,
                    "grams_per_unit": 100.0,
                    "grams_needed": 300.0,
                    "strands": 1,
                }
            ],
        }
        json_str = json.dumps(mock, ensure_ascii=False)
        parsed = self._normalize(mock)
        return parsed, json_str

    def _read_parsed_json(self, stored_path: str) -> dict:
        try:
            path = Path(settings.STORAGE_BASE_PATH) / stored_path.removeprefix(
                "storage/"
            )
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _normalize_yarns(self, yarns: list[dict]) -> list[dict]:
        result = []
        for yarn in yarns:
            n = dict(yarn)
            try:
                n["yarn_weight"] = YarnWeight(n.get("yarn_weight"))
            except (ValueError, KeyError, TypeError):
                n["yarn_weight"] = None
            n.setdefault("strands", 1)
            result.append(n)
        return result

    def _normalize(self, raw: dict) -> dict:
        try:
            raw["craft"] = CraftType(raw.get("craft"))
        except (ValueError, KeyError):
            raw["craft"] = None

        try:
            raw["gauge_unit"] = GaugeUnit(raw.get("gauge_unit"))
        except (ValueError, KeyError):
            raw["gauge_unit"] = None

        for yarn in raw.get("yarns", []):
            try:
                yarn["yarn_weight"] = YarnWeight(yarn.get("yarn_weight"))
            except (ValueError, KeyError):
                yarn["yarn_weight"] = None
            yarn.setdefault("strands", 1)

        return raw


pattern_service = PatternService()
