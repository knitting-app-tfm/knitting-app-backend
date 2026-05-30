import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.pattern import PatternSource, PatternStatus
from app.schemas.pattern import TextSegment
from app.services.pattern import PatternNotConfirmedError, PatternService

_PATTERN_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

_NO_FMT = {"bold": False, "italic": False, "font_size": None}


def _seg(
    text: str, bold: bool = False, italic: bool = False, font_size: float | None = None
) -> TextSegment:
    return TextSegment(text=text, bold=bold, italic=italic, font_size=font_size)


@pytest.fixture
def service():
    with patch("app.services.pattern.Groq"):
        yield PatternService()


@pytest.fixture
def mock_pattern():
    p = MagicMock()
    p.id = _PATTERN_ID
    p.tokens_file_path = None
    return p


# ---------------------------------------------------------------------------
# Orchestration — acceptance criteria
# ---------------------------------------------------------------------------


class TestTranslate:
    def test_raises_for_imported_pattern(self, service, mock_pattern):
        """AC5: IMPORTED status must raise 400-equivalent error."""
        mock_pattern.status = PatternStatus.IMPORTED
        db = MagicMock()

        with patch("app.services.pattern.pattern_repository") as mock_repo:
            mock_repo.get_by_id.return_value = mock_pattern
            with pytest.raises(PatternNotConfirmedError):
                service.translate(db, _PATTERN_ID)

    def test_returns_none_when_pattern_not_found(self, service):
        db = MagicMock()

        with patch("app.services.pattern.pattern_repository") as mock_repo:
            mock_repo.get_by_id.return_value = None
            result = service.translate(db, uuid.uuid4())

        assert result is None

    def test_confirmed_pdf_tokenizes_saves_and_returns_lines(
        self, service, mock_pattern
    ):
        """AC1: CONFIRMED + PDF — tokenizes, persists file, updates status."""
        mock_pattern.status = PatternStatus.CONFIRMED
        mock_pattern.source = PatternSource.PDF
        db = MagicMock()

        mock_segments = [_seg("Cast on")]
        mock_lines = [
            {"line": 1, **_NO_FMT, "tokens": [{"type": "text", "value": "Cast on"}]}
        ]
        expected_path = f"storage/tokens/{_PATTERN_ID}.json"

        with (
            patch("app.services.pattern.pattern_repository") as mock_repo,
            patch("app.services.pattern.abbreviation_repository") as mock_abbr_repo,
            patch.object(
                service, "_read_source_text", return_value=mock_segments
            ) as mock_read,
            patch.object(service, "_tokenize", return_value=mock_lines) as mock_tok,
            patch.object(service, "_enrich_abbreviations", return_value=mock_lines),
            patch.object(service, "_save_file", return_value=expected_path),
        ):
            mock_repo.get_by_id.return_value = mock_pattern
            mock_abbr_repo.get_all.return_value = []

            result = service.translate(db, _PATTERN_ID)

        mock_read.assert_called_once_with(mock_pattern)
        mock_tok.assert_called_once_with(mock_segments, set())
        mock_repo.set_tokenized.assert_called_once_with(db, mock_pattern, expected_path)
        assert result == mock_lines

    def test_confirmed_text_tokenizes_saves_and_returns_lines(
        self, service, mock_pattern
    ):
        """AC6: CONFIRMED + TEXT — reads .txt file, tokenizes, persists, updates status."""
        mock_pattern.status = PatternStatus.CONFIRMED
        mock_pattern.source = PatternSource.TEXT
        db = MagicMock()

        mock_segments = [_seg("Work k2")]
        mock_lines = [
            {"line": 1, **_NO_FMT, "tokens": [{"type": "text", "value": "Work k2"}]}
        ]
        expected_path = f"storage/tokens/{_PATTERN_ID}.json"

        with (
            patch("app.services.pattern.pattern_repository") as mock_repo,
            patch("app.services.pattern.abbreviation_repository") as mock_abbr_repo,
            patch.object(
                service, "_read_source_text", return_value=mock_segments
            ) as mock_read,
            patch.object(service, "_tokenize", return_value=mock_lines),
            patch.object(service, "_enrich_abbreviations", return_value=mock_lines),
            patch.object(service, "_save_file", return_value=expected_path),
        ):
            mock_repo.get_by_id.return_value = mock_pattern
            mock_abbr_repo.get_all.return_value = []

            result = service.translate(db, _PATTERN_ID)

        mock_read.assert_called_once_with(mock_pattern)
        mock_repo.set_tokenized.assert_called_once_with(db, mock_pattern, expected_path)
        assert result == mock_lines

    def test_tokenized_reuses_disk_without_retokenizing(self, service, mock_pattern):
        """AC2: TOKENIZED status — reads from disk, never calls _tokenize."""
        mock_pattern.status = PatternStatus.TOKENIZED
        mock_pattern.tokens_file_path = f"storage/tokens/{_PATTERN_ID}.json"
        db = MagicMock()

        stored_lines = [
            {"line": 1, **_NO_FMT, "tokens": []},
            {"line": 2, **_NO_FMT, "tokens": []},
        ]

        with (
            patch("app.services.pattern.pattern_repository") as mock_repo,
            patch.object(service, "_tokenize") as mock_tok,
            patch.object(service, "_read_tokens_file", return_value=stored_lines),
            patch.object(service, "_enrich_abbreviations", return_value=stored_lines),
        ):
            mock_repo.get_by_id.return_value = mock_pattern

            result = service.translate(db, _PATTERN_ID)

        mock_tok.assert_not_called()
        assert result == stored_lines


