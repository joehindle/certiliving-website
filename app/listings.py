from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)

import re

from werkzeug.exceptions import abort

from .db import get_db

bp = Blueprint('listings', __name__)

@bp.route('/')
def index():
    db = get_db()
    listings = db.execute(
        "SELECT * FROM listings ORDER BY created DESC"
    ).fetchall()

    return render_template('listings/index.html', listings=listings)

@bp.route('/listings/<int:id>', methods=('GET', 'POST'))
def detail(id):
    db = get_db()

    listing = db.execute(
        "SELECT * FROM listings WHERE id = ?",
        (id,)
    ).fetchone()

    if listing is None:
        return "Listing not found", 404

    # Handle enquiry form submission
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        error = None

        # ---------- REQUIRED ----------
        if not name:
            error = "Name is required."
        elif not email:
            error = "Email is required."
        elif not message:
            error = "Message is required."

        # ---------- LENGTH ----------
        elif len(name) > 100:
            error = "Name is too long."
        elif len(message) > 2000:
            error = "Message is too long."

        # ---------- EMAIL FORMAT ----------
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            error = "Invalid email address."

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
                (id, name, email, message)
            )
            db.commit()

            flash("Enquiry sent!", "success")
            return redirect(url_for('listings.detail', id=id))

    return render_template('listings/detail.html', listing=listing)
