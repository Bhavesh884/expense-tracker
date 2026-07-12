"""Tests for the Date Filter for Profile Page feature (Step 07 — Date Filter).

Covers the `category` extension to `_build_expense_filters()` /
`count_transactions()` / `get_transactions_page()` in database/db.py, the
`build_preset_ranges()` helper and `EXPENSE_CATEGORIES` allow-list in app.py,
and the `/profile` route's date-range + category filter, range validation,
active-filter summary, and pagination.

The seeded demo user (id 1) has 8 expenses totalling 295.25 across 7
categories, all dated July 2026:
    2026-07-02 Food          12.50 Lunch
    2026-07-04 Transport     40.00 Monthly metro pass
    2026-07-06 Bills         90.00 Electricity
    2026-07-09 Health        25.00 Pharmacy
    2026-07-12 Entertainment 30.00 Cinema
    2026-07-15 Shopping      60.00 T-shirt
    2026-07-18 Other         15.00 Misc
    2026-07-21 Food          22.75 Groceries
"""

import datetime

import database.db as db
from app import EXPENSE_CATEGORIES, build_preset_ranges

SEED_USER_ID = 1


def _pw_hash(password):
    from werkzeug.security import generate_password_hash

    return generate_password_hash(password)


def _login_demo(client):
    return client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )


# --------------------------------------------------------------------- #
# DB layer: category filter on count_transactions / get_transactions_page #
# --------------------------------------------------------------------- #

def test_count_transactions_filters_by_category_only(db_path):
    total = db.count_transactions(SEED_USER_ID, category="Food")
    assert total == 2, "Food category should match Lunch and Groceries"


def test_get_transactions_page_filters_by_category_only(db_path):
    rows = db.get_transactions_page(SEED_USER_ID, 10, 0, category="Food")
    descriptions = {r["description"] for r in rows}
    assert descriptions == {"Lunch", "Groceries"}


def test_date_range_and_category_combine(db_path):
    total = db.count_transactions(
        SEED_USER_ID, start_date="2026-07-01", end_date="2026-07-10", category="Food"
    )
    assert total == 1, "Only the 2026-07-02 Food row falls in this range"

    rows = db.get_transactions_page(
        SEED_USER_ID, 10, 0, start_date="2026-07-01", end_date="2026-07-10", category="Food"
    )
    assert len(rows) == 1
    assert rows[0]["description"] == "Lunch"
    assert rows[0]["category"] == "Food"


def test_date_range_alone_still_works(db_path):
    """Regression: date-range filtering without a category is unaffected."""
    total = db.count_transactions(SEED_USER_ID, start_date="2026-07-01", end_date="2026-07-10")
    assert total == 4, "Rows dated 07-02, 07-04, 07-06, 07-09 fall in this range"

    rows = db.get_transactions_page(
        SEED_USER_ID, 10, 0, start_date="2026-07-01", end_date="2026-07-10"
    )
    dates = {r["date"] for r in rows}
    assert dates == {"2026-07-02", "2026-07-04", "2026-07-06", "2026-07-09"}


def test_get_transactions_page_newest_first_with_expected_keys(db_path):
    rows = db.get_transactions_page(SEED_USER_ID, 10, 0)
    assert len(rows) == 8
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True), "Rows must be newest-first"
    assert set(rows[0].keys()) == {"id", "date", "description", "category", "amount"}


def test_category_none_behaves_as_no_filter(db_path):
    """Backward compatibility: category=None (or omitted) means no filter."""
    total_explicit_none = db.count_transactions(SEED_USER_ID, category=None)
    total_omitted = db.count_transactions(SEED_USER_ID)
    assert total_explicit_none == 8
    assert total_omitted == 8

    rows = db.get_transactions_page(SEED_USER_ID, 10, 0, category=None)
    assert len(rows) == 8


def test_category_parameterization_prevents_injection(db_path):
    """A category value crafted to look like SQL injection must bind as a
    literal string and match zero rows, never bypass the filter."""
    malicious = "Food' OR '1'='1"
    total = db.count_transactions(SEED_USER_ID, category=malicious)
    assert total == 0, "Injection-style category value must not widen the result set"

    rows = db.get_transactions_page(SEED_USER_ID, 10, 0, category=malicious)
    assert rows == []


# --------------------------------------------------------------------- #
# app.py: build_preset_ranges()                                        #
# --------------------------------------------------------------------- #

def test_build_preset_ranges_shape_and_keys():
    presets = build_preset_ranges(datetime.date(2026, 7, 12))
    assert set(presets.keys()) == {"month", "days30", "year"}
    for key in ("month", "days30", "year"):
        assert set(presets[key].keys()) == {"label", "start", "end"}


def test_build_preset_ranges_this_month_is_full_period():
    presets = build_preset_ranges(datetime.date(2026, 7, 12))
    month = presets["month"]
    assert month["start"] == "2026-07-01"
    assert month["end"] == "2026-07-31", "End should be the last day of the month, not today"
    assert month["label"] == "This month"


def test_build_preset_ranges_this_year_is_full_period():
    presets = build_preset_ranges(datetime.date(2026, 7, 12))
    year = presets["year"]
    assert year["start"] == "2026-01-01"
    assert year["end"] == "2026-12-31"
    assert year["label"] == "This year"


