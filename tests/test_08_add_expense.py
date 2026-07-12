"""Tests for the Add Expense feature (Step 08).

The seeded demo user (id 1) starts with 8 expenses totalling 295.25. These
tests exercise the create_expense() helper and the GET/POST /expenses/add route.
"""

import database.db as db

SEED_USER_ID = 1


def _login(client):
    """Log the test client in as the seeded demo user."""
    return client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )


# --------------------------------------------------------------------- #
# create_expense helper                                                 #
# --------------------------------------------------------------------- #

def test_create_expense_inserts_row(db_path):
    before = db.count_transactions(SEED_USER_ID)
    new_id = db.create_expense(SEED_USER_ID, 12.5, "Food", "2026-07-13", "Lunch")
    assert isinstance(new_id, int)
    assert db.count_transactions(SEED_USER_ID) == before + 1


def test_create_expense_allows_null_description(db_path):
    new_id = db.create_expense(SEED_USER_ID, 5.0, "Other", "2026-07-13", None)
    conn = db.get_db()
    row = conn.execute(
        "SELECT description FROM expenses WHERE id = ?", (new_id,)
    ).fetchone()
    conn.close()
    assert row["description"] is None


# --------------------------------------------------------------------- #
# GET /expenses/add                                                     #
# --------------------------------------------------------------------- #

def test_add_expense_get_requires_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_add_expense_get_renders_form(client):
    _login(client)
    resp = client.get("/expenses/add")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="amount"' in body
    assert 'name="category"' in body
    assert 'name="date"' in body


# --------------------------------------------------------------------- #
# POST /expenses/add                                                    #
# --------------------------------------------------------------------- #

def test_add_expense_post_requires_login(client):
    resp = client.post(
        "/expenses/add",
        data={"amount": "10", "category": "Food", "date": "2026-07-13"},
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_add_expense_valid_inserts_and_redirects(client, db_path):
    _login(client)
    before = db.count_transactions(SEED_USER_ID)
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "42.50",
            "category": "Shopping",
            "date": "2026-07-13",
            "description": "New shoes",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]
    assert db.count_transactions(SEED_USER_ID) == before + 1


def test_add_expense_shows_up_on_profile(client, db_path):
    _login(client)
    client.post(
        "/expenses/add",
        data={
            "amount": "99.00",
            "category": "Health",
            "date": "2026-07-13",
            "description": "Dentist visit",
        },
        follow_redirects=True,
    )
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)
    assert "Dentist visit" in body


def test_add_expense_blank_description_ok(client, db_path):
    _login(client)
    before = db.count_transactions(SEED_USER_ID)
    resp = client.post(
        "/expenses/add",
        data={"amount": "7", "category": "Other", "date": "2026-07-13", "description": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db.count_transactions(SEED_USER_ID) == before + 1


# --------------------------------------------------------------------- #
# POST /expenses/add — validation                                      #
# --------------------------------------------------------------------- #

def _assert_rejected(client, data):
    """POST invalid data and assert the form re-renders with no row inserted."""
    before = db.count_transactions(SEED_USER_ID)
    resp = client.post("/expenses/add", data=data, follow_redirects=False)
    assert resp.status_code == 200
    assert db.count_transactions(SEED_USER_ID) == before
    return resp.get_data(as_text=True)


def test_add_expense_rejects_empty_amount(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "", "category": "Food", "date": "2026-07-13"}
    )


def test_add_expense_rejects_zero_amount(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "0", "category": "Food", "date": "2026-07-13"}
    )


def test_add_expense_rejects_negative_amount(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "-5", "category": "Food", "date": "2026-07-13"}
    )


def test_add_expense_rejects_non_numeric_amount(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "abc", "category": "Food", "date": "2026-07-13"}
    )


def test_add_expense_preserves_input_on_error(client, db_path):
    _login(client)
    body = _assert_rejected(
        client,
        {"amount": "bad", "category": "Food", "date": "2026-07-13", "description": "Keep me"},
    )
    # Entered category and description survive the failed submit.
    assert "Keep me" in body
    assert 'value="Food" selected' in body


def test_add_expense_rejects_bad_category(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "10", "category": "Crypto", "date": "2026-07-13"}
    )


def test_add_expense_rejects_bad_date(client, db_path):
    _login(client)
    _assert_rejected(
        client, {"amount": "10", "category": "Food", "date": "not-a-date"}
    )
