from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, url_for
)

import html
import re
from urllib.parse import urlencode

import resend
from werkzeug.exceptions import abort

from .db import get_db

bp = Blueprint('listings', __name__)

MAX_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 1500
DEFAULT_SORT = 'newest'
DEFAULT_PER_PAGE = 9
ALLOWED_PER_PAGE = {4, 6, 9}
SIMILAR_LISTINGS_LIMIT = 6
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


def _validate_enquiry_form(name, email, message):
    if not name:
        return "Name is required."
    if not email:
        return "Email is required."
    if not message:
        return "Message is required."
    if len(name) > MAX_NAME_LENGTH:
        return "Name is too long."
    if len(message) > MAX_MESSAGE_LENGTH:
        return "Message is too long."
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return "Invalid email address."
    return None


def _send_enquiry_email(listing, name, email, message):
    resend_api_key = current_app.config.get("RESEND_API_KEY")
    to_email = current_app.config.get("ENQUIRY_TO_EMAIL")
    from_email = current_app.config.get("RESEND_FROM_EMAIL")

    if not resend_api_key:
        raise RuntimeError("Missing RESEND_API_KEY")
    if not to_email:
        raise RuntimeError("Missing ENQUIRY_TO_EMAIL")
    if not from_email:
        raise RuntimeError("Missing RESEND_FROM_EMAIL")

    resend.api_key = resend_api_key

    safe_name = html.escape(name)
    safe_email = html.escape(email)
    safe_message = html.escape(message).replace("\n", "<br>")
    safe_title = html.escape(listing["title"])
    safe_city = html.escape(listing["city"])
    listing_url = url_for("listings.detail", listing_id=listing["id"], _external=True)

    resend.Emails.send({
        "from": from_email,
        "to": to_email,
        "subject": f"New enquiry for {listing['title']} ({listing['city']})",
        "html": (
            "<h2>New CertiLiving enquiry</h2>"
            f"<p><strong>Listing:</strong> {safe_title} ({safe_city})</p>"
            f"<p><strong>From:</strong> {safe_name} ({safe_email})</p>"
            f"<p><strong>Message:</strong><br>{safe_message}</p>"
            f"<p><a href=\"{listing_url}\">View listing</a></p>"
        ),
    })


@bp.route('/')
def index():
    db = get_db()
    highlighted_listings = db.execute(
        "SELECT * FROM listings ORDER BY created DESC LIMIT %s",
        (SIMILAR_LISTINGS_LIMIT,),
    ).fetchall()

    return render_template(
        'listings/index.html',
        highlighted_listings=highlighted_listings,
    )


