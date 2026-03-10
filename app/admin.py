from functools import wraps
from pathlib import Path
import mimetypes
import uuid

import boto3
from botocore.client import Config
from flask import Blueprint, current_app, request, session, redirect, url_for, render_template, flash
from werkzeug.utils import secure_filename
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
        "room_type": _clean_optional(form.get("room_type")),
        "bills_included": form.get("bills_included") == "on",
        "available_from": _clean_optional(form.get("available_from")),
        "description": (form.get("description") or "").strip(),
    }


def _listing_preview_from_form(form, existing_photo_url=None):
    return {
        "title": (form.get("title") or "").strip(),
        "city": (form.get("city") or "").strip(),
        "rent_pcm": (form.get("rent_pcm") or "").strip(),
        "photo_url": existing_photo_url,
        "room_type": _clean_optional(form.get("room_type")),
        "bills_included": form.get("bills_included") == "on",
        "available_from": _clean_optional(form.get("available_from")),
        "description": (form.get("description") or "").strip(),
    }


def _build_r2_client():
    account_id = current_app.config.get("R2_ACCOUNT_ID")
    access_key = current_app.config.get("R2_ACCESS_KEY_ID")
    secret_key = current_app.config.get("R2_SECRET_ACCESS_KEY")
    if not account_id or not access_key or not secret_key:
        raise RuntimeError("R2 credentials are missing.")

    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _upload_listing_image(photo_file):
    filename = secure_filename(photo_file.filename or "")
    if not filename:
        return None

    ext = Path(filename).suffix.lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    if ext not in allowed_exts:
        raise ValueError("Please upload a JPG, PNG, WEBP, or GIF image.")

    content_type = photo_file.mimetype or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise ValueError("Invalid file type. Please upload an image.")

    key = f"listings/{uuid.uuid4().hex}{ext}"
    bucket = current_app.config.get("R2_BUCKET")
    base_url = (current_app.config.get("R2_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    missing = []
    if not bucket:
        missing.append("R2_BUCKET")
    if not base_url:
        missing.append("R2_PUBLIC_BASE_URL")
    if missing:
        raise RuntimeError("Missing R2 config: " + ", ".join(missing))

    client = _build_r2_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=photo_file.stream,
        ContentType=content_type,
    )
    return f"{base_url}/{key}"


def _delete_r2_image(photo_url):
    if not photo_url:
        return

    try:
        base_url = (current_app.config.get("R2_PUBLIC_BASE_URL") or "").strip().rstrip("/")
        if not base_url:
            return
        if not photo_url.startswith(base_url + "/"):
            return

        key = photo_url[len(base_url) + 1:]
        if not key:
            return

        bucket = current_app.config.get("R2_BUCKET")
        if not bucket:
            return

        client = _build_r2_client()
        client.delete_object(Bucket=bucket, Key=key)
    except Exception:
        current_app.logger.exception("Failed to delete R2 image: %s", photo_url)


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
        photo_url = None
        photo_file = request.files.get("photo_file")
        if photo_file and photo_file.filename:
            try:
                photo_url = _upload_listing_image(photo_file)
            except Exception as exc:
                flash(f"Image upload failed: {exc}", "error")
                listing_preview = _listing_preview_from_form(request.form)
                return render_template("admin/listings_form.html", listing=listing_preview)

        db = get_db()
        db.execute(
            """INSERT INTO listings
               (title, city, rent_pcm, photo_url, room_type, bills_included, available_from, description)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                listing_data["title"],
                listing_data["city"],
                listing_data["rent_pcm"],
                photo_url,
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
    listing = db.execute("SELECT * FROM listings WHERE id = %s", (listing_id,)).fetchone()
    if listing is None:
        return "Not found", 404

    if request.method == "POST":
        listing_data = _parse_listing_form(request.form)
        photo_url = listing["photo_url"]
        photo_file = request.files.get("photo_file")
        if photo_file and photo_file.filename:
            try:
                new_photo_url = _upload_listing_image(photo_file)
            except Exception as exc:
                flash(f"Image upload failed: {exc}", "error")
                listing_preview = _listing_preview_from_form(
                    request.form,
                    existing_photo_url=listing["photo_url"],
                )
                return render_template("admin/listings_form.html", listing=listing_preview)
            _delete_r2_image(listing["photo_url"])
            photo_url = new_photo_url

        db.execute(
            """UPDATE listings
               SET title=%s, city=%s, rent_pcm=%s, photo_url=%s, room_type=%s, bills_included=%s, available_from=%s, description=%s
               WHERE id=%s""",
            (
                listing_data["title"],
                listing_data["city"],
                listing_data["rent_pcm"],
                photo_url,
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
    listing = db.execute("SELECT photo_url FROM listings WHERE id = %s", (listing_id,)).fetchone()
    _delete_r2_image(listing["photo_url"] if listing else None)
    db.execute("DELETE FROM listings WHERE id = %s", (listing_id,))
    db.commit()
    return redirect(url_for("admin.listings_index"))
