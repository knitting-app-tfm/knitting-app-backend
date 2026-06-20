import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.models.abbreviation import Abbreviation
from scripts.populate_video_links import (
    QuotaExceededError,
    fetch_video_id,
    populate_video_links,
)


def _write_csv(
    path: Path, rows: list[dict], fieldnames: list[str] | None = None
) -> None:
    if fieldnames is None:
        fieldnames = [
            "abbreviation",
            "full_name",
            "description",
            "type",
            "craft",
            "video_link",
        ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _make_abbr(abbreviation="k", full_name="knit", craft_value="KNITTING") -> MagicMock:
    abbr = MagicMock(spec=Abbreviation)
    abbr.abbreviation = abbreviation
    abbr.full_name = full_name
    abbr.type.value = "STITCH"
    abbr.craft.value = craft_value
    abbr.video_link = None
    return abbr


def _mock_db(eligible: list) -> MagicMock:
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = eligible
    return mock_db


def _base_row(abbreviation="k", craft="KNITTING") -> dict:
    return {
        "abbreviation": abbreviation,
        "full_name": "knit",
        "description": "",
        "type": "STITCH",
        "craft": craft,
        "video_link": "",
    }


class TestFetchVideoId:
    def _mock_response(self, status_code: int, json_data: dict) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data
        return resp

    def _abbr(self) -> MagicMock:
        abbr = MagicMock()
        abbr.full_name = "knit"
        abbr.type.value = "STITCH"
        abbr.craft.value = "KNITTING"
        return abbr

    def test_returns_video_id_from_first_result(self):
        resp = self._mock_response(200, {"items": [{"id": {"videoId": "abc123"}}]})
        with patch("scripts.populate_video_links.requests.get", return_value=resp):
            assert fetch_video_id(self._abbr()) == "abc123"

    def test_returns_none_when_no_results(self):
        resp = self._mock_response(200, {"items": []})
        with patch("scripts.populate_video_links.requests.get", return_value=resp):
            assert fetch_video_id(self._abbr()) is None

    def test_raises_quota_exceeded_on_quota_error(self):
        resp = self._mock_response(
            403, {"error": {"errors": [{"reason": "quotaExceeded"}]}}
        )
        with patch("scripts.populate_video_links.requests.get", return_value=resp):
            with pytest.raises(QuotaExceededError):
                fetch_video_id(self._abbr())

    def test_raises_http_error_on_other_403(self):
        resp = self._mock_response(
            403, {"error": {"errors": [{"reason": "forbidden"}]}}
        )
        resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        with patch("scripts.populate_video_links.requests.get", return_value=resp):
            with pytest.raises(requests.HTTPError):
                fetch_video_id(self._abbr())


class TestPopulateVideoLinks:
    def test_writes_embed_url_and_saves_csv(self, tmp_path):
        csv_file = tmp_path / "abbr.csv"
        _write_csv(csv_file, [_base_row()])

        with (
            patch("scripts.populate_video_links.CSV_PATH", csv_file),
            patch(
                "scripts.populate_video_links.SessionLocal",
                return_value=_mock_db([_make_abbr()]),
            ),
            patch("scripts.populate_video_links.fetch_video_id", return_value="abc123"),
            patch("scripts.populate_video_links.seed_abbreviations"),
        ):
            populate_video_links()

        assert (
            _read_csv(csv_file)[0]["video_link"]
            == "https://www.youtube.com/embed/abc123"
        )

    def test_does_not_update_csv_when_no_video_found(self, tmp_path):
        csv_file = tmp_path / "abbr.csv"
        _write_csv(csv_file, [_base_row()])

        with (
            patch("scripts.populate_video_links.CSV_PATH", csv_file),
            patch(
                "scripts.populate_video_links.SessionLocal",
                return_value=_mock_db([_make_abbr()]),
            ),
            patch("scripts.populate_video_links.fetch_video_id", return_value=None),
            patch("scripts.populate_video_links.seed_abbreviations"),
        ):
            populate_video_links()

        assert _read_csv(csv_file)[0]["video_link"] == ""

    def test_skips_failed_row_and_continues_to_next(self, tmp_path):
        csv_file = tmp_path / "abbr.csv"
        _write_csv(csv_file, [_base_row("k"), _base_row("p")])
        abbr_k = _make_abbr("k")
        abbr_p = _make_abbr("p")

        with (
            patch("scripts.populate_video_links.CSV_PATH", csv_file),
            patch(
                "scripts.populate_video_links.SessionLocal",
                return_value=_mock_db([abbr_k, abbr_p]),
            ),
            patch(
                "scripts.populate_video_links.fetch_video_id",
                side_effect=[requests.RequestException("network error"), "xyz789"],
            ),
            patch("scripts.populate_video_links.seed_abbreviations"),
        ):
            populate_video_links()

        rows = _read_csv(csv_file)
        assert rows[0]["video_link"] == ""
        assert rows[1]["video_link"] == "https://www.youtube.com/embed/xyz789"

    def test_stops_on_quota_exceeded_and_calls_seeder(self, tmp_path):
        csv_file = tmp_path / "abbr.csv"
        _write_csv(csv_file, [_base_row()])

        with (
            patch("scripts.populate_video_links.CSV_PATH", csv_file),
            patch(
                "scripts.populate_video_links.SessionLocal",
                return_value=_mock_db([_make_abbr()]),
            ),
            patch(
                "scripts.populate_video_links.fetch_video_id",
                side_effect=QuotaExceededError,
            ),
            patch("scripts.populate_video_links.seed_abbreviations") as mock_seeder,
        ):
            populate_video_links()

        mock_seeder.assert_called_once_with(update_existing=True)

    def test_calls_seeder_on_normal_completion(self, tmp_path):
        csv_file = tmp_path / "abbr.csv"
        _write_csv(csv_file, [_base_row()])

        with (
            patch("scripts.populate_video_links.CSV_PATH", csv_file),
            patch(
                "scripts.populate_video_links.SessionLocal",
                return_value=_mock_db([_make_abbr()]),
            ),
            patch("scripts.populate_video_links.fetch_video_id", return_value="abc123"),
            patch("scripts.populate_video_links.seed_abbreviations") as mock_seeder,
        ):
            populate_video_links()

        mock_seeder.assert_called_once_with(update_existing=True)

    def test_adds_video_link_column_when_missing_from_csv(self, tmp_path):
        csv_file = tmp_path / "abbr.csv"
        _write_csv(
            csv_file,
            [
                {
                    "abbreviation": "k",
                    "full_name": "knit",
                    "description": "",
                    "type": "STITCH",
                    "craft": "KNITTING",
                }
            ],
            fieldnames=["abbreviation", "full_name", "description", "type", "craft"],
        )

        with (
            patch("scripts.populate_video_links.CSV_PATH", csv_file),
            patch(
                "scripts.populate_video_links.SessionLocal",
                return_value=_mock_db([_make_abbr()]),
            ),
            patch("scripts.populate_video_links.fetch_video_id", return_value="abc123"),
            patch("scripts.populate_video_links.seed_abbreviations"),
        ):
            populate_video_links()

        rows = _read_csv(csv_file)
        assert "video_link" in rows[0]
        assert rows[0]["video_link"] == "https://www.youtube.com/embed/abc123"
