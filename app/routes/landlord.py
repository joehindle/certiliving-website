from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, session

from .auth import role_required
from ..db import get_db
from ..extensions import limiter
from ..services.listing_forms import (
    listing_preview_from_form,
    normalize_supporting_photo_urls,
    parse_listing_form,
)
from ..services.listing_images import (
    delete_r2_image,
    delete_r2_images,
    process_listing_images,
)
from ..security import LISTING_WRITE_RATE_LIMITS, verify_protected_form


bp = Blueprint("landlord", __name__, url_prefix="/dashboard")

landlord_required = role_required("landlord", "admin")


def _current_owner_id():
    return session.get("auth_user_id")


def _current_account_status():
    return (session.get("auth_account_status") or "pending").strip().lower()


def _landlord_is_approved():
    roles = session.get("auth_roles") or []
    if "admin" in roles:
        return True
    return _current_account_status() == "approved"


def _refresh_account_status():
    user_id = _current_owner_id()
    if not user_id:
        return

    try:
        db = get_db()
        profile = db.execute(
            "SELECT account_status FROM profiles WHERE id = %s",
            (user_id,),
        ).fetchone()
    except Exception:
        current_app.logger.exception("Failed to refresh landlord account status")
        return

    if profile and profile.get("account_status"):
        session["auth_account_status"] = profile["account_status"].strip().lower()


def _dashboard_context(include_actions=True):
    return {
        "dashboard_kicker": "CertiLiving Dashboard",
        "dashboard_title": "Your listings",
        "dashboard_subtitle": "Create and manage the homes you personally list on CertiLiving.",
        "dashboard_listing_heading": "Your published listings",
        "dashboard_empty_title": "No listings yet",
        "dashboard_empty_copy": "Create your first listing to start showing your accommodation on the public site.",
        "new_listing_url": url_for("landlord.listings_new") if include_actions else None,
        "index_url": url_for("landlord.listings_index"),
        "edit_endpoint": "landlord.listings_edit",
        "delete_endpoint": "landlord.listings_delete",
        "account_status": _current_account_status(),
    }


def _redirect_if_not_approved():
    if _landlord_is_approved():
        return None
    flash(
        "Your account is waiting for admin approval before you can manage listings.",
        "info",
    )
    return redirect(url_for("landlord.listings_index"))


@bp.route("/")
@landlord_required
def home():
    return redirect(url_for("landlord.listings_index"))


@bp.route("/listings")
@landlord_required
def listings_index():
    _refresh_account_status()

    if not _landlord_is_approved():
        return render_template(
            "admin/listings_index.html",
            listings=[],
            account_pending=True,
            pending_title="Account under review",
            pending_copy=(
                "Thanks for registering. An admin needs to approve your account "
                "before you can create or manage listings."
            ),
            **_dashboard_context(include_actions=False),
        )

    db = get_db()
    listings = db.execute(
        "SELECT * FROM listings WHERE owner_id = %s ORDER BY created DESC",
        (_current_owner_id(),),
    ).fetchall()
    return render_template(
        "admin/listings_index.html",
        listings=listings,
        **_dashboard_context(),
    )


