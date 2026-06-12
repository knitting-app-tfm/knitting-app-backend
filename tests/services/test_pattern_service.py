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
from app.core.config import settings
from app.services.pattern import pattern_llm, pattern_parser

_PDF_BYTES = b"%PDF-1.4 test"
_PDF_CONTENT_TYPE = "application/pdf"


def _groq_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = content
    return response


@pytest.fixture
def service():
    with patch("app.services.pattern.pattern_service.Groq"):
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
    def test_delegates_to_pdfminer(self):
        with patch(
            "app.services.pattern.pattern_parser.extract_text",
            return_value="pattern text",
        ) as mock_fn:
            result = pattern_parser.extract_text_from_pdf(b"pdf bytes")

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

        parsed, _ = pattern_llm.call_llm(service._client, "pattern text")

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

        parsed, _ = pattern_llm.call_llm(service._client, "text")

        assert parsed["craft"] is None
        assert parsed["gauge_unit"] is None
        assert parsed["yarns"][0]["yarn_weight"] is None

    def test_fallback_on_groq_exception(self, service):
        service._client.chat.completions.create.side_effect = Exception(
            "connection error"
        )

        parsed, _ = pattern_llm.call_llm(service._client, "text")

        assert parsed == {"title": "Unknown", "craft": None, "yarns": []}

    def test_fallback_on_invalid_json(self, service):
        service._client.chat.completions.create.return_value = _groq_response(
            "not json {{"
        )

        parsed, _ = pattern_llm.call_llm(service._client, "text")

        assert parsed == {"title": "Unknown", "craft": None, "yarns": []}


class TestImportFromPdf:
    def test_calls_repository_with_only_file_paths(self, service):
        fixed_uuid = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        user_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
        db = MagicMock()
        mock_pattern = MagicMock()

        with (
            patch(
                "app.services.pattern.pattern_service.uuid.uuid4",
                return_value=fixed_uuid,
            ),
            patch(
                "app.services.pattern.pattern_storage.save_file",
                side_effect=[
                    f"storage/original/{fixed_uuid}.pdf",
                    f"storage/parsed/{fixed_uuid}.json",
                ],
            ),
            patch(
                "app.services.pattern.pattern_parser.extract_text_from_pdf",
                return_value="text",
            ),
            patch(
                "app.services.pattern.pattern_llm.get_parsed", return_value=({}, "{}")
            ),
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
        ):
            mock_repo.create.return_value = mock_pattern
            result = service.import_from_pdf(db, _PDF_BYTES, _PDF_CONTENT_TYPE, user_id)

        mock_repo.create.assert_called_once_with(
            db,
            yarns_data=[],
            source=PatternSource.PDF,
            status=PatternStatus.IMPORTED,
            original_file_path=f"storage/original/{fixed_uuid}.pdf",
            parsed_json_path=f"storage/parsed/{fixed_uuid}.json",
            user_id=user_id,
        )
        assert result is mock_pattern

    def test_propagates_invalid_type_error(self, service):
        with pytest.raises(InvalidFileTypeError):
            service.import_from_pdf(MagicMock(), b"data", "text/plain", uuid.uuid4())

    def test_propagates_too_large_error(self, service):
        oversized = b"x" * (_MAX_FILE_SIZE + 1)
        with pytest.raises(FileTooLargeError):
            service.import_from_pdf(
                MagicMock(), oversized, _PDF_CONTENT_TYPE, uuid.uuid4()
            )


class TestImportFromText:
    def test_calls_repository_with_only_file_paths(self, service):
        fixed_uuid = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
        user_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
        db = MagicMock()
        mock_pattern = MagicMock()

        with (
            patch(
                "app.services.pattern.pattern_service.uuid.uuid4",
                return_value=fixed_uuid,
            ),
            patch(
                "app.services.pattern.pattern_storage.save_file",
                side_effect=[
                    f"storage/original/{fixed_uuid}.txt",
                    f"storage/parsed/{fixed_uuid}.json",
                ],
            ),
            patch(
                "app.services.pattern.pattern_llm.get_parsed", return_value=({}, "{}")
            ),
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
        ):
            mock_repo.create.return_value = mock_pattern
            result = service.import_from_text(db, "cast on 20 stitches...", user_id)

        mock_repo.create.assert_called_once_with(
            db,
            yarns_data=[],
            source=PatternSource.TEXT,
            status=PatternStatus.IMPORTED,
            original_file_path=f"storage/original/{fixed_uuid}.txt",
            parsed_json_path=f"storage/parsed/{fixed_uuid}.json",
            user_id=user_id,
        )
        assert result is mock_pattern

    def test_raises_empty_text_error_for_empty_string(self, service):
        with pytest.raises(EmptyTextError):
            service.import_from_text(MagicMock(), "", uuid.uuid4())

    def test_raises_empty_text_error_for_whitespace_only(self, service):
        with pytest.raises(EmptyTextError):
            service.import_from_text(MagicMock(), "   \n\t  ", uuid.uuid4())


