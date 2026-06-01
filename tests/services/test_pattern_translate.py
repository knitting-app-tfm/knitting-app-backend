import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pdfminer.layout import LTChar, LTTextBox, LTTextLine

from app.models.pattern import PatternSource, PatternStatus
from app.schemas.pattern import TextSegment
from app.services.pattern import PatternNotConfirmedError, PatternService
from app.services.pattern import pattern_parser, pattern_tokenizer

_PATTERN_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

_NO_FMT = {"bold": False, "italic": False, "font_size": None}


def _seg(
    text: str, bold: bool = False, italic: bool = False, font_size: float | None = None
) -> TextSegment:
    return TextSegment(text=text, bold=bold, italic=italic, font_size=font_size)


@pytest.fixture
def service():
    with patch("app.services.pattern.pattern_service.Groq"):
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

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.get_by_id.return_value = mock_pattern
            with pytest.raises(PatternNotConfirmedError):
                service.translate(db, _PATTERN_ID)

    def test_returns_none_when_pattern_not_found(self, service):
        db = MagicMock()

        with patch(
            "app.services.pattern.pattern_service.pattern_repository"
        ) as mock_repo:
            mock_repo.get_by_id.return_value = None
            result = service.translate(db, uuid.uuid4())

        assert result is None

    def test_confirmed_pdf_tokenizes_saves_and_returns_lines(
        self, service, mock_pattern
    ):
        """AC1: CONFIRMED + PDF — tokenizes, persists file, updates status."""
        mock_pattern.status = PatternStatus.CONFIRMED
        mock_pattern.source = PatternSource.PDF
        mock_pattern.sizes = []
        db = MagicMock()

        mock_segments = [_seg("Cast on")]
        mock_lines = [
            {"line": 1, **_NO_FMT, "tokens": [{"type": "text", "value": "Cast on"}]}
        ]
        expected_path = f"storage/tokens/{_PATTERN_ID}.json"

        with (
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
            patch(
                "app.services.pattern.pattern_service.abbreviation_repository"
            ) as mock_abbr_repo,
            patch(
                "app.services.pattern.pattern_parser.read_source_text",
                return_value=mock_segments,
            ) as mock_read,
            patch(
                "app.services.pattern.pattern_tokenizer.tokenize",
                return_value=mock_lines,
            ) as mock_tok,
            patch(
                "app.services.pattern.pattern_tokenizer.enrich_abbreviations",
                return_value=mock_lines,
            ),
            patch(
                "app.services.pattern.pattern_storage.save_file",
                return_value=expected_path,
            ),
        ):
            mock_repo.get_by_id.return_value = mock_pattern
            mock_abbr_repo.get_all.return_value = []

            result = service.translate(db, _PATTERN_ID)

        mock_read.assert_called_once_with(mock_pattern)
        mock_tok.assert_called_once_with(mock_segments, set(), {}, 0)
        mock_repo.set_tokenized.assert_called_once_with(db, mock_pattern, expected_path)
        assert result == mock_lines

    def test_confirmed_text_tokenizes_saves_and_returns_lines(
        self, service, mock_pattern
    ):
        """AC6: CONFIRMED + TEXT — reads .txt file, tokenizes, persists, updates status."""
        mock_pattern.status = PatternStatus.CONFIRMED
        mock_pattern.source = PatternSource.TEXT
        mock_pattern.sizes = []
        db = MagicMock()

        mock_segments = [_seg("Work k2")]
        mock_lines = [
            {"line": 1, **_NO_FMT, "tokens": [{"type": "text", "value": "Work k2"}]}
        ]
        expected_path = f"storage/tokens/{_PATTERN_ID}.json"

        with (
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
            patch(
                "app.services.pattern.pattern_service.abbreviation_repository"
            ) as mock_abbr_repo,
            patch(
                "app.services.pattern.pattern_parser.read_source_text",
                return_value=mock_segments,
            ) as mock_read,
            patch(
                "app.services.pattern.pattern_tokenizer.tokenize",
                return_value=mock_lines,
            ),
            patch(
                "app.services.pattern.pattern_tokenizer.enrich_abbreviations",
                return_value=mock_lines,
            ),
            patch(
                "app.services.pattern.pattern_storage.save_file",
                return_value=expected_path,
            ),
        ):
            mock_repo.get_by_id.return_value = mock_pattern
            mock_abbr_repo.get_all.return_value = []

            result = service.translate(db, _PATTERN_ID)

        mock_read.assert_called_once_with(mock_pattern)
        mock_repo.set_tokenized.assert_called_once_with(db, mock_pattern, expected_path)
        assert result == mock_lines

    def test_tokenized_reuses_disk_without_retokenizing(self, service, mock_pattern):
        """AC2: TOKENIZED status — reads from disk, never calls tokenize."""
        mock_pattern.status = PatternStatus.TOKENIZED
        mock_pattern.tokens_file_path = f"storage/tokens/{_PATTERN_ID}.json"
        db = MagicMock()

        stored_lines = [
            {"line": 1, **_NO_FMT, "tokens": []},
            {"line": 2, **_NO_FMT, "tokens": []},
        ]

        with (
            patch(
                "app.services.pattern.pattern_service.pattern_repository"
            ) as mock_repo,
            patch("app.services.pattern.pattern_tokenizer.tokenize") as mock_tok,
            patch(
                "app.services.pattern.pattern_storage.read_tokens_file",
                return_value=stored_lines,
            ),
            patch(
                "app.services.pattern.pattern_tokenizer.enrich_abbreviations",
                return_value=stored_lines,
            ),
        ):
            mock_repo.get_by_id.return_value = mock_pattern

            result = service.translate(db, _PATTERN_ID)

        mock_tok.assert_not_called()
        assert result == stored_lines


