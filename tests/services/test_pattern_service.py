import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.pattern import (
    CraftType,
    GaugeUnit,
    PatternSource,
    PatternStatus,
    YarnWeight,
)
from app.services.pattern import (
    EmptyTextError,
    EmptyTitleError,
    FileTooLargeError,
    InvalidFileTypeError,
    PatternService,
    _MAX_FILE_SIZE,
)

_PDF_BYTES = b"%PDF-1.4 test"
_PDF_CONTENT_TYPE = "application/pdf"


def _groq_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = content
    return response


@pytest.fixture
def service():
    with patch("app.services.pattern.Groq"):
        yield PatternService()


@pytest.fixture
def confirm_kwargs():
    return dict(
        title="My Pattern",
        craft=CraftType.KNITTING,
        gauge_stitches=22.0,
        gauge_rows=None,
        gauge_size=10.0,
        gauge_unit=GaugeUnit.CM,
        needle_size="4mm",
        sizes=["S", "M"],
        yarns_data=[],
        cover_bytes=None,
        cover_suffix=".jpg",
    )


class TestValidate:
    def test_raises_invalid_type_for_non_pdf(self, service):
        with pytest.raises(InvalidFileTypeError):
            service._validate_pdf(b"data", "image/png")

    def test_raises_invalid_type_when_none(self, service):
        with pytest.raises(InvalidFileTypeError):
            service._validate_pdf(b"data", None)

    def test_raises_too_large(self, service):
        with pytest.raises(FileTooLargeError):
            service._validate_pdf(b"x" * (_MAX_FILE_SIZE + 1), _PDF_CONTENT_TYPE)

    def test_passes_for_valid_input(self, service):
        service._validate_pdf(_PDF_BYTES, _PDF_CONTENT_TYPE)  # must not raise


class TestExtractText:
    def test_delegates_to_pdfminer(self, service):
        with patch(
            "app.services.pattern.extract_text", return_value="pattern text"
        ) as mock_fn:
            result = service._extract_text(b"pdf bytes")

        mock_fn.assert_called_once()
        assert result == "pattern text"


class TestCallLlm:
    def test_parses_valid_response(self, service):
        payload = {
            "title": "Cozy Sweater",
            "craft": "KNITTING",
            "gauge_stitches": 22.0,
            "gauge_rows": 28.0,
            "gauge_size": 10.0,
            "gauge_unit": "CM",
            "needle_size": "4mm",
            "yarns": [
                {
                    "label": "MC",
                    "yarn_weight": "DK",
                    "meters_per_unit": 200.0,
                    "grams_per_unit": 100.0,
                    "grams_needed": 300.0,
                    "strands": 1,
                }
            ],
        }
        service._client.chat.completions.create.return_value = _groq_response(
            json.dumps(payload)
        )

        parsed, _ = service._call_llm("pattern text")

        assert parsed["title"] == "Cozy Sweater"
        assert parsed["craft"] == CraftType.KNITTING
        assert parsed["gauge_unit"] == GaugeUnit.CM
        assert parsed["yarns"][0]["yarn_weight"] == YarnWeight.DK

    def test_sets_none_for_unrecognized_enum_values(self, service):
        payload = {
            "title": "Test",
            "craft": "WEAVING",
            "gauge_unit": "FEET",
            "yarns": [{"yarn_weight": "CHUNKY", "strands": 1}],
        }
        service._client.chat.completions.create.return_value = _groq_response(
            json.dumps(payload)
        )

        parsed, _ = service._call_llm("text")

        assert parsed["craft"] is None
        assert parsed["gauge_unit"] is None
        assert parsed["yarns"][0]["yarn_weight"] is None

    def test_fallback_on_groq_exception(self, service):
        service._client.chat.completions.create.side_effect = Exception(
            "connection error"
        )

        parsed, _ = service._call_llm("text")

        assert parsed == {"title": "Unknown", "craft": None, "yarns": []}

    def test_fallback_on_invalid_json(self, service):
        service._client.chat.completions.create.return_value = _groq_response(
            "not json {{"
        )

        parsed, _ = service._call_llm("text")

        assert parsed == {"title": "Unknown", "craft": None, "yarns": []}