@bp.route('/listings')
def all_listings():
    db = get_db()
    city = request.args.get('city', '').strip()
    room_type = request.args.get('room_type', '').strip()
    bills_only = request.args.get('bills_only', '').strip() == '1'
    min_rent_raw = request.args.get('min_rent', '').strip()
    max_rent_raw = request.args.get('max_rent', '').strip()
    sort = request.args.get('sort', DEFAULT_SORT).strip()
    page_raw = request.args.get('page', '1').strip()
    per_page_raw = request.args.get('per_page', '').strip()

    min_rent = None
    max_rent = None
    try:
        if min_rent_raw:
            min_rent = int(min_rent_raw)
    except ValueError:
        min_rent = None
    try:
        if max_rent_raw:
            max_rent = int(max_rent_raw)
    except ValueError:
        max_rent = None

    try:
        page = int(page_raw)
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    try:
        per_page = int(per_page_raw) if per_page_raw else DEFAULT_PER_PAGE
    except ValueError:
        per_page = DEFAULT_PER_PAGE
    if per_page not in ALLOWED_PER_PAGE:
        per_page = DEFAULT_PER_PAGE

    where_clauses = []
    params = []
    if city:
        where_clauses.append("city = %s")
        params.append(city)
    if room_type:
        where_clauses.append("room_type = %s")
        params.append(room_type)
    if bills_only:
        where_clauses.append("bills_included = TRUE")
    if min_rent is not None:
        where_clauses.append("rent_pcm >= %s")
        params.append(min_rent)
    if max_rent is not None:
        where_clauses.append("rent_pcm <= %s")
        params.append(max_rent)

    sort_map = {
        'newest': 'created DESC',
        'price_asc': 'rent_pcm ASC, created DESC',
        'price_desc': 'rent_pcm DESC, created DESC',
    }
    order_by = sort_map.get(sort, sort_map[DEFAULT_SORT])
    if sort not in sort_map:
        sort = DEFAULT_SORT

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    total = db.execute(
        "SELECT COUNT(*) AS total FROM listings" + where_sql,
        params,
    ).fetchone()["total"]

    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page

    query = f"SELECT * FROM listings{where_sql} ORDER BY {order_by} LIMIT %s OFFSET %s"
    listings = db.execute(query, (*params, per_page, offset)).fetchall()

    city_options = db.execute(
        "SELECT DISTINCT city FROM listings WHERE city IS NOT NULL AND city != '' ORDER BY city ASC"
    ).fetchall()
    room_type_options = db.execute(
        "SELECT DISTINCT room_type FROM listings WHERE room_type IS NOT NULL AND room_type != '' ORDER BY room_type ASC"
    ).fetchall()

    filters = {
        'city': city,
        'room_type': room_type,
        'bills_only': bills_only,
        'min_rent': min_rent_raw,
        'max_rent': max_rent_raw,
        'sort': sort,
        'per_page': str(per_page),
    }

    base_params = {
        'city': city,
        'room_type': room_type,
        'bills_only': '1' if bills_only else '',
        'min_rent': min_rent_raw,
        'max_rent': max_rent_raw,
        'sort': sort,
        'per_page': str(per_page),
    }

    def build_url(extra=None, drop=None):
        params_copy = dict(base_params)
        if drop:
            for key in drop:
                params_copy.pop(key, None)
        if extra:
            params_copy.update(extra)
        params_copy = {
            key: value for key, value in params_copy.items()
            if value not in ("", None)
        }
        querystring = urlencode(params_copy)
        if querystring:
            return f"{url_for('listings.all_listings')}?{querystring}"
        return url_for('listings.all_listings')

    active_chips = []
    if city:
        active_chips.append({
            'label': f"City: {city}",
            'remove_url': build_url(drop=['city', 'page']),
        })
    if room_type:
        active_chips.append({
            'label': f"Room: {room_type}",
            'remove_url': build_url(drop=['room_type', 'page']),
        })
    if bills_only:
        active_chips.append({
            'label': "Bills included",
            'remove_url': build_url(drop=['bills_only', 'page']),
        })
    if min_rent_raw:
        active_chips.append({
            'label': f"Min rent: {min_rent_raw}",
            'remove_url': build_url(drop=['min_rent', 'page']),
        })
    if max_rent_raw:
        active_chips.append({
            'label': f"Max rent: {max_rent_raw}",
            'remove_url': build_url(drop=['max_rent', 'page']),
        })
    if sort != DEFAULT_SORT:
        sort_label = "Price low to high" if sort == 'price_asc' else "Price high to low"
        active_chips.append({
            'label': f"Sort: {sort_label}",
            'remove_url': build_url(extra={'sort': DEFAULT_SORT}, drop=['page']),
        })

    page_links = [
        {
            'page': page_number,
            'url': build_url(extra={'page': page_number}),
            'is_current': page_number == page,
        }
        for page_number in range(1, total_pages + 1)
    ]

    pagination = {
        'page': page,
        'total_pages': total_pages,
        'total_results': total,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_url': build_url(extra={'page': page - 1}) if page > 1 else None,
        'next_url': build_url(extra={'page': page + 1}) if page < total_pages else None,
        'page_links': page_links,
    }

    return render_template(
        'listings/all.html',
        listings=listings,
        filters=filters,
        city_options=city_options,
        room_type_options=room_type_options,
        active_chips=active_chips,
        pagination=pagination,
    )


@bp.route('/listings/<int:listing_id>', methods=('GET', 'POST'))
def detail(listing_id):
    db = get_db()

    listing = db.execute(
        "SELECT * FROM listings WHERE id = %s",
        (listing_id,)
    ).fetchone()

    if listing is None:
        abort(404)

    listing_images = _listing_image_urls(listing)

    similar_listings = db.execute(
        """
        SELECT *
        FROM listings
        WHERE id != %s AND city = %s
        ORDER BY ABS(rent_pcm - %s) ASC, created DESC
        LIMIT %s
        """,
        (listing_id, listing["city"], listing["rent_pcm"], SIMILAR_LISTINGS_LIMIT),
    ).fetchall()

    if len(similar_listings) < SIMILAR_LISTINGS_LIMIT:
        needed = SIMILAR_LISTINGS_LIMIT - len(similar_listings)
        exclude_ids = [row["id"] for row in similar_listings]
        exclude_ids.append(listing_id)
        placeholders = ",".join("%s" for _ in exclude_ids)
        fallback_listings = db.execute(
            f"""
            SELECT *
            FROM listings
            WHERE id NOT IN ({placeholders})
            ORDER BY created DESC
            LIMIT %s
            """,
            (*exclude_ids, needed),
        ).fetchall()
        similar_listings = list(similar_listings) + list(fallback_listings)

    # Handle enquiry form submission
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        error = _validate_enquiry_form(name, email, message)

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
                _send_enquiry_email(listing, name, email, message)
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
        listing_images=listing_images,
        similar_listings=similar_listings,
    )
