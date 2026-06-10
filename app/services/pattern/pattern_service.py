import json
import uuid
from uuid import UUID

from groq import Groq
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
from app.repositories.scaling import scaling_repository
from app.services.pattern import pattern_llm, pattern_parser, pattern_storage
from app.services.pattern.pattern_exceptions import (
    EmptyTextError,
    EmptyTitleError,
    FileTooLargeError,
    InvalidFileTypeError,
    PatternNotConfirmedError,
)
from app.services.pattern import pattern_tokenizer

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class PatternService:
    def __init__(self) -> None:
        self._client = Groq(api_key=settings.GROQ_API_KEY)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def import_from_pdf(
        self, db: Session, content: bytes, content_type: str | None, user_id: UUID
    ) -> Pattern:
        self._validate_pdf(content, content_type)
        file_uuid = str(uuid.uuid4())
        original_path = pattern_storage.save_file(
            content, "original", file_uuid, ".pdf"
        )
        text = pattern_parser.extract_text_from_pdf(content)
        _, json_str = pattern_llm.get_parsed(self._client, text)
        parsed_path = pattern_storage.save_file(json_str, "parsed", file_uuid, ".json")
        return self._persist_pattern(
            db, original_path, parsed_path, PatternSource.PDF, user_id
        )

    def import_from_text(self, db: Session, text: str, user_id: UUID) -> Pattern:
        if not text or not text.strip():
            raise EmptyTextError("Text cannot be empty")
        file_uuid = str(uuid.uuid4())
        original_path = pattern_storage.save_file(text, "original", file_uuid, ".txt")
        _, json_str = pattern_llm.get_parsed(self._client, text)
        parsed_path = pattern_storage.save_file(json_str, "parsed", file_uuid, ".json")
        return self._persist_pattern(
            db, original_path, parsed_path, PatternSource.TEXT, user_id
        )

    def get_by_id(self, db: Session, pattern_id: uuid.UUID) -> Pattern | None:
        return pattern_repository.get_by_id(db, pattern_id)

    def get_by_user_id(self, db: Session, user_id: UUID) -> list[Pattern]:
        return pattern_repository.get_by_user_id(db, user_id)

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
            parsed = pattern_storage.read_parsed_json(pattern.parsed_json_path)
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
            cover_image_path = pattern_storage.save_file(
                cover_bytes, "covers", str(pattern.id), cover_suffix
            )

        extra_kwargs = {}
        if pattern.status == PatternStatus.TOKENIZED:
            scaling_repository.delete_by_pattern_id(db, pattern.id)
            if pattern.tokens_file_path:
                pattern_storage.delete_file(pattern.tokens_file_path)
            extra_kwargs["tokens_file_path"] = None

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
            **extra_kwargs,
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
            known_full_names = {
                abbr.full_name.lower(): abbr.abbreviation
                for abbr in all_abbreviations
                if abbr.full_name
            }
            segments = pattern_parser.read_source_text(pattern)
            num_sizes = len(pattern.sizes) if pattern.sizes else 0
            lines = pattern_tokenizer.tokenize(
                segments, known_codes, known_full_names, num_sizes
            )
            pattern_tokenizer.enrich_abbreviations(lines, db)
            tokens_path = pattern_storage.save_file(
                json.dumps(lines, ensure_ascii=False),
                "tokens",
                str(pattern.id),
                ".json",
            )
            pattern_repository.set_tokenized(db, pattern, tokens_path)
        else:  # TOKENIZED
            lines = pattern_storage.read_tokens_file(pattern.tokens_file_path)
            pattern_tokenizer.enrich_abbreviations(lines, db)

        return lines

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_pdf(self, content: bytes, content_type: str | None) -> None:
        if content_type != "application/pdf":
            raise InvalidFileTypeError("Only PDF files are allowed")
        if len(content) > _MAX_FILE_SIZE:
            raise FileTooLargeError("File size must not exceed 10MB")

    def _persist_pattern(
        self,
        db: Session,
        original_path: str,
        parsed_path: str,
        source: PatternSource,
        user_id: UUID,
    ) -> Pattern:
        return pattern_repository.create(
            db,
            yarns_data=[],
            source=source,
            status=PatternStatus.IMPORTED,
            original_file_path=original_path,
            parsed_json_path=parsed_path,
            user_id=user_id,
        )

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


pattern_service = PatternService()
