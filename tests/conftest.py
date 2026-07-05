"""Shared pytest fixtures.

Each test runs against a fresh temporary SQLite database seeded with the demo
user. `database.db.DB_PATH` is monkeypatched so `get_db()` (which reads the
module global at call time) points every query at the temp file.
"""

import pytest

import database.db as db


@pytest.fixture()
def db_path(monkeypatch, tmp_path):
    """Point the app at a fresh, seeded temp database for the duration of a test."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    db.seed_db()
    return str(path)


@pytest.fixture()
def client(db_path):
    """A Flask test client wired to the temp database."""
    from app import app

    app.config.update(TESTING=True)
    return app.test_client()