@bp.route("/listings/new", methods=("GET", "POST"))
@landlord_required
@limiter.limit(LISTING_WRITE_RATE_LIMITS[0], methods=["POST"])
@limiter.limit(LISTING_WRITE_RATE_LIMITS[1], methods=["POST"])
def listings_new():
    _refresh_account_status()
    pending_redirect = _redirect_if_not_approved()
    if pending_redirect:
        return pending_redirect

    if request.method == "POST":
        is_valid_submission, security_error = verify_protected_form(
            request.form,
            context="landlord listing form",
        )
        if not is_valid_submission:
            flash(security_error, "error")
            listing_preview = listing_preview_from_form(request.form)
            return render_template(
                "admin/listings_form.html",
                listing=listing_preview,
                **_dashboard_context(),
            )

        listing_data = parse_listing_form(request.form)
        cover_photo_file = request.files.get("cover_photo_file")
        supporting_photo_files = request.files.getlist("supporting_photo_files")

        try:
            photo_url, supporting_photo_urls = process_listing_images(
                cover_photo_file=cover_photo_file,
                supporting_photo_files=supporting_photo_files,
                replace_supporting=False,
            )
        except Exception as exc:
            flash(f"Image upload failed: {exc}", "error")
            listing_preview = listing_preview_from_form(request.form)
            return render_template(
                "admin/listings_form.html",
                listing=listing_preview,
                **_dashboard_context(),
            )

        db = get_db()
        db.execute(
            """INSERT INTO listings
               (title, city, rent_pcm, photo_url, supporting_photo_urls, room_type, bills_included, available_from, description, owner_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
                _current_owner_id(),
            ),
        )
        db.commit()
        return redirect(url_for("landlord.listings_index"))

    return render_template(
        "admin/listings_form.html",
        listing=None,
        **_dashboard_context(),
    )


@bp.route("/listings/<int:listing_id>/edit", methods=("GET", "POST"))
@landlord_required
def listings_edit(listing_id):
    _refresh_account_status()
    pending_redirect = _redirect_if_not_approved()
    if pending_redirect:
        return pending_redirect

    db = get_db()
    listing = db.execute(
        "SELECT * FROM listings WHERE id = %s AND owner_id = %s",
        (listing_id, _current_owner_id()),
    ).fetchone()
    if listing is None:
        return "Not found", 404

    if request.method == "POST":
        listing_data = parse_listing_form(request.form)
        photo_url = listing["photo_url"]
        supporting_photo_urls = normalize_supporting_photo_urls(
            listing.get("supporting_photo_urls")
        )
        cover_photo_file = request.files.get("cover_photo_file")
        supporting_photo_files = request.files.getlist("supporting_photo_files")
        replace_supporting = any(
            photo_file and photo_file.filename for photo_file in supporting_photo_files
        )

        try:
            new_photo_url, new_supporting_photo_urls = process_listing_images(
                cover_photo_file=cover_photo_file,
                supporting_photo_files=supporting_photo_files,
                existing_cover_photo_url=photo_url,
                existing_supporting_photo_urls=supporting_photo_urls,
                replace_supporting=replace_supporting,
            )
        except Exception as exc:
            flash(f"Image upload failed: {exc}", "error")
            listing_preview = listing_preview_from_form(
                request.form,
                existing_photo_url=listing["photo_url"],
                existing_supporting_photo_urls=listing.get("supporting_photo_urls"),
            )
            return render_template(
                "admin/listings_form.html",
                listing=listing_preview,
                **_dashboard_context(),
            )

        photo_url = new_photo_url
        if replace_supporting:
            delete_r2_images(supporting_photo_urls)
        supporting_photo_urls = new_supporting_photo_urls

        db.execute(
            """UPDATE listings
               SET title=%s, city=%s, rent_pcm=%s, photo_url=%s, supporting_photo_urls=%s, room_type=%s, bills_included=%s, available_from=%s, description=%s
               WHERE id=%s AND owner_id=%s""",
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
                _current_owner_id(),
            ),
        )
        db.commit()
        return redirect(url_for("landlord.listings_index"))

    return render_template(
        "admin/listings_form.html",
        listing=listing,
        **_dashboard_context(),
    )


@bp.route("/listings/<int:listing_id>/delete", methods=("POST",))
@landlord_required
def listings_delete(listing_id):
    _refresh_account_status()
    pending_redirect = _redirect_if_not_approved()
    if pending_redirect:
        return pending_redirect

    db = get_db()
    listing = db.execute(
        "SELECT photo_url, supporting_photo_urls FROM listings WHERE id = %s AND owner_id = %s",
        (listing_id, _current_owner_id()),
    ).fetchone()
    if listing:
        delete_r2_image(listing["photo_url"])
        delete_r2_images(listing.get("supporting_photo_urls"))
        db.execute(
            "DELETE FROM listings WHERE id = %s AND owner_id = %s",
            (listing_id, _current_owner_id()),
        )
        db.commit()
    return redirect(url_for("landlord.listings_index"))