class TestGetById:
    def test_delegates_to_repository(self, service):
        db = MagicMock()
        pattern = MagicMock()
        pattern_id = uuid.uuid4()

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.get_by_id.return_value = pattern
            result = service.get_by_id(db, pattern_id)

        mock_repo.get_by_id.assert_called_once_with(db, pattern_id)
        assert result is pattern

    def test_returns_none_when_not_found(self, service):
        db = MagicMock()

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
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
            patch(
                "app.services.pattern.pattern_storage.read_parsed_json",
                return_value=parsed_data,
            ),
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

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
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
            patch(
                "app.services.pattern.pattern_storage.save_file",
                return_value=expected_path,
            ) as mock_save,
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
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

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.update.return_value = MagicMock()
            service.confirm(db, pattern, **confirm_kwargs)

        update_kwargs = mock_repo.update.call_args.kwargs
        assert update_kwargs["cover_image_path"] == "storage/covers/existing.jpg"

    def test_confirm_tokenized_pattern_resets_to_confirmed(
        self, service, confirm_kwargs
    ):
        db = MagicMock()
        pattern = MagicMock()
        pattern.status = PatternStatus.TOKENIZED
        pattern.tokens_file_path = "storage/tokens/abc.json"
        pattern.cover_image_path = None

        with (
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
            patch("app.services.pattern.pattern_service.scaling_repository"),
            patch("app.services.pattern.pattern_storage.delete_file"),
        ):
            mock_repo.update.return_value = MagicMock()
            service.confirm(db, pattern, **confirm_kwargs)

        update_kwargs = mock_repo.update.call_args.kwargs
        assert update_kwargs["tokens_file_path"] is None
        assert update_kwargs["status"] == PatternStatus.CONFIRMED

    def test_confirm_tokenized_pattern_deletes_scaling(self, service, confirm_kwargs):
        db = MagicMock()
        pattern = MagicMock()
        pattern.status = PatternStatus.TOKENIZED
        pattern.tokens_file_path = None
        pattern.cover_image_path = None

        with (
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
            patch(
                "app.services.pattern.pattern_service.scaling_repository"
            ) as mock_scaling_repo,
        ):
            mock_repo.update.return_value = MagicMock()
            service.confirm(db, pattern, **confirm_kwargs)

        mock_scaling_repo.delete_by_pattern_id.assert_called_once_with(db, pattern.id)

    def test_confirm_tokenized_pattern_deletes_tokens_file(
        self, service, confirm_kwargs
    ):
        db = MagicMock()
        pattern = MagicMock()
        pattern.status = PatternStatus.TOKENIZED
        pattern.tokens_file_path = "storage/tokens/abc.json"
        pattern.cover_image_path = None

        with (
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
            patch("app.services.pattern.pattern_service.scaling_repository"),
            patch("app.services.pattern.pattern_storage.delete_file") as mock_delete,
        ):
            mock_repo.update.return_value = MagicMock()
            service.confirm(db, pattern, **confirm_kwargs)

        mock_delete.assert_called_once_with("storage/tokens/abc.json")

    def test_confirm_normalizes_none_sizes_to_empty_list(self, service, confirm_kwargs):
        db = MagicMock()
        pattern = MagicMock()
        pattern.cover_image_path = None
        confirm_kwargs["sizes"] = None

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.update.return_value = MagicMock()
            service.confirm(db, pattern, **confirm_kwargs)

        update_kwargs = mock_repo.update.call_args.kwargs
        assert update_kwargs["sizes"] == []


# ---------------------------------------------------------------------------
# pattern_llm — get_parsed / mock_response
# ---------------------------------------------------------------------------


