from pathlib import Path
import mimetypes
import uuid

import boto3
from botocore.client import Config
from flask import Blueprint, current_app, request, session, redirect, url_for, render_template, flash
from werkzeug.utils import secure_filename
from .auth import role_required
from .db import get_db


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


def _normalize_supporting_photo_urls(photo_urls):
    if not photo_urls:
        return []
    if isinstance(photo_urls, str):
        return [photo_urls]
    return [photo_url for photo_url in photo_urls if photo_url]


def _dedupe_photo_urls(photo_urls):
    deduped = []
    seen = set()
    for photo_url in photo_urls or []:
        if photo_url and photo_url not in seen:
            deduped.append(photo_url)
            seen.add(photo_url)
    return deduped


def _listing_preview_from_form(
    form,
    existing_photo_url=None,
    existing_supporting_photo_urls=None,
):
    return {
        "title": (form.get("title") or "").strip(),
        "city": (form.get("city") or "").strip(),
        "rent_pcm": (form.get("rent_pcm") or "").strip(),
        "photo_url": existing_photo_url,
        "supporting_photo_urls": _normalize_supporting_photo_urls(
            existing_supporting_photo_urls
        ),
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


def _delete_r2_images(photo_urls):
    for photo_url in photo_urls or []:
        _delete_r2_image(photo_url)


def _upload_listing_images(photo_files):
    uploaded_urls = []
    for photo_file in photo_files or []:
        if photo_file and photo_file.filename:
            uploaded_urls.append(_upload_listing_image(photo_file))
    return uploaded_urls


def _process_listing_images(
    cover_photo_file=None,
    supporting_photo_files=None,
    existing_cover_photo_url=None,
    existing_supporting_photo_urls=None,
    replace_supporting=False,
):
    uploaded_urls = []
    cover_photo_url = existing_cover_photo_url
    supporting_photo_urls = _normalize_supporting_photo_urls(
        existing_supporting_photo_urls
    )

    try:
        if cover_photo_file and cover_photo_file.filename:
            cover_photo_url = _upload_listing_image(cover_photo_file)
            uploaded_urls.append(cover_photo_url)
        elif not cover_photo_url:
            raise ValueError("Cover photo is required.")

        new_supporting_photo_urls = _upload_listing_images(supporting_photo_files)
        uploaded_urls.extend(new_supporting_photo_urls)
        if replace_supporting and new_supporting_photo_urls:
            supporting_photo_urls = new_supporting_photo_urls
        else:
            supporting_photo_urls.extend(new_supporting_photo_urls)
        return cover_photo_url, _dedupe_photo_urls(supporting_photo_urls)
    except Exception:
        _delete_r2_images(uploaded_urls)
        raise


admin_required = role_required("admin")


@bp.route("/login", methods=("GET", "POST"))
def login():
    return redirect(url_for("auth.login", next=url_for("admin.listings_index")))


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("listings.index"))

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
        cover_photo_file = request.files.get("cover_photo_file")
        supporting_photo_files = request.files.getlist("supporting_photo_files")

        try:
            photo_url, supporting_photo_urls = _process_listing_images(
                cover_photo_file=cover_photo_file,
                supporting_photo_files=supporting_photo_files,
                replace_supporting=False,
            )
        except Exception as exc:
            flash(f"Image upload failed: {exc}", "error")
            listing_preview = _listing_preview_from_form(request.form)
            return render_template("admin/listings_form.html", listing=listing_preview)

        db = get_db()
        db.execute(
            """INSERT INTO listings
               (title, city, rent_pcm, photo_url, supporting_photo_urls, room_type, bills_included, available_from, description)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                listing_data["title"],
                listing_data["city"],
                listing_data["rent_pcm"],
                photo_url,
                supporting_photo_urls,
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
        supporting_photo_urls = _normalize_supporting_photo_urls(
            listing.get("supporting_photo_urls")
        )
        cover_photo_file = request.files.get("cover_photo_file")
        supporting_photo_files = request.files.getlist("supporting_photo_files")
        replace_supporting = any(
            photo_file and photo_file.filename for photo_file in supporting_photo_files
        )

        try:
            new_photo_url, new_supporting_photo_urls = _process_listing_images(
                cover_photo_file=cover_photo_file,
                supporting_photo_files=supporting_photo_files,
                existing_cover_photo_url=photo_url,
                existing_supporting_photo_urls=supporting_photo_urls,
                replace_supporting=replace_supporting,
            )
        except Exception as exc:
            flash(f"Image upload failed: {exc}", "error")
            listing_preview = _listing_preview_from_form(
                request.form,
                existing_photo_url=listing["photo_url"],
                existing_supporting_photo_urls=listing.get("supporting_photo_urls"),
            )
            return render_template("admin/listings_form.html", listing=listing_preview)
        photo_url = new_photo_url
        if replace_supporting:
            _delete_r2_images(supporting_photo_urls)
        supporting_photo_urls = new_supporting_photo_urls

        db.execute(
            """UPDATE listings
               SET title=%s, city=%s, rent_pcm=%s, photo_url=%s, supporting_photo_urls=%s, room_type=%s, bills_included=%s, available_from=%s, description=%s
               WHERE id=%s""",
            (
                listing_data["title"],
                listing_data["city"],
                listing_data["rent_pcm"],
                photo_url,
                supporting_photo_urls,
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
    listing = db.execute(
        "SELECT photo_url, supporting_photo_urls FROM listings WHERE id = %s",
        (listing_id,),
    ).fetchone()
    if listing:
        _delete_r2_image(listing["photo_url"])
        _delete_r2_images(listing.get("supporting_photo_urls"))
    db.execute("DELETE FROM listings WHERE id = %s", (listing_id,))
    db.commit()
    return redirect(url_for("admin.listings_index"))
