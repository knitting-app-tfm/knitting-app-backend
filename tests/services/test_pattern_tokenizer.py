from app.services.pattern.pattern_tokenizer import tokenize_line


def _tok(line: str, num_sizes: int = 0) -> list[dict]:
    return tokenize_line(
        line, known_codes=set(), known_full_names={}, num_sizes=num_sizes
    )


class TestInchDetection:
    # --- bare number + inch mark ---

    def test_number_double_quote(self):
        tokens = _tok('4"')
        assert len(tokens) == 1
        assert tokens[0]["type"] == "number"
        assert tokens[0]["value"] == 4
        assert tokens[0]["unit"] == "inch"
        assert tokens[0]["scalable"] is False

    def test_number_two_single_quotes(self):
        # '' is normalized to " so both representations produce the same unit value
        tokens = _tok("4''")
        assert len(tokens) == 1
        assert tokens[0]["type"] == "number"
        assert tokens[0]["value"] == 4
        assert tokens[0]["unit"] == "inch"
        assert tokens[0]["scalable"] is False

    def test_decimal_number_double_quote(self):
        tokens = _tok('13.5"')
        assert len(tokens) == 1
        assert tokens[0]["value"] == 13.5
        assert tokens[0]["unit"] == "inch"

    def test_number_double_quote_with_space(self):
        tokens = _tok('4 "')
        assert len(tokens) == 1
        assert tokens[0]["value"] == 4
        assert tokens[0]["unit"] == "inch"

    # --- size_group + inch mark ---

    def test_size_group_double_quote(self):
        # 13.5 (15, 16.5, 18, 19.5)" — 5 sizes
        tokens = _tok('13.5 (15, 16.5, 18, 19.5)"', num_sizes=5)
        assert len(tokens) == 1
        t = tokens[0]
        assert t["type"] == "size_group"
        assert t["values"] == [13.5, 15, 16.5, 18, 19.5]
        assert t["unit"] == "inch"

    def test_size_group_two_single_quotes(self):
        tokens = _tok("13.5 (15, 16.5, 18, 19.5)''", num_sizes=5)
        assert len(tokens) == 1
        t = tokens[0]
        assert t["type"] == "size_group"
        assert t["unit"] == "inch"

    def test_size_group_inch_mark_not_left_in_stream(self):
        # The " after the size group should be consumed; nothing should follow.
        tokens = _tok('10 (12, 14)"', num_sizes=3)
        assert len(tokens) == 1
        assert tokens[0]["type"] == "size_group"

    # --- mixed: cm and inch on the same line ---

    def test_cm_and_inch_size_groups_on_same_line(self):
        # "34.3 (38, 42, 45.7, 49.5) cm; 13.5 (15, 16.5, 18, 19.5)""
        line = '34.3 (38, 42, 45.7, 49.5) cm; 13.5 (15, 16.5, 18, 19.5)"'
        tokens = _tok(line, num_sizes=5)

        sg_tokens = [t for t in tokens if t["type"] == "size_group"]
        assert len(sg_tokens) == 2

        cm_group = sg_tokens[0]
        assert cm_group["values"] == [34.3, 38, 42, 45.7, 49.5]
        assert cm_group["unit"] == "cm"

        inch_group = sg_tokens[1]
        assert inch_group["values"] == [13.5, 15, 16.5, 18, 19.5]
        assert inch_group["unit"] == "inch"

    def test_gauge_equivalence_inline(self):
        # "23 sts = 10cm (4")" — the 4" is inside parens as an alternative,
        # parens don't match size_group (non-digit inside), so 4 is a number+inch token.
        tokens = _tok('10cm (4")')
        number_tokens = [t for t in tokens if t["type"] == "number"]
        assert any(t["unit"] == "cm" for t in number_tokens)
        inch_tokens = [t for t in number_tokens if t["unit"] == "inch"]
        assert len(inch_tokens) == 1
        assert inch_tokens[0]["value"] == 4

    # --- typographic / curly quote variants ---

    def test_number_right_curly_double_quote(self):
        # U+201D — what PDFs typically produce for inch marks
        tokens = _tok("4”")
        assert len(tokens) == 1
        assert tokens[0]["unit"] == "inch"

    def test_size_group_right_curly_double_quote(self):
        tokens = _tok("10 (11, 12, 12.5, 13)”", num_sizes=5)
        assert len(tokens) == 1
        t = tokens[0]
        assert t["type"] == "size_group"
        assert t["unit"] == "inch"

    def test_real_world_split_line(self):
        # Pattern: "10 (11, 12, 12.5, 13)" FROM CAST ON"
        # where " is U+201D (right curly double quote)
        tokens = _tok("10 (11, 12, 12.5, 13)” FROM CAST ON", num_sizes=5)
        sg = next(t for t in tokens if t["type"] == "size_group")
        assert sg["unit"] == "inch"
        assert sg["values"] == [10, 11, 12, 12.5, 13]
        # The inch mark must NOT appear in any text token
        text_values = " ".join(t["value"] for t in tokens if t["type"] == "text")
        assert "”" not in text_values

    def test_size_group_with_space_consumed_by_regex_before_inch_mark(self):
        # The SIZE_GROUP_RE consumes trailing whitespace via \s*, so m.end() lands
        # directly on the inch mark. This exercises the overall inch-mark detection path.
        tokens = _tok('13.5 (15, 16.5, 18, 19.5) "', num_sizes=5)
        assert len(tokens) == 1
        t = tokens[0]
        assert t["type"] == "size_group"
        assert t["unit"] == "inch"
        assert t["values"] == [13.5, 15, 16.5, 18, 19.5]

    # --- no false positives ---

    def test_plain_number_no_inch_mark(self):
        tokens = _tok("4")
        assert tokens[0]["unit"] is None

    def test_cm_unit_not_affected(self):
        tokens = _tok("10cm")
        assert tokens[0]["unit"] == "cm"
        assert tokens[0]["scalable"] is False
