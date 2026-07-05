"""Tests for the /profile backend wiring (Step 06 — Backend Connection).

The seeded demo user (id 1) has 8 expenses totalling 295.25, top category
"Bills", across 7 categories.
"""

import database.db as db

SEED_USER_ID = 1


# --------------------------------------------------------------------- #
# get_user_by_id                                                        #
# --------------------------------------------------------------------- #

def test_get_user_by_id_valid(db_path):
    user = db.get_user_by_id(SEED_USER_ID)
    assert user is not None
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"


def test_get_user_by_id_missing(db_path):
    assert db.get_user_by_id(9999) is None


# --------------------------------------------------------------------- #
# get_summary_stats                                                     #
# --------------------------------------------------------------------- #

def test_get_summary_stats_with_expenses(db_path):
    stats = db.get_summary_stats(SEED_USER_ID)
    assert round(stats["total_spent"], 2) == 295.25
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(db_path):
    stats = db.get_summary_stats(9999)
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


# --------------------------------------------------------------------- #
# get_recent_transactions                                              #
# --------------------------------------------------------------------- #

def test_get_recent_transactions_newest_first(db_path):
    txns = db.get_recent_transactions(SEED_USER_ID)
    assert len(txns) == 8
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)
    assert set(txns[0].keys()) == {"date", "description", "category", "amount"}


def test_get_recent_transactions_respects_limit(db_path):
    assert len(db.get_recent_transactions(SEED_USER_ID, limit=3)) == 3


def test_get_recent_transactions_empty(db_path):
    assert db.get_recent_transactions(9999) == []


# --------------------------------------------------------------------- #
# get_category_breakdown                                               #
# --------------------------------------------------------------------- #

def test_get_category_breakdown_ordered_and_sums_to_100(db_path):
    breakdown = db.get_category_breakdown(SEED_USER_ID)
    amounts = [c["amount"] for c in breakdown]
    assert amounts == sorted(amounts, reverse=True)
    assert breakdown[0]["category"] == "Bills"
    assert all(isinstance(c["pct"], int) for c in breakdown)
    assert sum(c["pct"] for c in breakdown) == 100


def test_get_category_breakdown_empty(db_path):
    assert db.get_category_breakdown(9999) == []


# --------------------------------------------------------------------- #
# GET /profile route                                                   #
# --------------------------------------------------------------------- #

def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_shows_real_data(client):
    client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
    assert "295.25" in body
    assert "Bills" in body


def test_profile_empty_state_for_new_user(client):
    db.create_user("Fresh User", "fresh@spendly.com", _pw_hash("Password!1"))
    client.post(
        "/login",
        data={"email": "fresh@spendly.com", "password": "Password!1"},
        follow_redirects=False,
    )
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "No transactions yet" in body
    assert "₹0.00" in body


def _pw_hash(password):
    from werkzeug.security import generate_password_hash

    return generate_password_hash(password)
