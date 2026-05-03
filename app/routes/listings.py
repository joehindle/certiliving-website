from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for
)

import re

from werkzeug.exceptions import abort

from ..db import get_db
from ..services.enquiry_services import send_enquiry_email, validate_enquiry_form
from ..services.listing_filters import get_filtered_listings_context
from ..services.listing_queries import get_highlighted_listings, get_similar_listings
from ..extensions import limiter
from ..security import (
    ENQUIRY_RATE_LIMITS,
    verify_protected_form,
    verify_turnstile_token,
)

bp = Blueprint('listings', __name__)

PLACEHOLDER_DETAIL_IMAGE = 'https://via.placeholder.com/900x600'


def _listing_image_urls(listing):
    image_urls = []

    cover_photo_url = listing.get('photo_url')
    if cover_photo_url:
        image_urls.append(cover_photo_url)

    supporting_photo_urls = listing.get('supporting_photo_urls') or []
    if isinstance(supporting_photo_urls, str):
        supporting_photo_urls = [supporting_photo_urls]
    image_urls.extend(
        photo_url for photo_url in supporting_photo_urls if photo_url
    )

    return image_urls or [PLACEHOLDER_DETAIL_IMAGE]


def _listing_description_paragraphs(description):
    text = (description or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    return [
        paragraph.strip()
        for paragraph in re.split(r"\n+", text)
        if paragraph.strip()
    ]


def _verify_turnstile_token(token, remoteip=None):
    return verify_turnstile_token(token, remoteip)


@bp.route('/')
def index():
    db = get_db()
    return render_template(
        'listings/index.html',
        highlighted_listings=get_highlighted_listings(db),
    )


@bp.route('/listings')
def all_listings():
    db = get_db()
    return render_template(
        'listings/all.html',
        **get_filtered_listings_context(db, request.args),
    )


@bp.route('/listings/<int:listing_id>', methods=('GET', 'POST'))
@limiter.limit(ENQUIRY_RATE_LIMITS[0], methods=["POST"])
@limiter.limit(ENQUIRY_RATE_LIMITS[1], methods=["POST"])
def detail(listing_id):
    db = get_db()

    listing = db.execute(
        "SELECT * FROM listings WHERE id = %s AND status = 'published'",
        (listing_id,)
    ).fetchone()

    if listing is None:
        abort(404)

    listing_images = _listing_image_urls(listing)
    current_image_raw = request.args.get("image", "0").strip()
    try:
        current_image_index = int(current_image_raw)
    except ValueError:
        current_image_index = 0
    if current_image_index < 0:
        current_image_index = 0
    if current_image_index >= len(listing_images):
        current_image_index = 0

    current_image_url = listing_images[current_image_index]
    prev_image_url = None
    next_image_url = None
    if len(listing_images) > 1:
        prev_index = (current_image_index - 1) % len(listing_images)
        next_index = (current_image_index + 1) % len(listing_images)
        prev_image_url = url_for("listings.detail", listing_id=listing_id, image=prev_index)
        next_image_url = url_for("listings.detail", listing_id=listing_id, image=next_index)

    # Handle enquiry form submission
    if request.method == 'POST':
        is_valid_submission, security_error = verify_protected_form(
            request.form,
            context=f"enquiry for listing_id={listing_id}",
        )
        if not is_valid_submission and security_error == "Please try again.":
            return redirect(url_for('listings.detail', listing_id=listing_id))

        if not is_valid_submission:
            flash(security_error, "error")
            return redirect(url_for('listings.detail', listing_id=listing_id))

        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        error = validate_enquiry_form(name, email, message)

        # ---------- IF ERROR ----------
        if error:
            flash(error, "error")
        else:
            db.execute(
                """
                INSERT INTO enquiries
                (listing_id, student_name, student_email, message)
                VALUES (%s, %s, %s, %s)
                """,
                (listing_id, name, email, message)
            )
            db.commit()
            try:
                send_enquiry_email(listing, name, email, message)
                flash("Enquiry sent!", "success")
            except Exception:
                current_app.logger.exception(
                    "Failed to send enquiry email for listing_id=%s",
                    listing_id,
                )
                flash("Enquiry saved, but email notification failed.", "error")
            return redirect(url_for('listings.detail', listing_id=listing_id))

    return render_template(
        'listings/detail.html',
        listing=listing,
        description_paragraphs=_listing_description_paragraphs(
            listing.get("description")
        ),
        listing_images=listing_images,
        current_image_index=current_image_index,
        current_image_url=current_image_url,
        prev_image_url=prev_image_url,
        next_image_url=next_image_url,
        similar_listings=get_similar_listings(db, listing),
    )
