from functools import wraps

from flask import Blueprint, current_app, request, session, redirect, url_for, render_template, flash
from .db import get_db
from .extensions import limiter
import time


bp = Blueprint("admin", __name__, url_prefix="/admin")


def _clean_optional(value):
    text = (value or "").strip()
    return text or None


def _parse_listing_form(form):
    return {
        "title": form["title"].strip(),
        "city": form["city"].strip(),
        "rent_pcm": form["rent_pcm"],
        "photo_url": _clean_optional(form.get("photo_url")),
        "room_type": _clean_optional(form.get("room_type")),
        "bills_included": 1 if form.get("bills_included") == "on" else 0,
        "available_from": _clean_optional(form.get("available_from")),
        "description": (form.get("description") or "").strip(),
    }


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped

@bp.route("/login", methods=("GET", "POST"))
@limiter.limit("5 per minute")
@limiter.limit("30 per hour")
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == current_app.config["ADMIN_PASSWORD"]:
            session["is_admin"] = True
            return redirect(url_for("admin.listings_index"))
        time.sleep(0.8)
        flash("Wrong password.")       
    return render_template("admin/login.html")

@bp.route("/logout", methods=("POST",))
@admin_required
def logout():
    session.clear()
    return redirect(url_for("admin.login"))

@bp.route("/")
@admin_required
def home():
    return redirect(url_for("admin.listings_index"))

@bp.route("/listings")
@admin_required
def listings_index():
    db = get_db()
    listings = db.execute("SELECT * FROM listings ORDER BY created DESC").fetchall()
    return render_template("admin/listings_index.html", listings=listings)

@bp.route("/listings/new", methods=("GET", "POST"))
@admin_required
def listings_new():
    if request.method == "POST":
        listing_data = _parse_listing_form(request.form)

        db = get_db()
        db.execute(
            """INSERT INTO listings
               (title, city, rent_pcm, photo_url, room_type, bills_included, available_from, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing_data["title"],
                listing_data["city"],
                listing_data["rent_pcm"],
                listing_data["photo_url"],
                listing_data["room_type"],
                listing_data["bills_included"],
                listing_data["available_from"],
                listing_data["description"],
            ),
        )
        db.commit()
        return redirect(url_for("admin.listings_index"))

    return render_template("admin/listings_form.html", listing=None)

@bp.route("/listings/<int:listing_id>/edit", methods=("GET", "POST"))
@admin_required
def listings_edit(listing_id):
    db = get_db()
    listing = db.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if listing is None:
        return "Not found", 404

    if request.method == "POST":
        listing_data = _parse_listing_form(request.form)

        db.execute(
            """UPDATE listings
               SET title=?, city=?, rent_pcm=?, photo_url=?, room_type=?, bills_included=?, available_from=?, description=?
               WHERE id=?""",
            (
                listing_data["title"],
                listing_data["city"],
                listing_data["rent_pcm"],
                listing_data["photo_url"],
                listing_data["room_type"],
                listing_data["bills_included"],
                listing_data["available_from"],
                listing_data["description"],
                listing_id,
            ),
        )
        db.commit()
        return redirect(url_for("admin.listings_index"))

    return render_template("admin/listings_form.html", listing=listing)

@bp.route("/listings/<int:listing_id>/delete", methods=("POST",))
@admin_required
def listings_delete(listing_id):
    db = get_db()
    db.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
    db.commit()
    return redirect(url_for("admin.listings_index"))