# ---------------------------------------------------------------------------
# _read_source_text (now pattern_parser.read_source_text)
# ---------------------------------------------------------------------------


class TestReadSourceText:
    def test_pdf_extracts_segments_with_formatting(self):
        pattern = MagicMock()
        pattern.source = PatternSource.PDF
        pattern.original_file_path = f"storage/original/{_PATTERN_ID}.pdf"

        mock_segments = [_seg("Cast on\n", bold=True, font_size=12.0)]

        with patch(
            "app.services.pattern.pattern_parser.extract_segments_from_pdf",
            return_value=mock_segments,
        ) as mock_extract:
            result = pattern_parser.read_source_text(pattern)

        assert result is mock_segments
        assert mock_extract.call_count == 1

    def test_text_produces_one_segment_per_line(self):
        pattern = MagicMock()
        pattern.source = PatternSource.TEXT
        pattern.original_file_path = f"storage/original/{_PATTERN_ID}.txt"

        with patch("pathlib.Path.read_text", return_value="line one\nline two"):
            result = pattern_parser.read_source_text(pattern)

        assert len(result) == 2
        assert result[0] == TextSegment(
            text="line one", bold=False, italic=False, font_size=None
        )
        assert result[1] == TextSegment(
            text="line two", bold=False, italic=False, font_size=None
        )

    def test_text_trailing_newline_produces_empty_last_segment(self):
        pattern = MagicMock()
        pattern.source = PatternSource.TEXT
        pattern.original_file_path = f"storage/original/{_PATTERN_ID}.txt"

        with patch("pathlib.Path.read_text", return_value="only line\n"):
            result = pattern_parser.read_source_text(pattern)

        assert len(result) == 2
        assert result[1] == TextSegment(
            text="", bold=False, italic=False, font_size=None
        )

    def test_text_segments_have_no_formatting(self):
        pattern = MagicMock()
        pattern.source = PatternSource.TEXT
        pattern.original_file_path = f"storage/original/{_PATTERN_ID}.txt"

        with patch("pathlib.Path.read_text", return_value="CO 20 sts"):
            result = pattern_parser.read_source_text(pattern)

        seg = result[0]
        assert seg.bold is False
        assert seg.italic is False
        assert seg.font_size is None


