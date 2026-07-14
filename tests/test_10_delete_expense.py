"""Tests for the Delete Expense feature (Step 10) and future-date validation.

The seeded demo user (id 1) starts with 8 expenses (ids 1-8). These tests
exercise the delete_expense() helper and the POST /expenses/<id>/delete route,
with particular attention to the ownership boundary, plus the new rule that
add/edit reject dates in the future.
"""

from datetime import datetime, timedelta

import database.db as db

SEED_USER_ID = 1
SEED_EXPENSE_ID = 1


def _login(client):
    """Log the test client in as the seeded demo user."""
    return client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )


def _make_other_user_expense():
    """Create a second user owning one expense; return (user_id, expense_id)."""
    other_id = db.create_user(
        "Other User", "other@spendly.com", db.generate_password_hash("Other123!")
    )
    expense_id = db.create_expense(other_id, 50.0, "Food", "2026-07-10", "Not yours")
    return other_id, expense_id


def _today():
    return datetime.now().date().isoformat()


def _tomorrow():
    return (datetime.now().date() + timedelta(days=1)).isoformat()


# --------------------------------------------------------------------- #
# delete_expense helper                                                 #
# --------------------------------------------------------------------- #

def test_delete_expense_removes_owned_row(db_path):
    deleted = db.delete_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    assert deleted == 1
    assert db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID) is None


def test_delete_expense_does_not_touch_foreign_row(db_path):
    other_id, expense_id = _make_other_user_expense()
    deleted = db.delete_expense(expense_id, SEED_USER_ID)
    assert deleted == 0
    # The other user's row is untouched.
    assert db.get_expense(expense_id, other_id) is not None


def test_delete_expense_returns_zero_for_missing_id(db_path):
    assert db.delete_expense(9999, SEED_USER_ID) == 0


# --------------------------------------------------------------------- #
# POST /expenses/<id>/delete                                            #
# --------------------------------------------------------------------- #

def test_delete_post_requires_login(client, db_path):
    resp = client.post(f"/expenses/{SEED_EXPENSE_ID}/delete")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    # Nothing deleted.
    assert db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID) is not None


def test_delete_post_removes_row_and_redirects(client, db_path):
    _login(client)
    before = db.count_transactions(SEED_USER_ID)
    resp = client.post(f"/expenses/{SEED_EXPENSE_ID}/delete", follow_redirects=False)
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]
    assert db.count_transactions(SEED_USER_ID) == before - 1
    assert db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID) is None


def test_delete_post_shows_flash_on_profile(client, db_path):
    _login(client)
    resp = client.post(
        f"/expenses/{SEED_EXPENSE_ID}/delete", follow_redirects=True
    )
    assert resp.status_code == 200
    assert "Expense deleted successfully." in resp.get_data(as_text=True)


def test_delete_post_missing_id_is_404(client, db_path):
    _login(client)
    resp = client.post("/expenses/9999/delete")
    assert resp.status_code == 404


def test_delete_post_foreign_expense_is_404(client, db_path):
    other_id, expense_id = _make_other_user_expense()
    _login(client)
    resp = client.post(f"/expenses/{expense_id}/delete")
    assert resp.status_code == 404
    # The other user's row is untouched.
    assert db.get_expense(expense_id, other_id) is not None


def test_delete_get_is_405(client, db_path):
    _login(client)
    resp = client.get(f"/expenses/{SEED_EXPENSE_ID}/delete")
    assert resp.status_code == 405
    # Nothing deleted.
    assert db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID) is not None


# --------------------------------------------------------------------- #
# Future-date validation on add/edit                                    #
# --------------------------------------------------------------------- #

def test_add_rejects_future_date(client, db_path):
    _login(client)
    before = db.count_transactions(SEED_USER_ID)
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "10",
            "category": "Food",
            "date": _tomorrow(),
            "description": "Time travel",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Date cannot be in the future." in resp.get_data(as_text=True)
    assert db.count_transactions(SEED_USER_ID) == before


def test_add_accepts_today(client, db_path):
    _login(client)
    before = db.count_transactions(SEED_USER_ID)
    resp = client.post(
        "/expenses/add",
        data={"amount": "10", "category": "Food", "date": _today()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.count_transactions(SEED_USER_ID) == before + 1


def test_edit_rejects_future_date(client, db_path):
    _login(client)
    before = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    resp = client.post(
        f"/expenses/{SEED_EXPENSE_ID}/edit",
        data={"amount": "10", "category": "Food", "date": _tomorrow()},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "Date cannot be in the future." in resp.get_data(as_text=True)
    # Row unchanged.
    assert db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID) == before


def test_edit_accepts_today(client, db_path):
    _login(client)
    resp = client.post(
        f"/expenses/{SEED_EXPENSE_ID}/edit",
        data={"amount": "10", "category": "Food", "date": _today()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    assert row["date"] == _today()
