from unittest.mock import MagicMock, patch

from app.core.database import get_db


class TestGetDb:
    def test_yields_session_from_session_local(self):
        mock_session = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=mock_session):
            gen = get_db()
            session = next(gen)
        assert session is mock_session

    def test_closes_session_after_yield(self):
        mock_session = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=mock_session):
            gen = get_db()
            next(gen)
            try:
                next(gen)
            except StopIteration:
                pass
        mock_session.close.assert_called_once()

    def test_closes_session_when_generator_is_closed_early(self):
        mock_session = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=mock_session):
            gen = get_db()
            next(gen)
            gen.close()
        mock_session.close.assert_called_once()
