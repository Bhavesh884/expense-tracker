"""Tests for the Edit Expense feature (Step 09).

The seeded demo user (id 1) starts with 8 expenses (ids 1-8). These tests
exercise the get_expense() / update_expense() helpers and the GET/POST
/expenses/<id>/edit route, with particular attention to the ownership boundary.
"""

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


# --------------------------------------------------------------------- #
# get_expense helper                                                    #
# --------------------------------------------------------------------- #

def test_get_expense_returns_owned_row(db_path):
    expense = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    assert expense is not None
    assert expense["id"] == SEED_EXPENSE_ID
    assert expense["user_id"] == SEED_USER_ID


def test_get_expense_returns_none_for_foreign_user(db_path):
    other_id, expense_id = _make_other_user_expense()
    # The seeded user must not be able to read the other user's expense.
    assert db.get_expense(expense_id, SEED_USER_ID) is None
    # But the true owner can.
    assert db.get_expense(expense_id, other_id) is not None


def test_get_expense_returns_none_for_missing_id(db_path):
    assert db.get_expense(9999, SEED_USER_ID) is None


# --------------------------------------------------------------------- #
# update_expense helper                                                 #
# --------------------------------------------------------------------- #

def test_update_expense_changes_owned_row(db_path):
    changed = db.update_expense(
        SEED_EXPENSE_ID, SEED_USER_ID, 99.99, "Bills", "2026-07-11", "Edited"
    )
    assert changed == 1
    row = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    assert row["amount"] == 99.99
    assert row["category"] == "Bills"
    assert row["date"] == "2026-07-11"
    assert row["description"] == "Edited"


def test_update_expense_allows_null_description(db_path):
    db.update_expense(
        SEED_EXPENSE_ID, SEED_USER_ID, 10.0, "Other", "2026-07-11", None
    )
    row = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    assert row["description"] is None


def test_update_expense_does_not_touch_foreign_row(db_path):
    other_id, expense_id = _make_other_user_expense()
    changed = db.update_expense(
        expense_id, SEED_USER_ID, 1.0, "Food", "2026-07-01", "hacked"
    )
    assert changed == 0
    # The other user's row is untouched.
    row = db.get_expense(expense_id, other_id)
    assert row["description"] == "Not yours"
    assert row["amount"] == 50.0


# --------------------------------------------------------------------- #
# GET /expenses/<id>/edit                                               #
# --------------------------------------------------------------------- #

def test_edit_get_requires_login(client):
    resp = client.get(f"/expenses/{SEED_EXPENSE_ID}/edit")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_edit_get_renders_prefilled_form(client, db_path):
    _login(client)
    resp = client.get(f"/expenses/{SEED_EXPENSE_ID}/edit")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Seed expense 1 is (12.50, Food, 2026-07-02, "Lunch").
    assert 'name="amount"' in body
    assert 'value="12.5"' in body
    assert 'value="Food" selected' in body
    assert "Lunch" in body


def test_edit_get_missing_id_is_404(client, db_path):
    _login(client)
    resp = client.get("/expenses/9999/edit")
    assert resp.status_code == 404


def test_edit_get_foreign_expense_is_404(client, db_path):
    _, expense_id = _make_other_user_expense()
    _login(client)
    resp = client.get(f"/expenses/{expense_id}/edit")
    assert resp.status_code == 404


# --------------------------------------------------------------------- #
# POST /expenses/<id>/edit                                              #
# --------------------------------------------------------------------- #

def test_edit_post_requires_login(client, db_path):
    resp = client.post(
        f"/expenses/{SEED_EXPENSE_ID}/edit",
        data={"amount": "10", "category": "Food", "date": "2026-07-13"},
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_edit_post_valid_updates_and_redirects(client, db_path):
    _login(client)
    before = db.count_transactions(SEED_USER_ID)
    resp = client.post(
        f"/expenses/{SEED_EXPENSE_ID}/edit",
        data={
            "amount": "77.25",
            "category": "Shopping",
            "date": "2026-07-14",
            "description": "New shoes",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]
    # No new row — the same one is edited.
    assert db.count_transactions(SEED_USER_ID) == before
    row = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    assert row["amount"] == 77.25
    assert row["category"] == "Shopping"
    assert row["date"] == "2026-07-14"
    assert row["description"] == "New shoes"


def test_edit_post_shows_change_on_profile(client, db_path):
    _login(client)
    client.post(
        f"/expenses/{SEED_EXPENSE_ID}/edit",
        data={
            "amount": "5.00",
            "category": "Health",
            "date": "2026-07-14",
            "description": "Updated pharmacy",
        },
        follow_redirects=True,
    )
    resp = client.get("/profile")
    assert "Updated pharmacy" in resp.get_data(as_text=True)


def test_edit_post_blank_description_ok(client, db_path):
    _login(client)
    resp = client.post(
        f"/expenses/{SEED_EXPENSE_ID}/edit",
        data={"amount": "8", "category": "Other", "date": "2026-07-14", "description": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    row = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    assert row["description"] is None


def test_edit_post_foreign_expense_is_404(client, db_path):
    other_id, expense_id = _make_other_user_expense()
    _login(client)
    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": "1", "category": "Food", "date": "2026-07-01"},
    )
    assert resp.status_code == 404
    # Untouched.
    row = db.get_expense(expense_id, other_id)
    assert row["amount"] == 50.0


# --------------------------------------------------------------------- #
# POST /expenses/<id>/edit — validation                                #
# --------------------------------------------------------------------- #

def _assert_rejected(client, data):
    """POST invalid data and assert the form re-renders with the row unchanged."""
    before = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    resp = client.post(
        f"/expenses/{SEED_EXPENSE_ID}/edit", data=data, follow_redirects=False
    )
    assert resp.status_code == 200
    after = db.get_expense(SEED_EXPENSE_ID, SEED_USER_ID)
    assert after == before
    return resp.get_data(as_text=True)


def test_edit_rejects_empty_amount(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "", "category": "Food", "date": "2026-07-14"}
    )


def test_edit_rejects_zero_amount(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "0", "category": "Food", "date": "2026-07-14"}
    )


def test_edit_rejects_negative_amount(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "-5", "category": "Food", "date": "2026-07-14"}
    )


def test_edit_rejects_non_numeric_amount(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "abc", "category": "Food", "date": "2026-07-14"}
    )


def test_edit_preserves_input_on_error(client, db_path):
    _login(client)
    body = _assert_rejected(
        client,
        {"amount": "bad", "category": "Bills", "date": "2026-07-14", "description": "Keep me"},
    )
    assert "Keep me" in body
    assert 'value="Bills" selected' in body


def test_edit_rejects_bad_category(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "10", "category": "Crypto", "date": "2026-07-14"}
    )


def test_edit_rejects_bad_date(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "10", "category": "Food", "date": "not-a-date"}
    )
