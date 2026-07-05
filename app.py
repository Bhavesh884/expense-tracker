import math
import os
import re
import sqlite3
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import (
    count_transactions,
    create_user,
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_transactions_page,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Number of expenses shown per page in the "All transactions" section.
TRANSACTIONS_PER_PAGE = 8


def is_strong_password(password):
    """True if the password is 8+ chars with upper, lower, and a special char."""
    return (
        len(password) >= 8
        and re.search(r"[a-z]", password)
        and re.search(r"[A-Z]", password)
        and re.search(r"[^A-Za-z0-9]", password)
    )


def build_initials(name):
    """Return up to two uppercase initials from a name, or '?' if unavailable."""
    parts = (name or "").split()
    initials = "".join(part[0] for part in parts[:2])
    return initials.upper() or "?"


def format_member_since(created_at):
    """Format a users.created_at timestamp as 'Month YYYY', or '—' if unparseable."""
    try:
        return datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
    except (TypeError, ValueError):
        return "—"


def parse_date_arg(value):
    """Return a 'YYYY-MM-DD' date string if valid, else None."""
    value = (value or "").strip()
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        return None

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not name or not email or not password or not confirm_password:
        return render_template("register.html", error="All fields are required.")

    if not is_strong_password(password):
        return render_template(
            "register.html",
            error=(
                "Password must be at least 8 characters and include an "
                "uppercase letter, a lowercase letter, and a special character."
            ),
        )

    if password != confirm_password:
        return render_template(
            "register.html", error="Passwords do not match."
        )

    if get_user_by_email(email):
        return render_template(
            "register.html", error="That email is already registered."
        )

    try:
        create_user(name, email, generate_password_hash(password))
    except sqlite3.IntegrityError:
        return render_template(
            "register.html", error="That email is already registered."
        )

    flash("Account created successfully. Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("landing"))
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    generic_error = "Invalid email or password. Please try again."

    if not email or not password:
        return render_template("login.html", error=generic_error, email=email)

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error=generic_error, email=email)

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    flash(f"Welcome back, {user['name']}!", "success")
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out successfully.", "success")
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    account = get_user_by_id(user_id)
    if account is None:
        session.clear()
        return redirect(url_for("login"))

    user = {
        "name": account["name"],
        "email": account["email"],
        "initials": build_initials(account["name"]),
        "member_since": format_member_since(account["created_at"]),
    }

    stats = get_summary_stats(user_id)
    summary = {
        "total_spent": "{:,.2f}".format(stats["total_spent"]),
        "transaction_count": stats["transaction_count"],
        "top_category": stats["top_category"],
    }

    transactions = [
        {
            "date": t["date"],
            "description": t["description"],
            "category": t["category"],
            "amount": "{:,.2f}".format(t["amount"]),
        }
        for t in get_recent_transactions(user_id)
    ]

    breakdown = [
        {
            "category": c["category"],
            "amount": "{:,.2f}".format(c["amount"]),
            "pct": c["pct"],
            "width_class": "bar-w" + str(round(c["pct"] / 5) * 5),
        }
        for c in get_category_breakdown(user_id)
    ]

    # "All transactions" section: optional date-range filter + pagination.
    start_date = parse_date_arg(request.args.get("start"))
    end_date = parse_date_arg(request.args.get("end"))

    total = count_transactions(user_id, start_date, end_date)
    total_pages = max(1, math.ceil(total / TRANSACTIONS_PER_PAGE))

    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, min(page, total_pages))

    offset = (page - 1) * TRANSACTIONS_PER_PAGE
    all_transactions = [
        {
            "id": t["id"],
            "date": t["date"],
            "description": t["description"],
            "category": t["category"],
            "amount": "{:,.2f}".format(t["amount"]),
        }
        for t in get_transactions_page(
            user_id, TRANSACTIONS_PER_PAGE, offset, start_date, end_date
        )
    ]

    pagination = {
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
    }

    filters = {"start": start_date or "", "end": end_date or ""}

    all_tx_open = any(
        request.args.get(key) is not None
        for key in ("open", "page", "start", "end")
    )

    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        transactions=transactions,
        breakdown=breakdown,
        all_transactions=all_transactions,
        pagination=pagination,
        filters=filters,
        all_tx_open=all_tx_open,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