class TestImportFromPdf:
    def test_calls_repository_with_only_file_paths(self, service):
        fixed_uuid = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        db = MagicMock()
        mock_pattern = MagicMock()

        with (
            patch("app.services.pattern.uuid.uuid4", return_value=fixed_uuid),
            patch.object(
                service,
                "_save_file",
                side_effect=[
                    f"storage/original/{fixed_uuid}.pdf",
                    f"storage/parsed/{fixed_uuid}.json",
                ],
            ),
            patch("app.services.pattern.extract_text", return_value="text"),
            patch.object(service, "_get_parsed", return_value=({}, "{}")),
            patch("app.services.pattern.pattern_repository") as mock_repo,
        ):
            mock_repo.create.return_value = mock_pattern
            result = service.import_from_pdf(db, _PDF_BYTES, _PDF_CONTENT_TYPE)

        mock_repo.create.assert_called_once_with(
            db,
            yarns_data=[],
            source=PatternSource.PDF,
            status=PatternStatus.IMPORTED,
            original_file_path=f"storage/original/{fixed_uuid}.pdf",
            parsed_json_path=f"storage/parsed/{fixed_uuid}.json",
        )
        assert result is mock_pattern

    def test_propagates_invalid_type_error(self, service):
        with pytest.raises(InvalidFileTypeError):
            service.import_from_pdf(MagicMock(), b"data", "text/plain")

    def test_propagates_too_large_error(self, service):
        oversized = b"x" * (_MAX_FILE_SIZE + 1)
        with pytest.raises(FileTooLargeError):
            service.import_from_pdf(MagicMock(), oversized, _PDF_CONTENT_TYPE)


class TestImportFromText:
    def test_calls_repository_with_only_file_paths(self, service):
        fixed_uuid = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
        db = MagicMock()
        mock_pattern = MagicMock()

        with (
            patch("app.services.pattern.uuid.uuid4", return_value=fixed_uuid),
            patch.object(
                service,
                "_save_file",
                side_effect=[
                    f"storage/original/{fixed_uuid}.txt",
                    f"storage/parsed/{fixed_uuid}.json",
                ],
            ),
            patch.object(service, "_get_parsed", return_value=({}, "{}")),
            patch("app.services.pattern.pattern_repository") as mock_repo,
        ):
            mock_repo.create.return_value = mock_pattern
            result = service.import_from_text(db, "cast on 20 stitches...")

        mock_repo.create.assert_called_once_with(
            db,
            yarns_data=[],
            source=PatternSource.TEXT,
            status=PatternStatus.IMPORTED,
            original_file_path=f"storage/original/{fixed_uuid}.txt",
            parsed_json_path=f"storage/parsed/{fixed_uuid}.json",
        )
        assert result is mock_pattern

    def test_raises_empty_text_error_for_empty_string(self, service):
        with pytest.raises(EmptyTextError):
            service.import_from_text(MagicMock(), "")

    def test_raises_empty_text_error_for_whitespace_only(self, service):
        with pytest.raises(EmptyTextError):
            service.import_from_text(MagicMock(), "   \n\t  ")


class TestGetById:
    def test_delegates_to_repository(self, service):
        db = MagicMock()
        pattern = MagicMock()
        pattern_id = uuid.uuid4()

        with patch("app.services.pattern.pattern_repository") as mock_repo:
            mock_repo.get_by_id.return_value = pattern
            result = service.get_by_id(db, pattern_id)

        mock_repo.get_by_id.assert_called_once_with(db, pattern_id)
        assert result is pattern

    def test_returns_none_when_not_found(self, service):
        db = MagicMock()

        with patch("app.services.pattern.pattern_repository") as mock_repo:
            mock_repo.get_by_id.return_value = None
            result = service.get_by_id(db, uuid.uuid4())

        assert result is None


