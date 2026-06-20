import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.models.abbreviation import Abbreviation, AbbreviationCraft
from scripts.seed_abbreviations import seed_abbreviations


def _write_csv(path: Path, rows: list[dict]) -> None:
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


def _mock_db_returning(abbr_obj):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = abbr_obj
    return mock_db


class TestSeedAbbreviationsUpdateExisting:
    def test_updates_video_link_for_matching_row(self, tmp_path):
        csv_file = tmp_path / "abbreviations.csv"
        _write_csv(
            csv_file,
            [
                {
                    "abbreviation": "k",
                    "full_name": "knit",
                    "description": "",
                    "type": "STITCH",
                    "craft": "KNITTING",
                    "video_link": "https://www.youtube.com/embed/abc123",
                },
            ],
        )

        mock_abbr = MagicMock(spec=Abbreviation)
        mock_abbr.video_link = None
        mock_db = _mock_db_returning(mock_abbr)

        with patch("scripts.seed_abbreviations.SessionLocal", return_value=mock_db):
            seed_abbreviations(update_existing=True, csv_path=csv_file)

        assert mock_abbr.video_link == "https://www.youtube.com/embed/abc123"
        mock_db.commit.assert_called_once()

    def test_skips_update_when_video_link_already_matches(self, tmp_path):
        csv_file = tmp_path / "abbreviations.csv"
        existing_url = "https://www.youtube.com/embed/abc123"
        _write_csv(
            csv_file,
            [
                {
                    "abbreviation": "k",
                    "full_name": "knit",
                    "description": "",
                    "type": "STITCH",
                    "craft": "KNITTING",
                    "video_link": existing_url,
                },
            ],
        )

        mock_abbr = MagicMock(spec=Abbreviation)
        mock_abbr.video_link = existing_url
        mock_db = _mock_db_returning(mock_abbr)

        with patch("scripts.seed_abbreviations.SessionLocal", return_value=mock_db):
            seed_abbreviations(update_existing=True, csv_path=csv_file)

        mock_db.commit.assert_not_called()

    def test_skips_csv_rows_with_empty_video_link(self, tmp_path):
        csv_file = tmp_path / "abbreviations.csv"
        _write_csv(
            csv_file,
            [
                {
                    "abbreviation": "k",
                    "full_name": "knit",
                    "description": "",
                    "type": "STITCH",
                    "craft": "KNITTING",
                    "video_link": "",
                },
            ],
        )

        mock_db = MagicMock()

        with patch("scripts.seed_abbreviations.SessionLocal", return_value=mock_db):
            seed_abbreviations(update_existing=True, csv_path=csv_file)

        mock_db.query.assert_not_called()
        mock_db.commit.assert_not_called()

    def test_does_not_require_empty_table(self, tmp_path):
        csv_file = tmp_path / "abbreviations.csv"
        _write_csv(
            csv_file,
            [
                {
                    "abbreviation": "k",
                    "full_name": "knit",
                    "description": "",
                    "type": "STITCH",
                    "craft": "KNITTING",
                    "video_link": "",
                },
            ],
        )

        mock_db = MagicMock()

        with patch("scripts.seed_abbreviations.SessionLocal", return_value=mock_db):
            seed_abbreviations(update_existing=True, csv_path=csv_file)

        count_called = any("count" in str(call) for call in mock_db.mock_calls)
        assert not count_called

    def test_does_not_modify_other_fields(self, tmp_path):
        csv_file = tmp_path / "abbreviations.csv"
        _write_csv(
            csv_file,
            [
                {
                    "abbreviation": "k",
                    "full_name": "knit UPDATED IN CSV",
                    "description": "new description in csv",
                    "type": "STITCH",
                    "craft": "KNITTING",
                    "video_link": "https://www.youtube.com/embed/abc123",
                },
            ],
        )

        class SimpleAbbr:
            abbreviation = "k"
            full_name = "knit ORIGINAL"
            description = "original description"
            video_link = None
            craft = AbbreviationCraft.KNITTING

        abbr = SimpleAbbr()
        mock_db = _mock_db_returning(abbr)

        with patch("scripts.seed_abbreviations.SessionLocal", return_value=mock_db):
            seed_abbreviations(update_existing=True, csv_path=csv_file)

        assert abbr.video_link == "https://www.youtube.com/embed/abc123"
        assert abbr.full_name == "knit ORIGINAL"
        assert abbr.description == "original description"

    def test_commits_per_row_not_in_batch(self, tmp_path):
        csv_file = tmp_path / "abbreviations.csv"
        _write_csv(
            csv_file,
            [
                {
                    "abbreviation": "k",
                    "full_name": "knit",
                    "description": "",
                    "type": "STITCH",
                    "craft": "KNITTING",
                    "video_link": "https://www.youtube.com/embed/first",
                },
                {
                    "abbreviation": "p",
                    "full_name": "purl",
                    "description": "",
                    "type": "STITCH",
                    "craft": "KNITTING",
                    "video_link": "https://www.youtube.com/embed/second",
                },
            ],
        )

        abbr_k = MagicMock(spec=Abbreviation)
        abbr_k.video_link = None
        abbr_p = MagicMock(spec=Abbreviation)
        abbr_p.video_link = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            abbr_k,
            abbr_p,
        ]

        with patch("scripts.seed_abbreviations.SessionLocal", return_value=mock_db):
            seed_abbreviations(update_existing=True, csv_path=csv_file)

        assert mock_db.commit.call_count == 2
