import os
import sqlite3

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "spendly.db")


def get_db():
    """Return a SQLite connection with dict-like rows and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the users and expenses tables if they do not already exist."""
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    """Return the user row matching the email, or None if it does not exist."""
    email = (email or "").strip().lower()
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return user


def create_user(name, email, password_hash):
    """Insert a new user and return the generated id."""
    email = (email or "").strip().lower()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_user_by_id(user_id):
    """Return the user row matching the id, or None if it does not exist."""
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


def get_summary_stats(user_id):
    """Return spending summary for a user: total spent, transaction count, top category."""
    conn = get_db()

    total_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    category_row = conn.execute(
        "SELECT category FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        (user_id,),
    ).fetchone()

    conn.close()

    transaction_count = total_row[1]
    if transaction_count == 0:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    top_category = category_row[0] if category_row is not None else "—"

    return {
        "total_spent": float(total_row[0]),
        "transaction_count": transaction_count,
        "top_category": top_category,
    }


def get_recent_transactions(user_id, limit=10):
    """Return the user's most recent expenses, newest first, capped at `limit`."""
    conn = get_db()
    rows = conn.execute(
        "SELECT date, description, category, amount "
        "FROM expenses "
        "WHERE user_id = ? "
        "ORDER BY date DESC, id DESC "
        "LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _build_expense_filters(user_id, start_date=None, end_date=None):
    """Return a (where_clause, params) pair filtering a user's expenses by date range."""
    clauses = ["user_id = ?"]
    params = [user_id]
    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)
    return " AND ".join(clauses), params


def count_transactions(user_id, start_date=None, end_date=None):
    """Return the number of a user's expenses, optionally within a date range."""
    where, params = _build_expense_filters(user_id, start_date, end_date)
    conn = get_db()
    total = conn.execute(
        "SELECT COUNT(*) FROM expenses WHERE " + where, params
    ).fetchone()[0]
    conn.close()
    return total


def get_transactions_page(user_id, limit, offset, start_date=None, end_date=None):
    """Return one page of a user's expenses, newest first, optionally within a date range."""
    where, params = _build_expense_filters(user_id, start_date, end_date)
    conn = get_db()
    rows = conn.execute(
        "SELECT id, date, description, category, amount "
        "FROM expenses WHERE " + where + " "
        "ORDER BY date DESC, id DESC "
        "LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_category_breakdown(user_id):
    """Return per-category spend totals for a user with integer percentages summing to 100."""
    conn = get_db()
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total "
        "FROM expenses WHERE user_id = ? "
        "GROUP BY category ORDER BY total DESC",
        (user_id,),
    ).fetchall()
    conn.close()

    if not rows:
        return []

    grand_total = sum(row["total"] for row in rows)
    if grand_total == 0:
        return []

    breakdown = []
    for row in rows:
        raw_pct = (row["total"] / grand_total) * 100
        breakdown.append(
            {
                "category": row["category"],
                "amount": float(row["total"]),
                "pct": int(raw_pct),
                "remainder": raw_pct - int(raw_pct),
            }
        )

    leftover = 100 - sum(item["pct"] for item in breakdown)
    for item in sorted(breakdown, key=lambda x: x["remainder"], reverse=True)[:leftover]:
        item["pct"] += 1

    return [
        {"category": item["category"], "amount": item["amount"], "pct": item["pct"]}
        for item in breakdown
    ]


def seed_db():
    """Insert one demo user and eight sample expenses, only if the DB is empty."""
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    expenses = [
        (user_id, 12.50, "Food", "2026-07-02", "Lunch"),
        (user_id, 40.00, "Transport", "2026-07-04", "Monthly metro pass"),
        (user_id, 90.00, "Bills", "2026-07-06", "Electricity"),
        (user_id, 25.00, "Health", "2026-07-09", "Pharmacy"),
        (user_id, 30.00, "Entertainment", "2026-07-12", "Cinema"),
        (user_id, 60.00, "Shopping", "2026-07-15", "T-shirt"),
        (user_id, 15.00, "Other", "2026-07-18", "Misc"),
        (user_id, 22.75, "Food", "2026-07-21", "Groceries"),
    ]
    conn.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        expenses,
    )

    conn.commit()
    conn.close()