class TestGetParsed:
    def test_calls_mock_response_when_flag_enabled(self):
        client = MagicMock()
        with patch.object(settings, "USE_MOCK_LLM", True):
            with patch(
                "app.services.pattern.pattern_llm.mock_response",
                return_value=({}, "{}"),
            ) as mock_fn:
                result = pattern_llm.get_parsed(client, "text")
        mock_fn.assert_called_once()
        assert result == ({}, "{}")

    def test_calls_call_llm_when_flag_disabled(self):
        client = MagicMock()
        with patch.object(settings, "USE_MOCK_LLM", False):
            with patch(
                "app.services.pattern.pattern_llm.call_llm",
                return_value=({"title": "T"}, "{}"),
            ) as mock_fn:
                pattern_llm.get_parsed(client, "text")
        mock_fn.assert_called_once_with(client, "text")


class TestMockResponse:
    def test_returns_parsed_dict_and_json_string(self):
        parsed, json_str = pattern_llm.mock_response()

        assert parsed["title"] == "Mock Knitting Pattern"
        assert parsed["craft"] == CraftType.KNITTING
        assert parsed["gauge_unit"] == GaugeUnit.CM
        assert parsed["yarns"][0]["yarn_weight"] == YarnWeight.DK
        assert json.loads(json_str)["title"] == "Mock Knitting Pattern"

    def test_json_string_is_valid_json(self):
        _, json_str = pattern_llm.mock_response()
        assert json.loads(json_str) is not None


class TestCallLlmNoneContent:
    def test_fallback_when_response_content_is_none(self, service):
        service._client.chat.completions.create.return_value = _groq_response(None)

        parsed, _ = pattern_llm.call_llm(service._client, "text")

        assert parsed == {"title": "Unknown", "craft": None, "yarns": []}


# ---------------------------------------------------------------------------
# pattern_service — _normalize_yarns
# ---------------------------------------------------------------------------


class TestNormalizeYarns:
    def test_valid_yarn_weight_is_coerced_to_enum(self, service):
        result = service._normalize_yarns([{"yarn_weight": "DK", "label": "Main"}])

        assert result[0]["yarn_weight"] == YarnWeight.DK
        assert result[0]["label"] == "Main"

    def test_invalid_yarn_weight_becomes_none(self, service):
        result = service._normalize_yarns([{"yarn_weight": "INVALID"}])

        assert result[0]["yarn_weight"] is None

    def test_none_yarn_weight_becomes_none(self, service):
        result = service._normalize_yarns([{"yarn_weight": None}])

        assert result[0]["yarn_weight"] is None

    def test_strands_defaults_to_one_when_absent(self, service):
        result = service._normalize_yarns([{"yarn_weight": "DK"}])

        assert result[0]["strands"] == 1

    def test_existing_strands_value_is_preserved(self, service):
        result = service._normalize_yarns([{"yarn_weight": "DK", "strands": 2}])

        assert result[0]["strands"] == 2

    def test_empty_list_returns_empty_list(self, service):
        assert service._normalize_yarns([]) == []

    def test_original_dict_is_not_mutated(self, service):
        original = {"yarn_weight": "DK", "label": "Main"}
        service._normalize_yarns([original])

        assert original["yarn_weight"] == "DK"

    def test_empty_string_float_fields_become_none(self, service):
        result = service._normalize_yarns(
            [
                {
                    "yarn_weight": "DK",
                    "meters_per_unit": "",
                    "grams_per_unit": "",
                    "grams_needed": "",
                }
            ]
        )

        assert result[0]["meters_per_unit"] is None
        assert result[0]["grams_per_unit"] is None
        assert result[0]["grams_needed"] is None

    def test_valid_float_fields_are_coerced_to_float(self, service):
        result = service._normalize_yarns(
            [
                {
                    "yarn_weight": "DK",
                    "meters_per_unit": "200",
                    "grams_per_unit": "100.5",
                    "grams_needed": [300, 400],
                }
            ]
        )

        assert result[0]["meters_per_unit"] == 200.0
        assert result[0]["grams_per_unit"] == 100.5
        assert result[0]["grams_needed"] == [300.0, 400.0]

    def test_grams_needed_scalar_wrapped_in_list(self, service):
        result = service._normalize_yarns([{"grams_needed": 250}])

        assert result[0]["grams_needed"] == [250.0]

    def test_grams_needed_none_stays_none(self, service):
        result = service._normalize_yarns([{"grams_needed": None}])

        assert result[0]["grams_needed"] is None

    def test_grams_needed_list_items_coerced_to_float(self, service):
        result = service._normalize_yarns([{"grams_needed": ["100", "200.5"]}])

        assert result[0]["grams_needed"] == [100.0, 200.5]


