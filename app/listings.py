from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)

from werkzeug.exceptions import abort

from .db import get_db

bp = Blueprint('listings',__name__, url_prefix='/listings')

@bp.route('/')
def index():
    db = get_db()
    listings = db.execute(
        "SELECT * FROM listings ORDER BY created DESC"
    ).fetchall()

    return render_template('listings/index.html', listings=listings)

@bp.route('/<int:id>', methods=('GET', 'POST'))
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
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']

        db.execute(
            """INSERT INTO enquiries 
            (listing_id, student_name, student_email, message)
            VALUES (?, ?, ?, ?)""",
            (id, name, email, message)
        )
        db.commit()

        flash("Enquiry sent!")
        return redirect(url_for('listings.detail', id=id))

    return render_template('listings/detail.html', listing=listing)
