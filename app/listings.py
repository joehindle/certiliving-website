from flask import (
    Blueprint, flash, redirect, render_template, request, url_for
)

import re

from werkzeug.exceptions import abort

from .db import get_db

bp = Blueprint('listings', __name__)


def _validate_enquiry_form(name, email, message):
    if not name:
        return "Name is required."
    if not email:
        return "Email is required."
    if not message:
        return "Message is required."
    if len(name) > 100:
        return "Name is too long."
    if len(message) > 2000:
        return "Message is too long."
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return "Invalid email address."
    return None


@bp.route('/')
def index():
    db = get_db()
    listings = db.execute(
        "SELECT * FROM listings ORDER BY created DESC"
    ).fetchall()

    return render_template('listings/index.html', listings=listings)

@bp.route('/listings/<int:listing_id>', methods=('GET', 'POST'))
def detail(listing_id):
    db = get_db()

    listing = db.execute(
        "SELECT * FROM listings WHERE id = ?",
        (listing_id,)
    ).fetchone()

    if listing is None:
        abort(404)

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
                VALUES (?, ?, ?, ?)
                """,
                (listing_id, name, email, message)
            )
            db.commit()

            flash("Enquiry sent!", "success")
            return redirect(url_for('listings.detail', listing_id=listing_id))

    return render_template('listings/detail.html', listing=listing)
