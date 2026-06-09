import json
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.pattern import pattern_storage


@pytest.fixture
def storage_base(tmp_path):
    with patch.object(settings, "STORAGE_BASE_PATH", str(tmp_path)):
        yield tmp_path


class TestSaveFile:
    def test_saves_bytes_and_returns_storage_path(self, storage_base):
        result = pattern_storage.save_file(b"pdf content", "original", "abc123", ".pdf")

        assert result == "storage/original/abc123.pdf"
        assert (storage_base / "original" / "abc123.pdf").read_bytes() == b"pdf content"

    def test_saves_text_and_returns_storage_path(self, storage_base):
        result = pattern_storage.save_file(
            '{"title": "T"}', "parsed", "abc123", ".json"
        )

        assert result == "storage/parsed/abc123.json"
        written = (storage_base / "parsed" / "abc123.json").read_text(encoding="utf-8")
        assert written == '{"title": "T"}'

    def test_creates_subdirectory_if_missing(self, storage_base):
        pattern_storage.save_file(b"data", "tokens", "xyz", ".json")

        assert (storage_base / "tokens").is_dir()

    def test_returns_storage_prefixed_path(self, storage_base):
        path = pattern_storage.save_file(b"x", "covers", "id1", ".png")

        assert path.startswith("storage/")


class TestReadParsedJson:
    def test_reads_valid_json_file(self, storage_base):
        file_path = storage_base / "parsed" / "test.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text('{"title": "My Pattern"}', encoding="utf-8")

        result = pattern_storage.read_parsed_json("storage/parsed/test.json")

        assert result == {"title": "My Pattern"}

    def test_returns_empty_dict_when_file_missing(self, storage_base):
        result = pattern_storage.read_parsed_json("storage/parsed/nonexistent.json")

        assert result == {}

    def test_returns_empty_dict_on_invalid_json(self, storage_base):
        file_path = storage_base / "parsed" / "bad.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("not json {{", encoding="utf-8")

        result = pattern_storage.read_parsed_json("storage/parsed/bad.json")

        assert result == {}


class TestReadTokensFile:
    def test_reads_valid_tokens_file(self, storage_base):
        tokens = [{"line": 1, "tokens": []}]
        file_path = storage_base / "tokens" / "test.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(tokens), encoding="utf-8")

        result = pattern_storage.read_tokens_file("storage/tokens/test.json")

        assert result == tokens

    def test_returns_empty_list_when_file_missing(self, storage_base):
        result = pattern_storage.read_tokens_file("storage/tokens/nonexistent.json")

        assert result == []

    def test_returns_empty_list_on_invalid_json(self, storage_base):
        file_path = storage_base / "tokens" / "bad.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("not json {{", encoding="utf-8")

        result = pattern_storage.read_tokens_file("storage/tokens/bad.json")

        assert result == []
