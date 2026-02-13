from functools import wraps
from flask import Blueprint, current_app, request, session, redirect, url_for, render_template, flash
from .db import get_db  # adjust import to match your project

bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped

@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == current_app.config["ADMIN_PASSWORD"]:
            session["is_admin"] = True
            return redirect(url_for("admin.listings_index"))
        flash("Wrong password.")
    return render_template("admin/login.html")

@bp.route("/logout")
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
        title = request.form["title"]
        city = request.form["city"]
        rent_pcm = request.form["rent_pcm"]
        photo_url = request.form.get("photo_url") or None
        room_type = request.form.get("room_type") or None
        bills_included = 1 if request.form.get("bills_included") == "on" else 0
        available_from = request.form.get("available_from") or None
        description = request.form.get("description") or ""

        db = get_db()
        db.execute(
            """INSERT INTO listings
               (title, city, rent_pcm, photo_url, room_type, bills_included, available_from, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, city, rent_pcm, photo_url, room_type, bills_included, available_from, description),
        )
        db.commit()
        return redirect(url_for("admin.listings_index"))

    return render_template("admin/listings_form.html", listing=None)

@bp.route("/listings/<int:id>/edit", methods=("GET", "POST"))
@admin_required
def listings_edit(id):
    db = get_db()
    listing = db.execute("SELECT * FROM listings WHERE id = ?", (id,)).fetchone()
    if listing is None:
        return "Not found", 404

    if request.method == "POST":
        title = request.form["title"]
        city = request.form["city"]
        rent_pcm = request.form["rent_pcm"]
        photo_url = request.form.get("photo_url") or None
        room_type = request.form.get("room_type") or None
        bills_included = 1 if request.form.get("bills_included") == "on" else 0
        available_from = request.form.get("available_from") or None
        description = request.form.get("description") or ""

        db.execute(
            """UPDATE listings
               SET title=?, city=?, rent_pcm=?, photo_url=?, room_type=?, bills_included=?, available_from=?, description=?
               WHERE id=?""",
            (title, city, rent_pcm, photo_url, room_type, bills_included, available_from, description, id),
        )
        db.commit()
        return redirect(url_for("admin.listings_index"))

    return render_template("admin/listings_form.html", listing=listing)

@bp.route("/listings/<int:id>/delete", methods=("POST",))
@admin_required
def listings_delete(id):
    db = get_db()
    db.execute("DELETE FROM listings WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for("admin.listings_index"))