# ---------------------------------------------------------------------------
# _read_source_text
# ---------------------------------------------------------------------------


class TestReadSourceText:
    def test_pdf_extracts_segments_with_formatting(self, service):
        pattern = MagicMock()
        pattern.source = PatternSource.PDF
        pattern.original_file_path = f"storage/original/{_PATTERN_ID}.pdf"

        mock_segments = [_seg("Cast on\n", bold=True, font_size=12.0)]

        with patch.object(
            service, "_extract_segments_from_pdf", return_value=mock_segments
        ) as mock_extract:
            result = service._read_source_text(pattern)

        assert result is mock_segments
        assert mock_extract.call_count == 1

    def test_text_produces_one_segment_per_line(self, service):
        pattern = MagicMock()
        pattern.source = PatternSource.TEXT
        pattern.original_file_path = f"storage/original/{_PATTERN_ID}.txt"

        with patch("pathlib.Path.read_text", return_value="line one\nline two"):
            result = service._read_source_text(pattern)

        assert len(result) == 2
        assert result[0] == TextSegment(
            text="line one", bold=False, italic=False, font_size=None
        )
        assert result[1] == TextSegment(
            text="line two", bold=False, italic=False, font_size=None
        )

    def test_text_trailing_newline_produces_empty_last_segment(self, service):
        pattern = MagicMock()
        pattern.source = PatternSource.TEXT
        pattern.original_file_path = f"storage/original/{_PATTERN_ID}.txt"

        with patch("pathlib.Path.read_text", return_value="only line\n"):
            result = service._read_source_text(pattern)

        assert len(result) == 2
        assert result[1] == TextSegment(
            text="", bold=False, italic=False, font_size=None
        )

    def test_text_segments_have_no_formatting(self, service):
        pattern = MagicMock()
        pattern.source = PatternSource.TEXT
        pattern.original_file_path = f"storage/original/{_PATTERN_ID}.txt"

        with patch("pathlib.Path.read_text", return_value="CO 20 sts"):
            result = service._read_source_text(pattern)

        seg = result[0]
        assert seg.bold is False
        assert seg.italic is False
        assert seg.font_size is None