# ---------------------------------------------------------------------------
# pattern_llm — normalize grams_needed
# ---------------------------------------------------------------------------


class TestNormalizeLlmGramsNeeded:
    def test_scalar_grams_needed_is_wrapped_in_list(self):
        raw = {"yarns": [{"grams_needed": 300.0, "strands": 1}]}
        result = pattern_llm.normalize(raw)

        assert result["yarns"][0]["grams_needed"] == [300.0]

    def test_array_grams_needed_is_unchanged(self):
        raw = {"yarns": [{"grams_needed": [100.0, 200.0], "strands": 1}]}
        result = pattern_llm.normalize(raw)

        assert result["yarns"][0]["grams_needed"] == [100.0, 200.0]

    def test_null_grams_needed_stays_null(self):
        raw = {"yarns": [{"grams_needed": None, "strands": 1}]}
        result = pattern_llm.normalize(raw)

        assert result["yarns"][0]["grams_needed"] is None

    def test_missing_grams_needed_key_is_not_added(self):
        raw = {"yarns": [{"strands": 1}]}
        result = pattern_llm.normalize(raw)

        assert "grams_needed" not in result["yarns"][0]


# ---------------------------------------------------------------------------
# confirm — grams_needed length validation
# ---------------------------------------------------------------------------


class TestConfirmGramsNeededValidation:
    def test_raises_when_array_length_does_not_match_sizes(
        self, service, confirm_kwargs
    ):
        confirm_kwargs["sizes"] = ["S", "M", "L"]
        confirm_kwargs["yarns_data"] = [{"grams_needed": [100.0, 200.0]}]  # 2 != 3

        with patch("app.services.pattern.pattern_service.pattern_repository"):
            with pytest.raises(
                ValueError, match="grams_needed must have one value per size"
            ):
                service.confirm(MagicMock(), MagicMock(), **confirm_kwargs)

    def test_passes_when_array_length_matches_sizes(self, service, confirm_kwargs):
        confirm_kwargs["sizes"] = ["S", "M"]
        confirm_kwargs["yarns_data"] = [{"grams_needed": [100.0, 200.0]}]
        pattern = MagicMock()
        pattern.cover_image_path = None

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.update.return_value = MagicMock()
            service.confirm(MagicMock(), pattern, **confirm_kwargs)  # must not raise

    def test_null_grams_needed_always_allowed_with_sizes(self, service, confirm_kwargs):
        confirm_kwargs["sizes"] = ["S", "M", "L"]
        confirm_kwargs["yarns_data"] = [{"grams_needed": None}]
        pattern = MagicMock()
        pattern.cover_image_path = None

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.update.return_value = MagicMock()
            service.confirm(MagicMock(), pattern, **confirm_kwargs)  # must not raise

    def test_single_element_allowed_when_no_sizes(self, service, confirm_kwargs):
        confirm_kwargs["sizes"] = []
        confirm_kwargs["yarns_data"] = [{"grams_needed": [150.0]}]
        pattern = MagicMock()
        pattern.cover_image_path = None

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.update.return_value = MagicMock()
            service.confirm(MagicMock(), pattern, **confirm_kwargs)  # must not raise

    def test_raises_when_multiple_elements_and_no_sizes(self, service, confirm_kwargs):
        confirm_kwargs["sizes"] = []
        confirm_kwargs["yarns_data"] = [{"grams_needed": [100.0, 200.0]}]

        with patch("app.services.pattern.pattern_service.pattern_repository"):
            with pytest.raises(
                ValueError, match="grams_needed must have one value per size"
            ):
                service.confirm(MagicMock(), MagicMock(), **confirm_kwargs)

    def test_null_grams_needed_allowed_when_no_sizes(self, service, confirm_kwargs):
        confirm_kwargs["sizes"] = []
        confirm_kwargs["yarns_data"] = [{"grams_needed": None}]
        pattern = MagicMock()
        pattern.cover_image_path = None

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.update.return_value = MagicMock()
            service.confirm(MagicMock(), pattern, **confirm_kwargs)  # must not raise
