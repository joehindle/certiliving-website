import json
import time
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .extensions import limiter


bp = Blueprint("auth", __name__)


def _supabase_auth_enabled():
    return bool(
        (current_app.config.get("SUPABASE_URL") or "").strip()
        and (current_app.config.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
    )


def _normalize_auth_roles(user):
    app_metadata = user.get("app_metadata") or {}
    roles = []

    role = app_metadata.get("role")
    if isinstance(role, str) and role.strip():
        roles.append(role.strip().lower())

    extra_roles = app_metadata.get("roles") or []
    if isinstance(extra_roles, str):
        extra_roles = [extra_roles]

    for value in extra_roles:
        if isinstance(value, str) and value.strip():
            roles.append(value.strip().lower())

    deduped = []
    seen = set()
    for role_name in roles:
        if role_name not in seen:
            deduped.append(role_name)
            seen.add(role_name)
    return deduped


def _configured_admin_emails():
    raw_value = current_app.config.get("SUPABASE_ADMIN_EMAILS") or ""
    return {
        email.strip().lower()
        for email in raw_value.split(",")
        if email.strip()
    }


def user_has_role(role):
    role = role.strip().lower()
    roles = session.get("auth_roles") or []
    if role in roles:
        return True

    if role == "admin":
        email = (session.get("auth_email") or "").strip().lower()
        return email in _configured_admin_emails()

    return False


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("auth_user_id") or not user_has_role(role):
                return redirect(url_for("auth.login", next=request.path))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _is_safe_redirect_target(target):
    if not target:
        return False
    base_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in {"http", "https"} and base_url.netloc == test_url.netloc


def _post_login_redirect():
    next_url = request.form.get("next") or request.args.get("next")
    if next_url and _is_safe_redirect_target(next_url):
        return next_url
    if user_has_role("admin"):
        return url_for("admin.listings_index")
    return url_for("listings.index")


def _sign_in_with_supabase(email, password):
    supabase_url = (current_app.config.get("SUPABASE_URL") or "").strip().rstrip("/")
    publishable_key = (current_app.config.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    request_obj = Request(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": publishable_key,
        },
        method="POST",
    )

    try:
        with urlopen(request_obj, timeout=10) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {400, 401, 422}:
            raise ValueError("Invalid email or password.") from exc
        current_app.logger.exception("Supabase sign-in failed with status=%s", exc.code)
        raise RuntimeError("Login is unavailable right now.") from exc
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        current_app.logger.exception("Supabase sign-in request failed")
        raise RuntimeError("Login is unavailable right now.") from exc

    user = response_payload.get("user") or {}
    if not user:
        raise RuntimeError("Login did not return a user record.")
    return user


def _start_authenticated_session(user):
    session.clear()
    session["auth_provider"] = "supabase"
    session["auth_user_id"] = user.get("id")
    session["auth_email"] = (user.get("email") or "").strip().lower()
    session["auth_roles"] = _normalize_auth_roles(user)


@bp.route("/login", methods=("GET", "POST"))
@limiter.limit("5 per minute")
@limiter.limit("30 per hour")
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not _supabase_auth_enabled():
            flash("Login is not configured yet.", "error")
        elif not email or not password:
            flash("Email and password are required.", "error")
        else:
            try:
                user = _sign_in_with_supabase(email, password)
            except ValueError as exc:
                time.sleep(0.8)
                flash(str(exc), "error")
            except RuntimeError as exc:
                flash(str(exc), "error")
            else:
                _start_authenticated_session(user)
                return redirect(_post_login_redirect())

    return render_template(
        "auth/login.html",
        next_url=request.args.get("next", ""),
        supabase_auth_enabled=_supabase_auth_enabled(),
    )


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("listings.index"))
