from flask import Blueprint, redirect, session, url_for

from ..auth import role_required


bp = Blueprint("admin", __name__, url_prefix="/admin")

admin_required = role_required("admin")


def admin_tabs(active):
    tabs = [
        ("listings", "Listing management", "admin.listings_index"),
        ("users", "User management", "admin.users_index"),
        ("enquiries", "Enquiries", "admin.enquiries_index"),
    ]
    return [
        {
            "label": label,
            "url": url_for(endpoint),
            "active": key == active,
        }
        for key, label, endpoint in tabs
    ]


@bp.route("/login", methods=("GET", "POST"))
def login():
    return redirect(url_for("auth.account", next=url_for("admin.listings_index")))


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("listings.index"))


@bp.route("/")
@admin_required
def home():
    return redirect(url_for("admin.listings_index"))


from . import enquiries, listings, users  # noqa: E402

listings.register_routes(bp, admin_required, admin_tabs)
users.register_routes(bp, admin_required, admin_tabs)
enquiries.register_routes(bp, admin_required, admin_tabs)