# ---------------------------------------------------------------------------
# tokenize (line-by-line structure + formatting propagation)
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_empty_segments_produce_empty_token_lists(self):
        segments = [_seg("Line one"), _seg(""), _seg("Line three")]
        result = pattern_tokenizer.tokenize(
            segments, known_codes=set(), known_full_names={}
        )

        assert len(result) == 3
        assert result[0] == {
            "line": 1,
            **_NO_FMT,
            "tokens": [{"type": "text", "value": "Line one"}],
        }
        assert result[1] == {"line": 2, **_NO_FMT, "tokens": []}
        assert result[2]["line"] == 3
        assert result[2]["tokens"] != []

    def test_line_numbers_are_one_indexed_and_sequential(self):
        segments = [_seg("a"), _seg(""), _seg("b")]
        result = pattern_tokenizer.tokenize(
            segments, known_codes=set(), known_full_names={}
        )

        assert [r["line"] for r in result] == [1, 2, 3]

    def test_empty_last_segment_maps_to_empty_line(self):
        segments = [_seg("only line"), _seg("")]
        result = pattern_tokenizer.tokenize(
            segments, known_codes=set(), known_full_names={}
        )

        assert len(result) == 2
        assert result[1]["line"] == 2
        assert result[1]["tokens"] == []

    def test_formatting_is_set_on_line_dict(self):
        segments = [_seg("Cast on", bold=True, italic=False, font_size=14.0)]
        result = pattern_tokenizer.tokenize(
            segments, known_codes=set(), known_full_names={}
        )

        line = result[0]
        assert line["bold"] is True
        assert line["italic"] is False
        assert line["font_size"] == 14.0

    def test_formatting_is_not_duplicated_on_tokens(self):
        segments = [_seg("20 sts", bold=False, italic=True, font_size=10.0)]
        result = pattern_tokenizer.tokenize(
            segments, known_codes={"sts"}, known_full_names={}
        )

        for token in result[0]["tokens"]:
            assert "bold" not in token
            assert "italic" not in token
            assert "font_size" not in token

    def test_line_dict_includes_formatting_fields(self):
        segments = [_seg("work in rounds", bold=False, italic=False, font_size=12.5)]
        result = pattern_tokenizer.tokenize(
            segments, known_codes=set(), known_full_names={}
        )

        line = result[0]
        assert "bold" in line
        assert "italic" in line
        assert "font_size" in line
        assert line["font_size"] == 12.5

    def test_empty_line_formatting_is_preserved(self):
        segments = [_seg(""), _seg("")]
        result = pattern_tokenizer.tokenize(
            segments, known_codes=set(), known_full_names={}
        )

        for line in result:
            assert "bold" in line
            assert "italic" in line
            assert "font_size" in line

    def test_different_lines_have_independent_formatting(self):
        segments = [
            _seg("Bold line", bold=True, font_size=16.0),
            _seg("Normal line", bold=False, font_size=10.0),
        ]
        result = pattern_tokenizer.tokenize(
            segments, known_codes=set(), known_full_names={}
        )

        assert result[0]["bold"] is True
        assert result[0]["font_size"] == 16.0

        assert result[1]["bold"] is False
        assert result[1]["font_size"] == 10.0


# ---------------------------------------------------------------------------
# tokenize_line — token type detection
# ---------------------------------------------------------------------------


