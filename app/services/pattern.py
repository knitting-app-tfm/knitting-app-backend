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

    def import_from_pdf(
        self, db: Session, content: bytes, content_type: str | None
    ) -> Pattern:
        self._validate(content, content_type)

        file_uuid = str(uuid.uuid4())

        original_path = self._save_bytes(
            content, subdir="original", file_uuid=file_uuid, suffix=".pdf"
        )

        text = self._extract_text(content)
        parsed, json_str = self._call_llm(text)

        parsed_path = self._save_text(
            json_str, subdir="parsed", file_uuid=file_uuid, suffix=".json"
        )

        yarns_data = parsed.pop("yarns", [])

        return pattern_repository.create(
            db,
            yarns_data=yarns_data,
            source=PatternSource.PDF,
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate(self, content: bytes, content_type: str | None) -> None:
        if content_type != "application/pdf":
            raise InvalidFileTypeError("Only PDF files are allowed")
        if len(content) > _MAX_FILE_SIZE:
            raise FileTooLargeError("File size must not exceed 10MB")

    def _save_bytes(
        self, content: bytes, subdir: str, file_uuid: str, suffix: str
    ) -> str:
        path = Path(settings.STORAGE_BASE_PATH) / subdir / f"{file_uuid}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return f"storage/{subdir}/{file_uuid}{suffix}"

    def _save_text(self, content: str, subdir: str, file_uuid: str, suffix: str) -> str:
        path = Path(settings.STORAGE_BASE_PATH) / subdir / f"{file_uuid}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"storage/{subdir}/{file_uuid}{suffix}"

    def _extract_text(self, content: bytes) -> str:
        return extract_text(BytesIO(content))

    def _call_llm(self, text: str) -> tuple[dict, str]:
        try:
            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": _LLM_PROMPT + text}],
                response_format={"type": "json_object"},
            )
            json_str = response.choices[0].message.content
            raw = json.loads(json_str)
            parsed = self._normalize(raw)
            return parsed, json.dumps(parsed, ensure_ascii=False)
        except Exception:
            # AC4: if LLM fails, return empty metadata — user fills in manually
            fallback = {"title": "Unknown", "craft": None, "yarns": []}
            return fallback, json.dumps(fallback)

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