# ---------------------------------------------------------------------------
# _tokenize (line-by-line structure + formatting propagation)
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_empty_segments_produce_empty_token_lists(self, service):
        segments = [_seg("Line one"), _seg(""), _seg("Line three")]
        result = service._tokenize(segments, known_codes=set())

        assert len(result) == 3
        assert result[0] == {
            "line": 1,
            **_NO_FMT,
            "tokens": [{"type": "text", "value": "Line one"}],
        }
        assert result[1] == {"line": 2, **_NO_FMT, "tokens": []}
        assert result[2]["line"] == 3
        assert result[2]["tokens"] != []

    def test_line_numbers_are_one_indexed_and_sequential(self, service):
        segments = [_seg("a"), _seg(""), _seg("b")]
        result = service._tokenize(segments, known_codes=set())

        assert [r["line"] for r in result] == [1, 2, 3]

    def test_empty_last_segment_maps_to_empty_line(self, service):
        segments = [_seg("only line"), _seg("")]
        result = service._tokenize(segments, known_codes=set())

        assert len(result) == 2
        assert result[1]["line"] == 2
        assert result[1]["tokens"] == []

    def test_formatting_is_set_on_line_dict(self, service):
        segments = [_seg("Cast on", bold=True, italic=False, font_size=14.0)]
        result = service._tokenize(segments, known_codes=set())

        line = result[0]
        assert line["bold"] is True
        assert line["italic"] is False
        assert line["font_size"] == 14.0

    def test_formatting_is_not_duplicated_on_tokens(self, service):
        segments = [_seg("20 sts", bold=False, italic=True, font_size=10.0)]
        result = service._tokenize(segments, known_codes={"sts"})

        for token in result[0]["tokens"]:
            assert "bold" not in token
            assert "italic" not in token
            assert "font_size" not in token

    def test_line_dict_includes_formatting_fields(self, service):
        segments = [_seg("work in rounds", bold=False, italic=False, font_size=12.5)]
        result = service._tokenize(segments, known_codes=set())

        line = result[0]
        assert "bold" in line
        assert "italic" in line
        assert "font_size" in line
        assert line["font_size"] == 12.5

    def test_empty_line_formatting_is_preserved(self, service):
        segments = [_seg(""), _seg("")]
        result = service._tokenize(segments, known_codes=set())

        for line in result:
            assert "bold" in line
            assert "italic" in line
            assert "font_size" in line

    def test_different_lines_have_independent_formatting(self, service):
        segments = [
            _seg("Bold line", bold=True, font_size=16.0),
            _seg("Normal line", bold=False, font_size=10.0),
        ]
        result = service._tokenize(segments, known_codes=set())

        assert result[0]["bold"] is True
        assert result[0]["font_size"] == 16.0

        assert result[1]["bold"] is False
        assert result[1]["font_size"] == 10.0


# ---------------------------------------------------------------------------
# _tokenize_line — token type detection
# ---------------------------------------------------------------------------