class TestTokenizeLine:
    def test_adjacent_plain_words_merge_into_single_text_token(self):
        tokens = pattern_tokenizer.tokenize_line(
            "Cast on", known_codes=set(), known_full_names={}
        )

        assert tokens == [{"type": "text", "value": "Cast on"}]

    def test_abbreviation_splits_surrounding_text(self):
        tokens = pattern_tokenizer.tokenize_line(
            "Work sts here", known_codes={"sts"}, known_full_names={}
        )

        assert tokens[0] == {"type": "text", "value": "Work"}
        assert tokens[1]["type"] == "abbreviation"
        assert tokens[1]["code"] == "sts"
        assert tokens[2] == {"type": "text", "value": "here"}

    def test_size_group_extracts_values_and_peeks_unit(self):
        tokens = pattern_tokenizer.tokenize_line(
            "Cast on 147 (159) 174 sts", known_codes={"sts"}, known_full_names={}
        )

        sg = next(t for t in tokens if t["type"] == "size_group")
        assert sg["values"] == [147, 159, 174]
        assert sg["unit"] == "sts"
        assert sg["scalable"] is True

    def test_size_group_does_not_consume_following_abbreviation(self):
        """The unit-peek must not remove the abbreviation token from the stream."""
        tokens = pattern_tokenizer.tokenize_line(
            "147 (159) 174 sts", known_codes={"sts"}, known_full_names={}
        )

        types = [t["type"] for t in tokens]
        assert "size_group" in types
        assert "abbreviation" in types

    def test_number_with_non_scalable_unit(self):
        tokens = pattern_tokenizer.tokenize_line(
            "3.5mm", known_codes=set(), known_full_names={}
        )

        assert tokens == [
            {"type": "number", "value": 3.5, "unit": "mm", "scalable": False}
        ]

    def test_number_with_scalable_unit(self):
        tokens = pattern_tokenizer.tokenize_line(
            "11 rounds", known_codes=set(), known_full_names={}
        )

        assert tokens == [
            {"type": "number", "value": 11, "unit": "rounds", "scalable": True}
        ]

    def test_number_unit_is_consumed_not_duplicated(self):
        """'rounds' consumed as number unit must not also appear as a text token."""
        tokens = pattern_tokenizer.tokenize_line(
            "11 rounds", known_codes=set(), known_full_names={}
        )

        assert len(tokens) == 1
        assert tokens[0]["type"] == "number"

    def test_bare_number_has_no_unit(self):
        tokens = pattern_tokenizer.tokenize_line(
            "5", known_codes=set(), known_full_names={}
        )

        assert tokens == [
            {"type": "number", "value": 5, "unit": None, "scalable": False}
        ]

    def test_whole_number_value_serializes_as_int(self):
        tokens = pattern_tokenizer.tokenize_line(
            "11 rows", known_codes=set(), known_full_names={}
        )

        assert isinstance(tokens[0]["value"], int)

    def test_decimal_number_value_is_float(self):
        tokens = pattern_tokenizer.tokenize_line(
            "3.5mm", known_codes=set(), known_full_names={}
        )

        assert isinstance(tokens[0]["value"], float)

    def test_punctuation_is_dropped(self):
        tokens = pattern_tokenizer.tokenize_line(
            "k2, p1", known_codes={"k2", "p1"}, known_full_names={}
        )

        assert all(t["type"] == "abbreviation" for t in tokens)
        assert len(tokens) == 2

    def test_abbreviation_matching_is_case_insensitive(self):
        tokens = pattern_tokenizer.tokenize_line(
            "CO", known_codes={"co"}, known_full_names={}
        )

        assert tokens[0]["type"] == "abbreviation"
        assert tokens[0]["code"] == "CO"

    def test_number_unit_stored_as_raw_keyword(self):
        """Unit is stored exactly as it appears in the text, never canonicalised."""
        tokens = pattern_tokenizer.tokenize_line(
            "5 sts", known_codes=set(), known_full_names={}
        )

        assert tokens[0]["unit"] == "sts"

    def test_full_line_example(self):
        """Integration: the spec's reference line produces the expected token sequence."""
        known = {"sts"}
        tokens = pattern_tokenizer.tokenize_line(
            "Cast on 147 (159) 174 sts on 3.5mm needles",
            known_codes=known,
            known_full_names={},
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

    def test_unit_before_number_scalable(self):
        tokens = pattern_tokenizer.tokenize_line(
            "row 1", known_codes=set(), known_full_names={}
        )

        assert tokens == [
            {"type": "number", "value": 1, "unit": "row", "scalable": True}
        ]

    def test_unit_before_number_in_sentence(self):
        """Spec example 2: 'Work row 1 as follows'."""
        tokens = pattern_tokenizer.tokenize_line(
            "Work row 1 as follows", known_codes=set(), known_full_names={}
        )

        assert tokens[0] == {"type": "text", "value": "Work"}
        assert tokens[1] == {
            "type": "number",
            "value": 1,
            "unit": "row",
            "scalable": True,
        }
        assert tokens[2] == {"type": "text", "value": "as follows"}

    def test_unit_before_number_plural_form(self):
        tokens = pattern_tokenizer.tokenize_line(
            "round 2", known_codes=set(), known_full_names={}
        )

        assert tokens == [
            {"type": "number", "value": 2, "unit": "round", "scalable": True}
        ]

    def test_unit_before_number_consumes_both_unit_and_number(self):
        tokens = pattern_tokenizer.tokenize_line(
            "row 5", known_codes=set(), known_full_names={}
        )

        assert len(tokens) == 1
        assert tokens[0]["type"] == "number"

    # ------------------------------------------------------------------
    # Unit keyword without adjacent number (Case 3)
    # ------------------------------------------------------------------

    def test_unit_keyword_without_adjacent_number_becomes_text(self):
        """Spec example 3: 'work in rounds' — no number adjacent to any unit word."""
        tokens = pattern_tokenizer.tokenize_line(
            "work in rounds", known_codes=set(), known_full_names={}
        )

        assert tokens == [{"type": "text", "value": "work in rounds"}]

    def test_unit_keyword_between_text_words_is_not_consumed(self):
        tokens = pattern_tokenizer.tokenize_line(
            "work in rows", known_codes=set(), known_full_names={}
        )

        assert tokens == [{"type": "text", "value": "work in rows"}]

    def test_unit_keyword_without_number_becomes_abbreviation_when_in_known_codes(
        self,
    ):
        """'sts' with no adjacent number falls through to the abbreviation path."""
        tokens = pattern_tokenizer.tokenize_line(
            "work sts", known_codes={"sts"}, known_full_names={}
        )

        assert tokens[0] == {"type": "text", "value": "work"}
        assert tokens[1] == {
            "type": "abbreviation",
            "code": "sts",
            "translated": False,
            "full_name": None,
            "quantity": None,
        }

    # ------------------------------------------------------------------
    # Spec examples (full-line integration)
    # ------------------------------------------------------------------

    def test_spec_example_cast_on_20_sts(self):
        """Spec example 1: number-before-unit consumes 'sts' as unit."""
        tokens = pattern_tokenizer.tokenize_line(
            "Cast on 20 sts on 3.5mm needles", known_codes=set(), known_full_names={}
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

    def test_spec_example_work_row_1(self):
        """Spec example 2: unit-before-number for 'row 1'."""
        tokens = pattern_tokenizer.tokenize_line(
            "Work row 1 as follows", known_codes=set(), known_full_names={}
        )

        assert tokens[0] == {"type": "text", "value": "Work"}
        assert tokens[1] == {
            "type": "number",
            "value": 1,
            "unit": "row",
            "scalable": True,
        }
        assert tokens[2] == {"type": "text", "value": "as follows"}

    def test_spec_example_work_in_rounds(self):
        """Spec example 3: no number adjacent to any unit — all text."""
        tokens = pattern_tokenizer.tokenize_line(
            "work in rounds", known_codes=set(), known_full_names={}
        )

        assert tokens == [{"type": "text", "value": "work in rounds"}]


# ---------------------------------------------------------------------------
# enrich_abbreviations (now pattern_tokenizer.enrich_abbreviations)
# ---------------------------------------------------------------------------


class TestEnrichAbbreviations:
    def test_found_abbreviation_sets_translated_and_full_name(self):
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
                        "quantity": None,
                    }
                ],
            }
        ]

        with patch(
            "app.services.pattern.pattern_tokenizer.abbreviation_repository"
        ) as mock_repo:
            mock_repo.get_by_code.return_value = abbr
            pattern_tokenizer.enrich_abbreviations(lines, db)

        assert lines[0]["tokens"][0]["translated"] is True
        assert lines[0]["tokens"][0]["full_name"] == "stitches"

    def test_not_found_abbreviation_sets_translated_false(self):
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
                        "quantity": None,
                    }
                ],
            }
        ]

        with patch(
            "app.services.pattern.pattern_tokenizer.abbreviation_repository"
        ) as mock_repo:
            mock_repo.get_by_code.return_value = None
            pattern_tokenizer.enrich_abbreviations(lines, db)

        assert lines[0]["tokens"][0]["translated"] is False
        assert lines[0]["tokens"][0]["full_name"] is None

    def test_non_abbreviation_tokens_are_not_touched(self):
        db = MagicMock()
        token = {"type": "text", "value": "Cast on"}
        lines = [{"line": 1, **_NO_FMT, "tokens": [token]}]

        with patch(
            "app.services.pattern.pattern_tokenizer.abbreviation_repository"
        ) as mock_repo:
            pattern_tokenizer.enrich_abbreviations(lines, db)
            mock_repo.get_by_code.assert_not_called()

        assert lines[0]["tokens"][0]["type"] == "text"
        assert lines[0]["tokens"][0]["value"] == "Cast on"

    def test_empty_lines_are_skipped(self):
        db = MagicMock()
        lines = [{"line": 2, **_NO_FMT, "tokens": []}]

        with patch(
            "app.services.pattern.pattern_tokenizer.abbreviation_repository"
        ) as mock_repo:
            pattern_tokenizer.enrich_abbreviations(lines, db)
            mock_repo.get_by_code.assert_not_called()

    def test_suffixed_code_falls_back_to_alpha_prefix(self):
        """code 'k2' not in DB, but alpha prefix 'k' is."""
        db = MagicMock()
        abbr = MagicMock()
        abbr.full_name = "knit"
        lines = [
            {
                "line": 1,
                **_NO_FMT,
                "tokens": [
                    {
                        "type": "abbreviation",
                        "code": "k2",
                        "translated": False,
                        "full_name": None,
                        "quantity": None,
                    }
                ],
            }
        ]

        with patch(
            "app.services.pattern.pattern_tokenizer.abbreviation_repository"
        ) as mock_repo:
            mock_repo.get_by_code.side_effect = lambda _db, code: (
                abbr if code == "k" else None
            )
            pattern_tokenizer.enrich_abbreviations(lines, db)

        assert lines[0]["tokens"][0]["translated"] is True
        assert lines[0]["tokens"][0]["full_name"] == "knit"

    def test_suffixed_code_with_no_matching_prefix_stays_untranslated(self):
        db = MagicMock()
        lines = [
            {
                "line": 1,
                **_NO_FMT,
                "tokens": [
                    {
                        "type": "abbreviation",
                        "code": "xyz2",
                        "translated": False,
                        "full_name": None,
                        "quantity": None,
                    }
                ],
            }
        ]

        with patch(
            "app.services.pattern.pattern_tokenizer.abbreviation_repository"
        ) as mock_repo:
            mock_repo.get_by_code.return_value = None
            pattern_tokenizer.enrich_abbreviations(lines, db)

        assert lines[0]["tokens"][0]["translated"] is False
        assert lines[0]["tokens"][0]["full_name"] is None

    def test_quantity_is_appended_to_full_name(self):
        """Fix 4: when token has quantity, full_name = f'{abbr.full_name} {quantity}'."""
        db = MagicMock()
        abbr = MagicMock()
        abbr.full_name = "knit"
        lines = [
            {
                "line": 1,
                **_NO_FMT,
                "tokens": [
                    {
                        "type": "abbreviation",
                        "code": "k2",
                        "translated": False,
                        "full_name": None,
                        "quantity": 2,
                    }
                ],
            }
        ]

        with patch(
            "app.services.pattern.pattern_tokenizer.abbreviation_repository"
        ) as mock_repo:
            mock_repo.get_by_code.side_effect = lambda _db, code: (
                abbr if code in ("k2", "k") else None
            )
            pattern_tokenizer.enrich_abbreviations(lines, db)

        assert lines[0]["tokens"][0]["full_name"] == "knit 2"
        assert lines[0]["tokens"][0]["translated"] is True


