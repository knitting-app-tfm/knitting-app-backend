import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.pattern import GaugeUnit, PatternStatus
from app.services.scaling import (
    InvalidGaugeError,
    InvalidSizeLabelError,
    InvalidSizePositionError,
    PatternNotFoundError,
    PatternNotTokenizedError,
    ScalingConfigNotFoundError,
    ScalingService,
)


@pytest.fixture
def service():
    return ScalingService()


@pytest.fixture
def pattern_with_sizes():
    pattern = MagicMock()
    pattern.id = uuid.uuid4()
    pattern.sizes = ["XS", "S", "M", "L"]
    return pattern


@pytest.fixture
def one_size_pattern():
    pattern = MagicMock()
    pattern.id = uuid.uuid4()
    pattern.sizes = []
    return pattern


@pytest.fixture
def valid_gauge():
    return {
        "gauge_stitches": 20.0,
        "gauge_rows": 28.0,
        "gauge_size": 10.0,
        "gauge_unit": "CM",
        "needle_size": "4mm",
    }


class TestUpsertSize:
    def test_upsert_size_valid(self, service, pattern_with_sizes, valid_gauge):
        db = MagicMock()
        mock_scaling = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
            patch(
                "app.services.scaling.scaling_service.yarn_repository"
            ) as mock_yarn_repo,
        ):
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes
            mock_scaling_repo.upsert.return_value = mock_scaling
            mock_yarn_repo.get_by_pattern_id.return_value = []

            result = service.upsert_size(
                db,
                pattern_with_sizes.id,
                size_label="M",
                size_position=2,
                **valid_gauge,
            )

        assert result is mock_scaling

    def test_upsert_size_recalculates_existing_user_yarns(
        self, service, pattern_with_sizes, valid_gauge
    ):
        db = MagicMock()
        mock_scaling = MagicMock()
        mock_scaling.size_position = 2

        user_yarn = MagicMock()
        user_yarn.pattern_yarn = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
            patch(
                "app.services.scaling.scaling_service.yarn_repository"
            ) as mock_yarn_repo,
            patch(
                "app.services.scaling.scaling_service._calculate_factors",
                return_value=(1.0, 1.0),
            ),
            patch(
                "app.services.scaling.scaling_service.compute_yarn_calculation",
                return_value=(350.0, 2),
            ),
        ):
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes
            mock_scaling_repo.upsert.return_value = mock_scaling
            mock_yarn_repo.get_by_pattern_id.return_value = [user_yarn]

            service.upsert_size(
                db,
                pattern_with_sizes.id,
                size_label="M",
                size_position=2,
                **valid_gauge,
            )

        assert user_yarn.calculated_grams_needed == 350.0
        assert user_yarn.calculated_skeins_needed == 2
        db.commit.assert_called()

    def test_upsert_size_invalid_label(self, service, pattern_with_sizes, valid_gauge):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidSizeLabelError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="XXL",
                    size_position=0,
                    **valid_gauge,
                )

    def test_upsert_size_invalid_position(
        self, service, pattern_with_sizes, valid_gauge
    ):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidSizePositionError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="S",
                    size_position=0,
                    **valid_gauge,
                )

    def test_upsert_size_pattern_not_found(self, service, valid_gauge):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = None

            with pytest.raises(PatternNotFoundError):
                service.upsert_size(
                    db, uuid.uuid4(), size_label="S", size_position=1, **valid_gauge
                )

    def test_upsert_size_one_size_uses_canonical_values(
        self, service, one_size_pattern, valid_gauge
    ):
        db = MagicMock()
        mock_scaling = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
            patch(
                "app.services.scaling.scaling_service.yarn_repository"
            ) as mock_yarn_repo,
        ):
            mock_pattern_repo.get_by_id.return_value = one_size_pattern
            mock_scaling_repo.upsert.return_value = mock_scaling
            mock_yarn_repo.get_by_pattern_id.return_value = []

            result = service.upsert_size(
                db,
                one_size_pattern.id,
                size_label="anything",
                size_position=99,
                **valid_gauge,
            )

        assert result is mock_scaling

    def test_upsert_size_one_size_none_sizes_uses_canonical_values(
        self, service, valid_gauge
    ):
        db = MagicMock()
        pattern = MagicMock()
        pattern.id = uuid.uuid4()
        pattern.sizes = None
        mock_scaling = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
            patch(
                "app.services.scaling.scaling_service.yarn_repository"
            ) as mock_yarn_repo,
        ):
            mock_pattern_repo.get_by_id.return_value = pattern
            mock_scaling_repo.upsert.return_value = mock_scaling
            mock_yarn_repo.get_by_pattern_id.return_value = []

            service.upsert_size(
                db, pattern.id, size_label="S", size_position=1, **valid_gauge
            )

        mock_scaling_repo.upsert.assert_called_once()
        call_args = mock_scaling_repo.upsert.call_args
        assert call_args.args[2] == "One size"
        assert call_args.args[3] == 0