class TestTokenizeLine:
    def test_adjacent_plain_words_merge_into_single_text_token(self, service):
        tokens = service._tokenize_line("Cast on", known_codes=set())

        assert tokens == [{"type": "text", "value": "Cast on"}]

    def test_abbreviation_splits_surrounding_text(self, service):
        tokens = service._tokenize_line("Work sts here", known_codes={"sts"})

        assert tokens[0] == {"type": "text", "value": "Work"}
        assert tokens[1]["type"] == "abbreviation"
        assert tokens[1]["code"] == "sts"
        assert tokens[2] == {"type": "text", "value": "here"}

    def test_size_group_extracts_values_and_peeks_unit(self, service):
        tokens = service._tokenize_line(
            "Cast on 147 (159) 174 sts", known_codes={"sts"}
        )

        sg = next(t for t in tokens if t["type"] == "size_group")
        assert sg["values"] == [147, 159, 174]
        assert sg["unit"] == "sts"  # raw keyword, not canonicalised
        assert sg["scalable"] is True

    def test_size_group_does_not_consume_following_abbreviation(self, service):
        """The unit-peek must not remove the abbreviation token from the stream."""
        tokens = service._tokenize_line("147 (159) 174 sts", known_codes={"sts"})

        types = [t["type"] for t in tokens]
        assert "size_group" in types
        assert "abbreviation" in types

    def test_number_with_non_scalable_unit(self, service):
        tokens = service._tokenize_line("3.5mm", known_codes=set())

        assert tokens == [
            {"type": "number", "value": 3.5, "unit": "mm", "scalable": False}
        ]

    def test_number_with_scalable_unit(self, service):
        tokens = service._tokenize_line("11 rounds", known_codes=set())

        assert tokens == [
            {"type": "number", "value": 11, "unit": "rounds", "scalable": True}
        ]

    def test_number_unit_is_consumed_not_duplicated(self, service):
        """'rounds' consumed as number unit must not also appear as a text token."""
        tokens = service._tokenize_line("11 rounds", known_codes=set())

        assert len(tokens) == 1
        assert tokens[0]["type"] == "number"

    def test_bare_number_has_no_unit(self, service):
        tokens = service._tokenize_line("5", known_codes=set())

        assert tokens == [
            {"type": "number", "value": 5, "unit": None, "scalable": False}
        ]

    def test_whole_number_value_serializes_as_int(self, service):
        tokens = service._tokenize_line("11 rows", known_codes=set())

        assert isinstance(tokens[0]["value"], int)

    def test_decimal_number_value_is_float(self, service):
        tokens = service._tokenize_line("3.5mm", known_codes=set())

        assert isinstance(tokens[0]["value"], float)

    def test_punctuation_is_dropped(self, service):
        tokens = service._tokenize_line("k2, p1", known_codes={"k2", "p1"})

        assert all(t["type"] == "abbreviation" for t in tokens)
        assert len(tokens) == 2

    def test_abbreviation_matching_is_case_insensitive(self, service):
        tokens = service._tokenize_line("CO", known_codes={"co"})

        assert tokens[0]["type"] == "abbreviation"
        assert tokens[0]["code"] == "CO"

    def test_number_unit_stored_as_raw_keyword(self, service):
        """Unit is stored exactly as it appears in the text, never canonicalised."""
        tokens = service._tokenize_line("5 sts", known_codes=set())

        assert tokens[0]["unit"] == "sts"

    def test_full_line_example(self, service):
        """Integration: the spec's reference line produces the expected token sequence."""
        known = {"sts"}
        tokens = service._tokenize_line(
            "Cast on 147 (159) 174 sts on 3.5mm needles", known_codes=known
        )

        assert tokens[0] == {"type": "text", "value": "Cast on"}
        assert tokens[1]["type"] == "size_group"
        assert tokens[1]["values"] == [147, 159, 174]
        assert tokens[2]["type"] == "abbreviation"
        assert tokens[2]["code"] == "sts"
        assert tokens[3] == {"type": "text", "value": "on"}
        assert tokens[4] == {
            "type": "number",
            "value": 3.5,
            "unit": "mm",
            "scalable": False,
        }

    # ------------------------------------------------------------------
    # Unit-before-number (Case 2)
    # ------------------------------------------------------------------

    def test_unit_before_number_scalable(self, service):
        tokens = service._tokenize_line("row 1", known_codes=set())

        assert tokens == [
            {"type": "number", "value": 1, "unit": "row", "scalable": True}
        ]

    def test_unit_before_number_in_sentence(self, service):
        """Spec example 2: 'Work row 1 as follows'."""
        tokens = service._tokenize_line("Work row 1 as follows", known_codes=set())

        assert tokens[0] == {"type": "text", "value": "Work"}
        assert tokens[1] == {
            "type": "number",
            "value": 1,
            "unit": "row",
            "scalable": True,
        }
        assert tokens[2] == {"type": "text", "value": "as follows"}

    def test_unit_before_number_plural_form(self, service):
        tokens = service._tokenize_line("round 2", known_codes=set())

        assert tokens == [
            {"type": "number", "value": 2, "unit": "round", "scalable": True}
        ]

    def test_unit_before_number_consumes_both_unit_and_number(self, service):
        tokens = service._tokenize_line("row 5", known_codes=set())

        assert len(tokens) == 1
        assert tokens[0]["type"] == "number"

    # ------------------------------------------------------------------
    # Unit keyword without adjacent number (Case 3)
    # ------------------------------------------------------------------

    def test_unit_keyword_without_adjacent_number_becomes_text(self, service):
        """Spec example 3: 'work in rounds' — no number adjacent to any unit word."""
        tokens = service._tokenize_line("work in rounds", known_codes=set())

        assert tokens == [{"type": "text", "value": "work in rounds"}]

    def test_unit_keyword_between_text_words_is_not_consumed(self, service):
        tokens = service._tokenize_line("work in rows", known_codes=set())

        assert tokens == [{"type": "text", "value": "work in rows"}]

    def test_unit_keyword_without_number_becomes_abbreviation_when_in_known_codes(
        self, service
    ):
        """'sts' with no adjacent number falls through to the abbreviation path."""
        tokens = service._tokenize_line("work sts", known_codes={"sts"})

        assert tokens[0] == {"type": "text", "value": "work"}
        assert tokens[1] == {
            "type": "abbreviation",
            "code": "sts",
            "translated": False,
            "full_name": None,
        }

    # ------------------------------------------------------------------
    # Spec examples (full-line integration)
    # ------------------------------------------------------------------

    def test_spec_example_cast_on_20_sts(self, service):
        """Spec example 1: number-before-unit consumes 'sts' as unit."""
        tokens = service._tokenize_line(
            "Cast on 20 sts on 3.5mm needles", known_codes=set()
        )

        assert tokens[0] == {"type": "text", "value": "Cast on"}
        assert tokens[1] == {
            "type": "number",
            "value": 20,
            "unit": "sts",
            "scalable": True,
        }
        assert tokens[2] == {"type": "text", "value": "on"}
        assert tokens[3] == {
            "type": "number",
            "value": 3.5,
            "unit": "mm",
            "scalable": False,
        }
        assert tokens[4] == {"type": "text", "value": "needles"}

    def test_spec_example_work_row_1(self, service):
        """Spec example 2: unit-before-number for 'row 1'."""
        tokens = service._tokenize_line("Work row 1 as follows", known_codes=set())

        assert tokens[0] == {"type": "text", "value": "Work"}
        assert tokens[1] == {
            "type": "number",
            "value": 1,
            "unit": "row",
            "scalable": True,
        }
        assert tokens[2] == {"type": "text", "value": "as follows"}

    def test_spec_example_work_in_rounds(self, service):
        """Spec example 3: no number adjacent to any unit — all text."""
        tokens = service._tokenize_line("work in rounds", known_codes=set())

        assert tokens == [{"type": "text", "value": "work in rounds"}]


