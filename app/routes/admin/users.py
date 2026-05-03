from flask import flash, redirect, render_template, request, url_for

from ...db import get_db


def register_routes(bp, admin_required, admin_tabs):
    @bp.route("/users")
    @admin_required
    def users_index():
        db = get_db()
        users = db.execute(
            """SELECT id, email, role, display_name, account_status, created_at
               FROM profiles
               ORDER BY created_at DESC"""
        ).fetchall()
        return render_template(
            "admin/users_index.html",
            users=users,
            admin_tabs=admin_tabs("users"),
        )

    @bp.route("/users/<user_id>/status", methods=("POST",))
    @admin_required
    def users_update_status(user_id):
        account_status = (request.form.get("account_status") or "").strip().lower()
        if account_status not in {"pending", "approved", "rejected"}:
            flash("Choose a valid account status.", "error")
            return redirect(url_for("admin.users_index"))

        db = get_db()
        db.execute(
            "UPDATE profiles SET account_status = %s WHERE id = %s",
            (account_status, user_id),
        )
        db.commit()
        flash("Account status updated.", "success")
        return redirect(url_for("admin.users_index"))

    @bp.route("/users/<user_id>/role", methods=("POST",))
    @admin_required
    def users_update_role(user_id):
        role = (request.form.get("role") or "").strip().lower()
        if role not in {"admin", "landlord"}:
            flash("Choose a valid role.", "error")
            return redirect(url_for("admin.users_index"))

        db = get_db()
        db.execute(
            "UPDATE profiles SET role = %s WHERE id = %s",
            (role, user_id),
        )
        db.commit()
        flash("User role updated.", "success")
        return redirect(url_for("admin.users_index"))
