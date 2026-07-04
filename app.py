import os
import re
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import create_user, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


def is_strong_password(password):
    """True if the password is 8+ chars with upper, lower, and a special char."""
    return (
        len(password) >= 8
        and re.search(r"[a-z]", password)
        and re.search(r"[A-Z]", password)
        and re.search(r"[^A-Za-z0-9]", password)
    )

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
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Step 05 is UI-first: the page is driven by hardcoded sample data so the
    # layout can be validated before real queries are wired in a later step.
    user = {
        "name": session.get("user_name", "Demo User"),
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "July 2026",
    }

    summary = {
        "total_spent": "295.25",
        "transaction_count": 8,
        "top_category": "Bills",
    }

    transactions = [
        {"date": "2026-07-21", "description": "Groceries", "category": "Food", "amount": "22.75"},
        {"date": "2026-07-18", "description": "Misc", "category": "Other", "amount": "15.00"},
        {"date": "2026-07-15", "description": "T-shirt", "category": "Shopping", "amount": "60.00"},
        {"date": "2026-07-12", "description": "Cinema", "category": "Entertainment", "amount": "30.00"},
        {"date": "2026-07-09", "description": "Pharmacy", "category": "Health", "amount": "25.00"},
        {"date": "2026-07-06", "description": "Electricity", "category": "Bills", "amount": "90.00"},
        {"date": "2026-07-04", "description": "Monthly metro pass", "category": "Transport", "amount": "40.00"},
        {"date": "2026-07-02", "description": "Lunch", "category": "Food", "amount": "12.50"},
    ]

    breakdown = [
        {"category": "Bills", "amount": "90.00", "width": "profile-bar-fill--w1"},
        {"category": "Shopping", "amount": "60.00", "width": "profile-bar-fill--w2"},
        {"category": "Transport", "amount": "40.00", "width": "profile-bar-fill--w3"},
        {"category": "Food", "amount": "35.25", "width": "profile-bar-fill--w4"},
        {"category": "Entertainment", "amount": "30.00", "width": "profile-bar-fill--w5"},
    ]

    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        transactions=transactions,
        breakdown=breakdown,
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