# ---------------------------------------------------------------------------
# _enrich_abbreviations
# ---------------------------------------------------------------------------


class TestEnrichAbbreviations:
    def test_found_abbreviation_sets_translated_and_full_name(self, service):
        db = MagicMock()
        abbr = MagicMock()
        abbr.full_name = "stitches"

        lines = [
            {
                "line": 1,
                **_NO_FMT,
                "tokens": [
                    {
                        "type": "abbreviation",
                        "code": "sts",
                        "translated": False,
                        "full_name": None,
                    }
                ],
            }
        ]

        with patch("app.services.pattern.abbreviation_repository") as mock_repo:
            mock_repo.get_by_code.return_value = abbr
            service._enrich_abbreviations(lines, db)

        assert lines[0]["tokens"][0]["translated"] is True
        assert lines[0]["tokens"][0]["full_name"] == "stitches"

    def test_not_found_abbreviation_sets_translated_false(self, service):
        db = MagicMock()
        lines = [
            {
                "line": 1,
                **_NO_FMT,
                "tokens": [
                    {
                        "type": "abbreviation",
                        "code": "CO",
                        "translated": False,
                        "full_name": None,
                    }
                ],
            }
        ]

        with patch("app.services.pattern.abbreviation_repository") as mock_repo:
            mock_repo.get_by_code.return_value = None
            service._enrich_abbreviations(lines, db)

        assert lines[0]["tokens"][0]["translated"] is False
        assert lines[0]["tokens"][0]["full_name"] is None

    def test_non_abbreviation_tokens_are_not_touched(self, service):
        db = MagicMock()
        token = {"type": "text", "value": "Cast on"}
        lines = [{"line": 1, **_NO_FMT, "tokens": [token]}]

        with patch("app.services.pattern.abbreviation_repository") as mock_repo:
            service._enrich_abbreviations(lines, db)
            mock_repo.get_by_code.assert_not_called()

        assert lines[0]["tokens"][0]["type"] == "text"
        assert lines[0]["tokens"][0]["value"] == "Cast on"

    def test_empty_lines_are_skipped(self, service):
        db = MagicMock()
        lines = [{"line": 2, **_NO_FMT, "tokens": []}]

        with patch("app.services.pattern.abbreviation_repository") as mock_repo:
            service._enrich_abbreviations(lines, db)
            mock_repo.get_by_code.assert_not_called()
