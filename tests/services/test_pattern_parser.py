from app.schemas.pattern import TextSegment
from app.services.pattern.pattern_parser import _join_split_groups


def _seg(text: str) -> TextSegment:
    return TextSegment(text=text, bold=False, italic=False, font_size=12)


class TestJoinSplitGroups:
    def test_no_merge_needed(self):
        lines = [_seg("Cast on 88 stitches."), _seg("Work in rib for 2 cm.")]
        result = _join_split_groups(lines)
        assert len(result) == 2
        assert result[0].text == "Cast on 88 stitches."
        assert result[1].text == "Work in rib for 2 cm."

    def test_merges_unmatched_open_paren(self):
        lines = [_seg("68 (74, 76,"), _seg("80, 84) stitches")]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "68 (74, 76, 80, 84) stitches"

    def test_merges_trailing_digit_before_size_group(self):
        lines = [_seg("CO 10"), _seg("(10, 14, 18) sts")]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "CO 10 (10, 14, 18) sts"

    def test_does_not_merge_trailing_digit_before_label(self):
        lines = [_seg("Row 1"), _seg("(RS): knit all sts")]
        result = _join_split_groups(lines)
        assert len(result) == 2

    # --- new: unit keyword on next line ---

    def test_merges_unit_keyword_stitches_on_next_line(self):
        lines = [
            _seg("Cast on 88 (98, 105, 111, 114)"),
            _seg("stitches for back."),
        ]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "Cast on 88 (98, 105, 111, 114) stitches for back."

    def test_merges_unit_keyword_sts_on_next_line(self):
        lines = [_seg("Cast on 20 (24, 28)"), _seg("sts, pm.")]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "Cast on 20 (24, 28) sts, pm."

    def test_merges_unit_keyword_rows_on_next_line(self):
        lines = [_seg("Work 10 (12, 14)"), _seg("rows in pattern.")]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "Work 10 (12, 14) rows in pattern."

    def test_merges_unit_keyword_rounds_on_next_line(self):
        lines = [_seg("Work 6 (8, 10)"), _seg("rounds.")]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "Work 6 (8, 10) rounds."

    def test_merges_unit_keyword_mm_on_next_line(self):
        lines = [_seg("Using needles 3.5 (4.0, 4.5)"), _seg("mm.")]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "Using needles 3.5 (4.0, 4.5) mm."

    def test_merges_unit_keyword_cm_on_next_line(self):
        lines = [
            _seg("Work until piece measures 20 (22, 24)"),
            _seg("cm from cast-on."),
        ]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert (
            result[0].text == "Work until piece measures 20 (22, 24) cm from cast-on."
        )

    def test_merges_unit_keyword_case_insensitive(self):
        lines = [_seg("Cast on 10 (12, 14)"), _seg("Stitches, then join.")]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "Cast on 10 (12, 14) Stitches, then join."

    def test_does_not_merge_close_paren_followed_by_non_unit(self):
        lines = [_seg("Work (RS)"), _seg("turn.")]
        result = _join_split_groups(lines)
        assert len(result) == 2

    def test_does_not_merge_close_paren_followed_by_unit_word_embedded(self):
        # "stitching" starts with "st" prefix but is not a standalone unit keyword
        lines = [_seg("Continue (pattern)"), _seg("stitching as set.")]
        result = _join_split_groups(lines)
        # "stitching" matches "st" + "itching" — "st" followed by non-boundary char
        # so should NOT merge
        assert len(result) == 2

    def test_multiple_consecutive_merges(self):
        lines = [
            _seg("68 (74,"),
            _seg("76, 80)"),
            _seg("stitches total."),
        ]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "68 (74, 76, 80) stitches total."

    def test_preserves_formatting_from_first_segment(self):
        lines = [
            TextSegment(text="Cast on 10 (12)", bold=True, italic=False, font_size=14),
            TextSegment(text="sts.", bold=False, italic=True, font_size=12),
        ]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].bold is True
        assert result[0].italic is False
        assert result[0].font_size == 14

    def test_empty_input(self):
        assert _join_split_groups([]) == []

    def test_single_segment_unchanged(self):
        lines = [_seg("Cast on 20 sts.")]
        result = _join_split_groups(lines)
        assert len(result) == 1
        assert result[0].text == "Cast on 20 sts."