class TestUpsertGauge:
    def test_upsert_gauge_valid(self, service, pattern_with_sizes):
        db = MagicMock()
        mock_scaling = MagicMock()

        with (
            patch(
                "app.services.scaling.scaling_service.pattern_repository"
            ) as mock_pattern_repo,
            patch(
                "app.services.scaling.scaling_service.scaling_repository"
            ) as mock_scaling_repo,
            patch(
                "app.services.scaling.scaling_service.yarn_repository"
            ) as mock_yarn_repo,
        ):
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes
            mock_scaling_repo.upsert.return_value = mock_scaling
            mock_yarn_repo.get_by_pattern_id.return_value = []

            result = service.upsert_size(
                db,
                pattern_with_sizes.id,
                size_label="M",
                size_position=2,
                gauge_stitches=20.0,
                gauge_rows=28.0,
                gauge_size=10.0,
                gauge_unit="CM",
                needle_size="4mm",
            )

        assert result is mock_scaling

    def test_upsert_gauge_stitches_decimal(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidGaugeError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.5,
                    gauge_rows=28.0,
                    gauge_size=10.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_rows_decimal(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidGaugeError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.0,
                    gauge_rows=28.5,
                    gauge_size=10.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_zero_value(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(
                InvalidGaugeError, match="Value must be greater than zero"
            ):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=0.0,
                    gauge_rows=28.0,
                    gauge_size=10.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_negative_value(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(
                InvalidGaugeError, match="Value must be greater than zero"
            ):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.0,
                    gauge_rows=28.0,
                    gauge_size=-5.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_rows_zero_value(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(
                InvalidGaugeError, match="Value must be greater than zero"
            ):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.0,
                    gauge_rows=0.0,
                    gauge_size=10.0,
                    gauge_unit="CM",
                    needle_size=None,
                )

    def test_upsert_gauge_invalid_unit(self, service, pattern_with_sizes):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pattern_repo:
            mock_pattern_repo.get_by_id.return_value = pattern_with_sizes

            with pytest.raises(InvalidGaugeError):
                service.upsert_size(
                    db,
                    pattern_with_sizes.id,
                    size_label="M",
                    size_position=2,
                    gauge_stitches=20.0,
                    gauge_rows=28.0,
                    gauge_size=10.0,
                    gauge_unit="YARDS",
                    needle_size=None,
                )


class TestScalePattern:
    def _make_pattern(
        self,
        status=None,
        sizes=None,
        gauge_stitches=20.0,
        gauge_rows=28.0,
        gauge_size=10.0,
        gauge_unit=GaugeUnit.CM,
    ):
        pattern = MagicMock()
        pattern.id = uuid.uuid4()
        pattern.status = status if status is not None else PatternStatus.TOKENIZED
        pattern.sizes = sizes
        pattern.gauge_stitches = gauge_stitches
        pattern.gauge_rows = gauge_rows
        pattern.gauge_size = gauge_size
        pattern.gauge_unit = gauge_unit
        return pattern

    def _make_scaling(
        self,
        size_position=0,
        size_label="M",
        gauge_stitches=20.0,
        gauge_rows=None,
        gauge_size=10.0,
        gauge_unit=GaugeUnit.CM,
    ):
        scaling = MagicMock()
        scaling.size_position = size_position
        scaling.size_label = size_label
        scaling.gauge_stitches = gauge_stitches
        scaling.gauge_rows = gauge_rows
        scaling.gauge_size = gauge_size
        scaling.gauge_unit = gauge_unit
        return scaling

    def _run(self, service, pattern, user_scaling, tokens):
        db = MagicMock()
        with (
            patch("app.services.scaling.scaling_service.pattern_repository") as mock_pr,
            patch("app.services.scaling.scaling_service.scaling_repository") as mock_sr,
            patch("app.services.scaling.scaling_service.pattern_storage") as mock_ps,
        ):
            mock_pr.get_by_id.return_value = pattern
            mock_sr.get_by_pattern_id.return_value = user_scaling
            mock_ps.read_tokens_file.return_value = tokens
            return service.scale_pattern(db, pattern.id)

    def _line(self, *tokens):
        return {
            "line": 1,
            "bold": False,
            "italic": False,
            "font_size": None,
            "tokens": list(tokens),
        }

    def test_scale_pattern_stitches(self, service):
        # pattern: 20 sts/10cm, user: 25 sts/10cm → factor = 0.8
        pattern = self._make_pattern(gauge_stitches=20.0, gauge_rows=None)
        scaling = self._make_scaling(gauge_stitches=25.0, gauge_rows=None)
        tokens = [
            self._line(
                {"type": "number", "value": 100, "unit": "sts", "scalable": True}
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["value"] == 80  # round(100 * 0.8)
        assert token["scaled"] is True
        assert result["rows_warning"] is False

    def test_scale_pattern_rows_with_gauge(self, service):
        # pattern: 28 rows/10cm, user: 30 rows/10cm → factor ≈ 0.933
        pattern = self._make_pattern(gauge_stitches=20.0, gauge_rows=28.0)
        scaling = self._make_scaling(gauge_stitches=20.0, gauge_rows=30.0)
        tokens = [
            self._line(
                {"type": "number", "value": 30, "unit": "rows", "scalable": True}
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["value"] == 28  # round(30 * 28/30)
        assert token["scaled"] is True
        assert result["rows_warning"] is False

    def test_scale_pattern_rows_without_gauge(self, service):
        # user didn't provide row gauge → factor_rows is None
        pattern = self._make_pattern(gauge_stitches=20.0, gauge_rows=None)
        scaling = self._make_scaling(gauge_stitches=20.0, gauge_rows=None)
        tokens = [
            self._line(
                {"type": "number", "value": 30, "unit": "rows", "scalable": True}
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["value"] == 30  # unchanged
        assert token["scaled"] is False
        assert result["rows_warning"] is True

    def test_scale_pattern_non_scalable_units(self, service):
        pattern = self._make_pattern(gauge_stitches=20.0, gauge_rows=None)
        scaling = self._make_scaling(gauge_stitches=25.0, gauge_rows=None)
        tokens = [
            self._line(
                {"type": "number", "value": 4.5, "unit": "mm", "scalable": False},
                {"type": "number", "value": 50, "unit": "cm", "scalable": False},
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        t0 = result["lines"][0]["tokens"][0]
        t1 = result["lines"][0]["tokens"][1]
        assert t0["value"] == 4.5
        assert t0["scaled"] is False
        assert t1["value"] == 50
        assert t1["scaled"] is False

    def test_scale_pattern_size_group(self, service):
        # 3 sizes, size_position=1 → extract values[1] then scale
        pattern = self._make_pattern(
            sizes=["S", "M", "L"], gauge_stitches=20.0, gauge_rows=None
        )
        scaling = self._make_scaling(
            size_position=1, size_label="M", gauge_stitches=25.0
        )
        # values=[80, 90, 100], num_sizes=3, len=3 → no offset → idx=1 → 90
        # factor_stitches = 20/25 = 0.8 → round(90*0.8) = 72
        tokens = [
            self._line(
                {
                    "type": "size_group",
                    "values": [80, 90, 100],
                    "unit": "sts",
                    "scalable": True,
                }
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["type"] == "number"
        assert token["value"] == 72
        assert token["scaled"] is True

    def test_scale_pattern_size_group_rows_with_factor(self, service):
        # size_group with row unit and factor_rows available → scale and mark scaled
        pattern = self._make_pattern(
            sizes=["S", "M", "L"], gauge_stitches=20.0, gauge_rows=28.0
        )
        scaling = self._make_scaling(
            size_position=1, size_label="M", gauge_stitches=20.0, gauge_rows=30.0
        )
        # values=[8, 10, 12], idx=1 → extracted=10, factor=28/30 → round(10*0.933)=9
        tokens = [
            self._line(
                {
                    "type": "size_group",
                    "values": [8, 10, 12],
                    "unit": "rows",
                    "scalable": True,
                }
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["type"] == "number"
        assert token["value"] == 9
        assert token["scaled"] is True
        assert result["rows_warning"] is False

    def test_scale_pattern_size_group_rows_without_factor(self, service):
        # size_group with row unit but no factor_rows → value unchanged, rows_warning=True
        # values differ by size so scaled=True even without gauge math
        pattern = self._make_pattern(
            sizes=["S", "M", "L"], gauge_stitches=20.0, gauge_rows=None
        )
        scaling = self._make_scaling(
            size_position=1, size_label="M", gauge_stitches=20.0, gauge_rows=None
        )
        tokens = [
            self._line(
                {
                    "type": "size_group",
                    "values": [8, 10, 12],
                    "unit": "rows",
                    "scalable": True,
                }
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["type"] == "number"
        assert token["value"] == 10
        assert token["scaled"] is True  # values[1]=10 != values[0]=8 → size-specific
        assert token.get("rows_warning") is True
        assert result["rows_warning"] is True

    def test_scale_pattern_size_group_non_scalable_different_values(self, service):
        # cm unit is not gauge-scalable; selected value differs from base → scaled=True
        pattern = self._make_pattern(
            sizes=["XS", "S", "M", "L", "XL"], gauge_stitches=20.0, gauge_rows=None
        )
        scaling = self._make_scaling(
            size_position=3, size_label="L", gauge_stitches=20.0, gauge_rows=None
        )
        tokens = [
            self._line(
                {
                    "type": "size_group",
                    "values": [10, 10, 11.4, 12.7, 12.7],
                    "unit": "cm",
                    "scalable": False,
                }
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["type"] == "number"
        assert token["value"] == 12.7
        assert token["scaled"] is True  # 12.7 != values[0]=10

    def test_scale_pattern_size_group_non_scalable_same_value(self, service):
        # cm unit, all values identical → scaled=False (no size or gauge difference)
        pattern = self._make_pattern(
            sizes=["XS", "S", "M", "L", "XL"], gauge_stitches=20.0, gauge_rows=None
        )
        scaling = self._make_scaling(
            size_position=2, size_label="M", gauge_stitches=20.0, gauge_rows=None
        )
        tokens = [
            self._line(
                {
                    "type": "size_group",
                    "values": [10, 10, 10, 10, 10],
                    "unit": "cm",
                    "scalable": False,
                }
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["value"] == 10
        assert token["scaled"] is False  # 10 == values[0]=10 → no difference

    def test_scale_pattern_size_group_no_unit_different_values(self, service):
        # size_group with no unit (e.g. a repeat count); value differs → scaled=True
        pattern = self._make_pattern(
            sizes=["S", "M", "L"], gauge_stitches=20.0, gauge_rows=None
        )
        scaling = self._make_scaling(
            size_position=2, size_label="L", gauge_stitches=20.0, gauge_rows=None
        )
        tokens = [
            self._line(
                {
                    "type": "size_group",
                    "values": [2, 2, 3],
                    "unit": None,
                    "scalable": False,
                }
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["value"] == 3
        assert token["scaled"] is True  # 3 != values[0]=2

    def test_scale_pattern_text_and_abbreviation_pass_through(self, service):
        # text and abbreviation tokens are returned unchanged
        pattern = self._make_pattern(gauge_stitches=20.0, gauge_rows=None)
        scaling = self._make_scaling(gauge_stitches=25.0, gauge_rows=None)
        text_token = {"type": "text", "value": "Cast on"}
        abbr_token = {
            "type": "abbreviation",
            "code": "k",
            "translated": True,
            "full_name": "knit",
            "quantity": None,
        }
        tokens = [self._line(text_token, abbr_token)]

        result = self._run(service, pattern, scaling, tokens)

        assert result["lines"][0]["tokens"][0] == text_token
        assert result["lines"][0]["tokens"][1] == abbr_token

    def test_scale_pattern_different_gauge_units(self, service):
        # pattern: 23 sts per 10 cm, user: 29 sts per 4 inch
        # pattern_density = 23/10 = 2.3 sts/cm
        # user_density = 29 / (4 * 2.54) = 29/10.16 ≈ 2.8543 sts/cm
        # factor = 2.3 / (29/10.16) = 2.3 * 10.16 / 29 ≈ 0.8059
        # value=100 → round(100 * 0.8059) = 81
        pattern = self._make_pattern(
            gauge_stitches=23.0,
            gauge_rows=None,
            gauge_size=10.0,
            gauge_unit=GaugeUnit.CM,
        )
        scaling = self._make_scaling(
            gauge_stitches=29.0,
            gauge_rows=None,
            gauge_size=4.0,
            gauge_unit=GaugeUnit.INCH,
        )
        tokens = [
            self._line(
                {"type": "number", "value": 100, "unit": "sts", "scalable": True}
            )
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["value"] == 81
        assert token["scaled"] is True

    def test_scale_pattern_different_gauge_sizes(self, service):
        # pattern: 20 sts per 10 cm, user: 12 sts per 4 cm (both CM)
        # pattern_density = 20/10 = 2.0 sts/cm
        # user_density = 12/4 = 3.0 sts/cm
        # factor = 2.0/3.0 ≈ 0.6667
        # value=90 → round(90 * 2/3) = 60
        pattern = self._make_pattern(
            gauge_stitches=20.0,
            gauge_rows=None,
            gauge_size=10.0,
            gauge_unit=GaugeUnit.CM,
        )
        scaling = self._make_scaling(
            gauge_stitches=12.0,
            gauge_rows=None,
            gauge_size=4.0,
            gauge_unit=GaugeUnit.CM,
        )
        tokens = [
            self._line({"type": "number", "value": 90, "unit": "sts", "scalable": True})
        ]

        result = self._run(service, pattern, scaling, tokens)

        token = result["lines"][0]["tokens"][0]
        assert token["value"] == 60
        assert token["scaled"] is True

    def test_scale_pattern_missing_pattern_gauge(self, service):
        pattern = self._make_pattern(
            gauge_stitches=20.0, gauge_rows=None, gauge_size=None
        )
        scaling = self._make_scaling(gauge_stitches=20.0, gauge_rows=None)
        db = MagicMock()

        with (
            patch("app.services.scaling.scaling_service.pattern_repository") as mock_pr,
            patch("app.services.scaling.scaling_service.scaling_repository") as mock_sr,
        ):
            mock_pr.get_by_id.return_value = pattern
            mock_sr.get_by_pattern_id.return_value = scaling

            with pytest.raises(InvalidGaugeError, match="Pattern gauge is required"):
                service.scale_pattern(db, pattern.id)

    def test_scale_pattern_pattern_not_found(self, service):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pr:
            mock_pr.get_by_id.return_value = None

            with pytest.raises(PatternNotFoundError):
                service.scale_pattern(db, uuid.uuid4())

    def test_scale_pattern_not_tokenized(self, service):
        db = MagicMock()
        pattern = MagicMock()
        pattern.status = PatternStatus.CONFIRMED

        with patch(
            "app.services.scaling.scaling_service.pattern_repository"
        ) as mock_pr:
            mock_pr.get_by_id.return_value = pattern

            with pytest.raises(PatternNotTokenizedError):
                service.scale_pattern(db, uuid.uuid4())

    def test_scale_pattern_no_scaling(self, service):
        db = MagicMock()
        pattern = MagicMock()
        pattern.status = PatternStatus.TOKENIZED

        with (
            patch("app.services.scaling.scaling_service.pattern_repository") as mock_pr,
            patch("app.services.scaling.scaling_service.scaling_repository") as mock_sr,
        ):
            mock_pr.get_by_id.return_value = pattern
            mock_sr.get_by_pattern_id.return_value = None

            with pytest.raises(ScalingConfigNotFoundError):
                service.scale_pattern(db, uuid.uuid4())


class TestGetByPatternId:
    def test_returns_scaling_when_found(self, service):
        db = MagicMock()
        mock_scaling = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.scaling_repository"
        ) as mock_sr:
            mock_sr.get_by_pattern_id.return_value = mock_scaling

            result = service.get_by_pattern_id(db, uuid.uuid4())

        assert result is mock_scaling

    def test_returns_none_when_not_found(self, service):
        db = MagicMock()

        with patch(
            "app.services.scaling.scaling_service.scaling_repository"
        ) as mock_sr:
            mock_sr.get_by_pattern_id.return_value = None

            result = service.get_by_pattern_id(db, uuid.uuid4())

        assert result is None