class TestGetPrefill:
    def test_returns_none_when_pattern_not_found(self, service):
        db = MagicMock()

        with patch.object(service, "get_by_id", return_value=None):
            result = service.get_prefill(db, uuid.uuid4())

        assert result is None

    def test_reads_parsed_json_for_imported_pattern(self, service):
        db = MagicMock()
        pattern = MagicMock()
        pattern.status = PatternStatus.IMPORTED
        pattern.parsed_json_path = "storage/parsed/test.json"
        parsed_data = {
            "title": "LLM Pattern",
            "craft": "KNITTING",
            "sizes": ["S", "M", "L"],
            "gauge_stitches": 22.0,
            "gauge_rows": None,
            "gauge_size": 10.0,
            "gauge_unit": "CM",
            "needle_size": "4mm",
            "yarns": [{"label": "Main", "yarn_weight": "DK", "strands": 1}],
        }

        with (
            patch.object(service, "get_by_id", return_value=pattern),
            patch.object(service, "_read_parsed_json", return_value=parsed_data),
        ):
            result = service.get_prefill(db, pattern.id)

        assert result["title"] == "LLM Pattern"
        assert result["sizes"] == ["S", "M", "L"]
        assert result["yarns"] == parsed_data["yarns"]

    def test_reads_db_data_for_confirmed_pattern(self, service):
        db = MagicMock()
        pattern = MagicMock()
        pattern.status = PatternStatus.CONFIRMED
        pattern.title = "Confirmed Pattern"
        pattern.sizes = ["XS", "S"]
        pattern.yarns = []

        with patch.object(service, "get_by_id", return_value=pattern):
            result = service.get_prefill(db, pattern.id)

        assert result["title"] == "Confirmed Pattern"
        assert result["sizes"] == ["XS", "S"]


class TestConfirm:
    def test_calls_repository_with_correct_args(self, service, confirm_kwargs):
        db = MagicMock()
        pattern = MagicMock()
        pattern.cover_image_path = None
        mock_result = MagicMock()

        with patch("app.services.pattern.pattern_repository") as mock_repo:
            mock_repo.update.return_value = mock_result
            result = service.confirm(db, pattern, **confirm_kwargs)

        mock_repo.update.assert_called_once_with(
            db,
            pattern,
            yarns_data=[],
            title="My Pattern",
            craft=CraftType.KNITTING,
            gauge_stitches=22.0,
            gauge_rows=None,
            gauge_size=10.0,
            gauge_unit=GaugeUnit.CM,
            needle_size="4mm",
            sizes=["S", "M"],
            cover_image_path=None,
            status=PatternStatus.CONFIRMED,
        )
        assert result is mock_result

    def test_raises_empty_title_error_for_empty_string(self, service, confirm_kwargs):
        confirm_kwargs["title"] = ""
        with pytest.raises(EmptyTitleError):
            service.confirm(MagicMock(), MagicMock(), **confirm_kwargs)

    def test_raises_empty_title_error_for_whitespace_only(
        self, service, confirm_kwargs
    ):
        confirm_kwargs["title"] = "   "
        with pytest.raises(EmptyTitleError):
            service.confirm(MagicMock(), MagicMock(), **confirm_kwargs)

    def test_saves_cover_image_and_passes_path_to_repository(
        self, service, confirm_kwargs
    ):
        db = MagicMock()
        pattern = MagicMock()
        pattern.id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        pattern.cover_image_path = None
        confirm_kwargs["cover_bytes"] = b"image data"
        confirm_kwargs["cover_suffix"] = ".png"
        expected_path = f"storage/covers/{pattern.id}.png"

        with (
            patch.object(
                service, "_save_file", return_value=expected_path
            ) as mock_save,
            patch("app.services.pattern.pattern_repository") as mock_repo,
        ):
            mock_repo.update.return_value = MagicMock()
            service.confirm(db, pattern, **confirm_kwargs)

        mock_save.assert_called_once_with(
            b"image data", "covers", str(pattern.id), ".png"
        )
        update_kwargs = mock_repo.update.call_args.kwargs
        assert update_kwargs["cover_image_path"] == expected_path

    def test_keeps_existing_cover_image_when_no_new_image(
        self, service, confirm_kwargs
    ):
        db = MagicMock()
        pattern = MagicMock()
        pattern.cover_image_path = "storage/covers/existing.jpg"
        confirm_kwargs["cover_bytes"] = None

        with patch("app.services.pattern.pattern_repository") as mock_repo:
            mock_repo.update.return_value = MagicMock()
            service.confirm(db, pattern, **confirm_kwargs)

        update_kwargs = mock_repo.update.call_args.kwargs
        assert update_kwargs["cover_image_path"] == "storage/covers/existing.jpg"