# ---------------------------------------------------------------------------
# tokenize_line — full-name matching (Case 1)
# ---------------------------------------------------------------------------


class TestTokenizeLineFullNameMatching:
    def test_full_name_match_emits_abbreviation_token(self):
        """Spec example: 'knit 2 together' matched before 'knit'."""
        tokens = pattern_tokenizer.tokenize_line(
            "knit 2 together on 3.5mm needles",
            known_codes={"k2tog"},
            known_full_names={"knit 2 together": "k2tog", "knit": "k"},
        )

        assert tokens[0] == {
            "type": "abbreviation",
            "code": "k2tog",
            "translated": False,
            "full_name": None,
            "quantity": None,
        }
        assert tokens[1] == {"type": "text", "value": "on"}
        assert tokens[2] == {
            "type": "number",
            "value": 3.5,
            "unit": "mm",
            "scalable": False,
        }
        assert tokens[3] == {"type": "text", "value": "needles"}

    def test_longer_full_name_takes_priority_over_shorter(self):
        tokens = pattern_tokenizer.tokenize_line(
            "knit 2 together please",
            known_codes={"k2tog", "k"},
            known_full_names={"knit 2 together": "k2tog", "knit": "k"},
        )

        assert tokens[0]["code"] == "k2tog"
        assert len([t for t in tokens if t["type"] == "abbreviation"]) == 1

    def test_full_name_match_is_case_insensitive(self):
        tokens = pattern_tokenizer.tokenize_line(
            "KNIT 2 TOGETHER",
            known_codes={"k2tog"},
            known_full_names={"knit 2 together": "k2tog"},
        )

        assert tokens[0]["type"] == "abbreviation"
        assert tokens[0]["code"] == "k2tog"

    def test_full_name_not_matched_inside_longer_word(self):
        """'knit' should not match inside 'knitting' (word-boundary guard)."""
        tokens = pattern_tokenizer.tokenize_line(
            "knitting",
            known_codes=set(),
            known_full_names={"knit": "k"},
        )

        assert tokens == [{"type": "text", "value": "knitting"}]

    def test_full_name_match_mid_line_splits_surrounding_text(self):
        tokens = pattern_tokenizer.tokenize_line(
            "work knit 2 together here",
            known_codes={"k2tog"},
            known_full_names={"knit 2 together": "k2tog"},
        )

        assert tokens[0] == {"type": "text", "value": "work"}
        assert tokens[1]["type"] == "abbreviation"
        assert tokens[1]["code"] == "k2tog"
        assert tokens[2] == {"type": "text", "value": "here"}

    def test_empty_known_full_names_skips_full_name_scan(self):
        tokens = pattern_tokenizer.tokenize_line(
            "Cast on", known_codes=set(), known_full_names={}
        )

        assert tokens == [{"type": "text", "value": "Cast on"}]