def test_build_preset_ranges_last_30_days_trailing_window():
    presets = build_preset_ranges(datetime.date(2026, 7, 12))
    days30 = presets["days30"]
    assert days30["end"] == "2026-07-12", "Trailing window ends on 'today'"
    assert days30["start"] == "2026-06-13"
    assert days30["label"] == "Last 30 days"


def test_build_preset_ranges_month_boundary_february():
    """Prove the last-day-of-month logic works across a short month."""
    presets = build_preset_ranges(datetime.date(2026, 2, 15))
    month = presets["month"]
    assert month["start"] == "2026-02-01"
    assert month["end"] == "2026-02-28"


def test_expense_categories_allow_list():
    assert EXPENSE_CATEGORIES == (
        "Food",
        "Transport",
        "Bills",
        "Health",
        "Entertainment",
        "Shopping",
        "Other",
    )


# --------------------------------------------------------------------- #
# GET /profile route: auth guard                                       #
# --------------------------------------------------------------------- #

def test_profile_requires_login(client):
    resp = client.get("/profile?open=1&category=Food")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# --------------------------------------------------------------------- #
# GET /profile route: category filter                                  #
# --------------------------------------------------------------------- #

def test_profile_category_filter_narrows_results(client):
    _login_demo(client)
    resp = client.get("/profile?open=1&category=Food")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Lunch" in body
    assert "Groceries" in body
    # None of the non-Food descriptions should appear in the filtered table.
    assert "Electricity" not in body
    assert "Cinema" not in body
    assert "2 transaction" in body, "Pagination summary should reflect 2 matches"


def test_profile_date_and_category_combined(client):
    _login_demo(client)
    resp = client.get("/profile?open=1&start=2026-07-01&end=2026-07-10&category=Food")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Lunch" in body
    assert "Groceries" not in body
    assert "1 transaction" in body


# --------------------------------------------------------------------- #
# GET /profile route: inverted range validation                        #
# --------------------------------------------------------------------- #

def test_profile_inverted_date_range_shows_validation_message(client):
    _login_demo(client)
    resp = client.get("/profile?open=1&start=2026-07-20&end=2026-07-01")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "tx-filter-error" in body
    assert "after the" in body.lower() or "is after" in body.lower()
    # Must not silently render a normal filtered table of results.
    assert "No transactions found" not in body


def test_profile_valid_range_does_not_show_error(client):
    _login_demo(client)
    resp = client.get("/profile?open=1&start=2026-07-01&end=2026-07-10")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "tx-filter-error" not in body


# --------------------------------------------------------------------- #
# GET /profile route: invalid / unknown category handling              #
# --------------------------------------------------------------------- #

def test_profile_unknown_category_treated_as_all(client):
    _login_demo(client)
    resp = client.get("/profile?open=1&category=DoesNotExist")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "8 transaction" in body, "Unknown category should behave like no filter"


def test_profile_injection_style_category_falls_back_to_all(client):
    _login_demo(client)
    resp = client.get("/profile?open=1&category=" + "Food' OR '1'='1")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Falls back to "All" (8 rows) — must not error, and must not narrow to
    # zero-by-injection either.
    assert "8 transaction" in body


# --------------------------------------------------------------------- #
# GET /profile route: active-filter summary                            #
# --------------------------------------------------------------------- #

def test_profile_active_filter_summary_present_when_filtered(client):
    _login_demo(client)
    resp = client.get("/profile?open=1&category=Food")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "tx-filter-summary" in body
    assert "Food" in body
    assert "Clear filters" in body


def test_profile_active_filter_summary_absent_when_no_filter(client):
    _login_demo(client)
    resp = client.get("/profile?open=1")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "tx-filter-summary" not in body


# --------------------------------------------------------------------- #
# GET /profile route: category select options                          #
# --------------------------------------------------------------------- #

def test_profile_category_select_renders_all_options(client):
    _login_demo(client)
    resp = client.get("/profile?open=1")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'name="category"' in body
    assert "<select" in body
    for category in EXPENSE_CATEGORIES:
        assert f'value="{category}"' in body, f"Missing option for {category}"


# --------------------------------------------------------------------- #
# GET /profile route: category threaded through pagination/filter links #
# --------------------------------------------------------------------- #

def test_profile_category_state_retained_in_select_and_links(client):
    _login_demo(client)
    resp = client.get("/profile?open=1&category=Food")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # The select's Food option should be marked selected.
    assert 'value="Food" selected' in body, "Selected option should retain filter state"
    # Preset / clear links should carry the active category forward.
    assert "category=Food" in body


# --------------------------------------------------------------------- #
# GET /profile route: empty state for a brand-new user                 #
# --------------------------------------------------------------------- #

def test_profile_empty_state_with_category_filter_for_new_user(client):
    db.create_user("Fresh User", "fresh@spendly.com", _pw_hash("Password!1"))
    client.post(
        "/login",
        data={"email": "fresh@spendly.com", "password": "Password!1"},
        follow_redirects=False,
    )
    resp = client.get("/profile?open=1&category=Food")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "profile-empty" in body
    assert "No transactions found" in body or "No transactions yet" in body
