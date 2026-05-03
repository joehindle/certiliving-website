from flask import flash, redirect, render_template, request, url_for

from ...db import get_db
from ...extensions import limiter
from ...security import LISTING_WRITE_RATE_LIMITS, verify_protected_form
from ...services.listing_forms import (
    listing_preview_from_form,
    normalize_supporting_photo_urls,
    parse_listing_form,
)
from ...services.listing_images import (
    delete_r2_image,
    delete_r2_images,
    process_listing_images,
)


def register_routes(bp, admin_required, admin_tabs):
    @bp.route("/listings")
    @admin_required
    def listings_index():
        db = get_db()
        
        owner_id_filter = request.args.get('owner_id')
        
        # Get distinct owners for the filter dropdown
        owners = db.execute(
            """SELECT DISTINCT p.id, p.display_name 
               FROM listings l
               JOIN profiles p ON l.owner_id = p.id
               WHERE p.display_name IS NOT NULL
               ORDER BY p.display_name"""
        ).fetchall()

        if owner_id_filter:
            listings = db.execute(
                """SELECT l.*, p.display_name as owner_display_name 
                   FROM listings l 
                   LEFT JOIN profiles p ON l.owner_id = p.id
                   WHERE l.owner_id = %s
                   ORDER BY l.created DESC""",
                (owner_id_filter,)
            ).fetchall()
        else:
            listings = db.execute(
                """SELECT l.*, p.display_name as owner_display_name 
                   FROM listings l 
                   LEFT JOIN profiles p ON l.owner_id = p.id
                   ORDER BY l.created DESC"""
            ).fetchall()
            
        return render_template(
            "admin/listings_index.html",
            listings=listings,
            admin_tabs=admin_tabs("listings"),
            listing_status_endpoint="admin.listings_update_status",
            owners=owners,
            current_owner_filter=owner_id_filter,
            is_admin_dashboard=True
        )

    @bp.route("/listings/new", methods=("GET", "POST"))
    @admin_required
    @limiter.limit(LISTING_WRITE_RATE_LIMITS[0], methods=["POST"])
    @limiter.limit(LISTING_WRITE_RATE_LIMITS[1], methods=["POST"])
    def listings_new():
        if request.method == "POST":
            is_valid_submission, security_error = verify_protected_form(
                request.form,
                context="admin listing form",
            )
            if not is_valid_submission:
                flash(security_error, "error")
                listing_preview = listing_preview_from_form(request.form)
                return render_template("admin/listings_form.html", listing=listing_preview)

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
                return render_template("admin/listings_form.html", listing=listing_preview)

            db = get_db()
            db.execute(
                """INSERT INTO listings
                   (title, city, rent_pcm, photo_url, supporting_photo_urls, room_type, bills_included, available_from, description, status)
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
                    "published",
                ),
            )
            db.commit()
            return redirect(url_for("admin.listings_index"))

        return render_template("admin/listings_form.html", listing=None)

    @bp.route("/listings/<int:listing_id>/edit", methods=("GET", "POST"))
    @admin_required
    def listings_edit(listing_id):
        db = get_db()
        listing = db.execute(
            "SELECT * FROM listings WHERE id = %s",
            (listing_id,),
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
                return render_template("admin/listings_form.html", listing=listing_preview)

            photo_url = new_photo_url
            if replace_supporting:
                delete_r2_images(supporting_photo_urls)
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
            delete_r2_image(listing["photo_url"])
            delete_r2_images(listing.get("supporting_photo_urls"))
        db.execute("DELETE FROM listings WHERE id = %s", (listing_id,))
        db.commit()
        return redirect(url_for("admin.listings_index"))

    @bp.route("/listings/<int:listing_id>/status", methods=("POST",))
    @admin_required
    def listings_update_status(listing_id):
        status = (request.form.get("status") or "").strip().lower()
        if status not in {"pending_review", "published", "rejected"}:
            flash("Choose a valid listing status.", "error")
            return redirect(url_for("admin.listings_index"))

        db = get_db()
        db.execute(
            "UPDATE listings SET status = %s WHERE id = %s",
            (status, listing_id),
        )
        db.commit()
        flash("Listing status updated.", "success")
        return redirect(url_for("admin.listings_index"))