# ---------------------------------------------------------------------------
# tokenize_line — suffixed abbreviation (Case 2 / Fix 3)
# ---------------------------------------------------------------------------


class TestTokenizeLineSuffixedAbbreviation:
    def test_suffixed_word_emits_abbreviation_with_quantity(self):
        """k2 alone (no following size group) → abbreviation with code='k2', quantity=2."""
        tokens = pattern_tokenizer.tokenize_line(
            "k2 p1 on 3.5mm needles",
            known_codes={"k", "p"},
            known_full_names={},
        )

        assert tokens[0] == {
            "type": "abbreviation",
            "code": "k2",
            "translated": False,
            "full_name": None,
            "quantity": 2,
        }
        assert tokens[1] == {
            "type": "abbreviation",
            "code": "p1",
            "translated": False,
            "full_name": None,
            "quantity": 1,
        }
        assert tokens[2] == {"type": "text", "value": "on"}
        assert tokens[3] == {
            "type": "number",
            "value": 3.5,
            "unit": "mm",
            "scalable": False,
        }
        assert tokens[4] == {"type": "text", "value": "needles"}

    def test_suffixed_word_not_matched_when_prefix_unknown(self):
        """'xyz2' with unknown prefix 'xyz' must not become an abbreviation."""
        tokens = pattern_tokenizer.tokenize_line(
            "xyz2", known_codes={"k"}, known_full_names={}
        )

        assert tokens == [{"type": "text", "value": "xyz2"}]

    def test_exact_match_takes_priority_over_suffix_match(self):
        """When 'k2' is directly in known_codes it is matched before suffix logic."""
        tokens = pattern_tokenizer.tokenize_line(
            "k2", known_codes={"k2", "k"}, known_full_names={}
        )

        assert tokens[0]["type"] == "abbreviation"
        assert tokens[0]["code"] == "k2"

    def test_word_ending_in_non_digit_is_not_a_suffixed_abbr(self):
        """'k2tog' ends in 'g', so suffix rule does not apply; it needs a direct code match."""
        tokens = pattern_tokenizer.tokenize_line(
            "k2tog", known_codes={"k"}, known_full_names={}
        )

        assert tokens == [{"type": "text", "value": "k2tog"}]

    def test_suffixed_match_is_case_insensitive_on_prefix(self):
        tokens = pattern_tokenizer.tokenize_line(
            "K2", known_codes={"k"}, known_full_names={}
        )

        assert tokens[0]["type"] == "abbreviation"
        assert tokens[0]["code"] == "K2"

    def test_suffixed_split_when_digits_plus_parens_form_valid_size_group(self):
        """K23 (24, 25) with num_sizes=3 → abbreviation 'K' + size_group [23, 24, 25]."""
        tokens = pattern_tokenizer.tokenize_line(
            "K23 (24, 25)",
            known_codes={"k"},
            known_full_names={},
            num_sizes=3,
        )

        assert tokens[0] == {
            "type": "abbreviation",
            "code": "K",
            "translated": False,
            "full_name": None,
            "quantity": None,
        }
        assert tokens[1]["type"] == "size_group"
        assert tokens[1]["values"] == [23, 24, 25]

    def test_suffixed_no_split_when_size_group_count_mismatch(self):
        """K23 (24, 25) with num_sizes=2 → count 3 ≠ 2 → no split, full code K23 with quantity."""
        tokens = pattern_tokenizer.tokenize_line(
            "K23 (24, 25)",
            known_codes={"k"},
            known_full_names={},
            num_sizes=2,
        )

        assert tokens[0]["code"] == "K23"
        assert tokens[0].get("quantity") == 23


