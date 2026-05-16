import json
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
    PatternSource,
    PatternStatus,
    YarnWeight,
)
from app.models.pattern import Pattern
from app.repositories.pattern import pattern_repository


class InvalidFileTypeError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


class EmptyTextError(ValueError):
    pass


_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_LLM_PROMPT = """You are a knitting and crochet pattern parser.
Extract metadata from the pattern text below and return ONLY a JSON object with this exact structure (use null for unknown fields):

{
  "title": "string",
  "craft": "KNITTING" | "CROCHET" | null,
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
        parsed, json_str = self._get_parsed(text)
        parsed_path = self._save_file(json_str, "parsed", file_uuid, ".json")
        return self._persist_pattern(
            db, parsed, original_path, parsed_path, PatternSource.PDF
        )

    def import_from_text(self, db: Session, text: str) -> Pattern:
        if not text or not text.strip():
            raise EmptyTextError("Text cannot be empty")
        file_uuid = str(uuid.uuid4())
        original_path = self._save_file(text, "original", file_uuid, ".txt")
        parsed, json_str = self._get_parsed(text)
        parsed_path = self._save_file(json_str, "parsed", file_uuid, ".json")
        return self._persist_pattern(
            db, parsed, original_path, parsed_path, PatternSource.TEXT
        )

    # ------------------------------------------------------------------
    # Private helpers
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
        parsed: dict,
        original_path: str,
        parsed_path: str,
        source: PatternSource,
    ) -> Pattern:
        yarns_data = parsed.pop("yarns", [])
        return pattern_repository.create(
            db,
            yarns_data=yarns_data,
            source=source,
            status=PatternStatus.IMPORTED,
            original_file_path=original_path,
            parsed_json_path=parsed_path,
            title=parsed.get("title") or "Unknown",
            craft=parsed.get("craft"),
            gauge_stitches=parsed.get("gauge_stitches"),
            gauge_rows=parsed.get("gauge_rows"),
            gauge_size=parsed.get("gauge_size"),
            gauge_unit=parsed.get("gauge_unit"),
            needle_size=parsed.get("needle_size"),
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
