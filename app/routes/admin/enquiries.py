from flask import flash, redirect, render_template, url_for

from ...db import get_db


def register_routes(bp, admin_required, admin_tabs):
    @bp.route("/enquiries")
    @admin_required
    def enquiries_index():
        db = get_db()
        enquiries = db.execute(
            """SELECT e.*, l.title AS listing_title, l.city AS listing_city
               FROM enquiries e
               LEFT JOIN listings l ON e.listing_id = l.id
               ORDER BY e.created DESC"""
        ).fetchall()
        return render_template(
            "admin/enquiries_index.html",
            enquiries=enquiries,
            admin_tabs=admin_tabs("enquiries"),
        )

    @bp.route("/enquiries/<int:enquiry_id>/delete", methods=("POST",))
    @admin_required
    def enquiries_delete(enquiry_id):
        db = get_db()
        db.execute("DELETE FROM enquiries WHERE id = %s", (enquiry_id,))
        db.commit()
        flash("Enquiry deleted.", "success")
        return redirect(url_for("admin.enquiries_index"))