# ---------------------------------------------------------------------------
# Size group regex fixes (Fix 1 + Fix 2)
# ---------------------------------------------------------------------------


class TestSizeGroupFixes:
    def test_comma_separated_values_in_parentheses(self):
        """Fix 1: '23 (24, 25, 27)' → single size_group with 4 values."""
        tokens = pattern_tokenizer.tokenize_line(
            "23 (24, 25, 27)", known_codes=set(), known_full_names={}
        )

        sg = next(t for t in tokens if t["type"] == "size_group")
        assert sg["values"] == [23, 24, 25, 27]

    def test_alternating_bare_and_parenthesised(self):
        """Fix 1: '35 (41) 47' → size_group with 3 values."""
        tokens = pattern_tokenizer.tokenize_line(
            "35 (41) 47", known_codes=set(), known_full_names={}
        )

        sg = next(t for t in tokens if t["type"] == "size_group")
        assert sg["values"] == [35, 41, 47]

    def test_mixed_parens_and_square_brackets(self):
        """Fix 1: '(4, 4, 4)[2, 2, 4]' → size_group with 6 values."""
        tokens = pattern_tokenizer.tokenize_line(
            "(4, 4, 4)[2, 2, 4]", known_codes=set(), known_full_names={}
        )

        sg = next(t for t in tokens if t["type"] == "size_group")
        assert sg["values"] == [4, 4, 4, 2, 2, 4]

    def test_decimal_values_in_size_group(self):
        """Fix 1: '1.5 (1.5) 2 (2)' → size_group with decimal values."""
        tokens = pattern_tokenizer.tokenize_line(
            "1.5 (1.5) 2 (2)", known_codes=set(), known_full_names={}
        )

        sg = next(t for t in tokens if t["type"] == "size_group")
        assert sg["values"] == [1.5, 1.5, 2, 2]

    def test_size_group_accepted_when_count_matches_num_sizes(self):
        """Fix 2: size group accepted when value count == num_sizes."""
        tokens = pattern_tokenizer.tokenize_line(
            "23 (24, 25, 27)",
            known_codes=set(),
            known_full_names={},
            num_sizes=4,
        )

        assert any(t["type"] == "size_group" for t in tokens)

    def test_size_group_rejected_when_count_mismatches_num_sizes(self):
        """Fix 2: size group NOT accepted when value count ≠ num_sizes."""
        tokens = pattern_tokenizer.tokenize_line(
            "23 (24, 25, 27)",
            known_codes=set(),
            known_full_names={},
            num_sizes=2,
        )

        assert not any(t["type"] == "size_group" for t in tokens)

    def test_size_group_accepted_with_num_sizes_zero(self):
        """num_sizes=0 (default) means no validation — accept any size group."""
        tokens = pattern_tokenizer.tokenize_line(
            "147 (159) 174", known_codes=set(), known_full_names={}, num_sizes=0
        )

        assert any(t["type"] == "size_group" for t in tokens)


# ---------------------------------------------------------------------------
# extract_segments_from_pdf — pdfminer integration
# ---------------------------------------------------------------------------


def _make_mock_line(text: str, fontname: str, font_size: float):
    """Build a mock LTTextLine whose first LTChar has the given font attributes."""
    char = MagicMock()
    char.__class__ = LTChar
    char.fontname = fontname
    char.size = font_size

    line = MagicMock()
    line.__class__ = LTTextLine
    line.__iter__ = lambda self: iter([char])
    line.get_text.return_value = text
    return line


def _make_mock_line_no_chars(text: str):
    """Build a mock LTTextLine with no LTChar children (triggers the else branch)."""
    line = MagicMock()
    line.__class__ = LTTextLine
    line.__iter__ = lambda self: iter([])  # no LTChar objects
    line.get_text.return_value = text
    return line


def _make_page(*lines):
    """Wrap lines in a mock LTTextBox inside a mock page layout."""
    box = MagicMock()
    box.__class__ = LTTextBox
    box.__iter__ = lambda self: iter(lines)

    page = MagicMock()
    page.__iter__ = lambda self: iter([box])
    return page


class TestExtractSegmentsFromPdf:
    def test_extracts_text_and_bold_flag(self):
        page = _make_page(_make_mock_line("Cast on\n", "Arial-Bold", 12.0))

        with patch(
            "app.services.pattern.pattern_parser.extract_pages", return_value=[page]
        ):
            result = pattern_parser.extract_segments_from_pdf(Path("fake.pdf"))

        assert len(result) == 1
        assert result[0].text == "Cast on\n"
        assert result[0].bold is True
        assert result[0].font_size == 12.0

    def test_extracts_italic_flag(self):
        page = _make_page(_make_mock_line("Note\n", "Times-Italic", 10.0))

        with patch(
            "app.services.pattern.pattern_parser.extract_pages", return_value=[page]
        ):
            result = pattern_parser.extract_segments_from_pdf(Path("fake.pdf"))

        assert result[0].italic is True
        assert result[0].bold is False

    def test_non_bold_non_italic_font(self):
        page = _make_page(_make_mock_line("Plain\n", "Arial", 11.0))

        with patch(
            "app.services.pattern.pattern_parser.extract_pages", return_value=[page]
        ):
            result = pattern_parser.extract_segments_from_pdf(Path("fake.pdf"))

        assert result[0].bold is False
        assert result[0].italic is False

    def test_line_with_no_chars_gets_default_formatting(self):
        page = _make_page(_make_mock_line_no_chars("empty-char line\n"))

        with patch(
            "app.services.pattern.pattern_parser.extract_pages", return_value=[page]
        ):
            result = pattern_parser.extract_segments_from_pdf(Path("fake.pdf"))

        assert result[0].bold is False
        assert result[0].italic is False
        assert result[0].font_size is None

    def test_multiple_lines_across_pages(self):
        page1 = _make_page(_make_mock_line("Line 1\n", "Arial", 10.0))
        page2 = _make_page(_make_mock_line("Line 2\n", "Arial-Bold", 12.0))

        with patch(
            "app.services.pattern.pattern_parser.extract_pages",
            return_value=[page1, page2],
        ):
            result = pattern_parser.extract_segments_from_pdf(Path("fake.pdf"))

        assert len(result) == 2
        assert result[0].text == "Line 1\n"
        assert result[1].bold is True

    def test_empty_pdf_returns_no_segments(self):
        page = MagicMock()
        page.__iter__ = lambda self: iter([])  # no LTTextBox

        with patch(
            "app.services.pattern.pattern_parser.extract_pages", return_value=[page]
        ):
            result = pattern_parser.extract_segments_from_pdf(Path("fake.pdf"))

        assert result == []
