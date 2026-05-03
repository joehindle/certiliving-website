import time
from functools import wraps
from urllib.parse import urlparse, urljoin

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

from ..extensions import limiter
from ..security import AUTH_RATE_LIMITS, verify_protected_form
from ..services.supabase_auth import (
    load_profile,
    sign_in_with_supabase,
    sign_up_with_supabase,
    supabase_auth_enabled,
    verify_confirmation_token,
)


bp = Blueprint("auth", __name__)


def _normalize_profile_roles(profile):
    if not profile:
        return []

    roles = []
    role = profile.get("role")
    if isinstance(role, str) and role.strip():
        roles.append(role.strip().lower())

    extra_roles = profile.get("roles") or []
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


def user_has_role(role):
    role = role.strip().lower()
    roles = session.get("auth_roles") or []
    return role in roles


def user_has_any_role(*roles):
    normalized = {
        role.strip().lower()
        for role in roles
        if isinstance(role, str) and role.strip()
    }
    current_roles = {
        role.strip().lower()
        for role in (session.get("auth_roles") or [])
        if isinstance(role, str) and role.strip()
    }
    return bool(normalized & current_roles)


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("auth_user_id") or not user_has_any_role(*roles):
                return redirect(url_for("auth.account", next=request.path))
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
    if user_has_role("landlord"):
        return url_for("landlord.listings_index")
    return url_for("listings.index")


def _current_auth_mode():
    mode = (request.form.get("mode") or request.args.get("mode") or "login").strip().lower()
    if mode not in {"login", "register"}:
        return "login"
    return mode


def _start_authenticated_session(user, profile):
    session.clear()
    session["auth_provider"] = "supabase"
    session["auth_user_id"] = user.get("id")
    session["auth_email"] = (profile.get("email") or user.get("email") or "").strip().lower()
    session["auth_display_name"] = (profile.get("display_name") or "").strip()
    session["auth_roles"] = _normalize_profile_roles(profile)
    session["auth_account_status"] = (
        profile.get("account_status") or "pending"
    ).strip().lower()


@bp.route("/account", methods=("GET", "POST"), endpoint="account")
@bp.route("/login", methods=("GET", "POST"), endpoint="login")
@limiter.limit(AUTH_RATE_LIMITS[0], methods=["POST"])
@limiter.limit(AUTH_RATE_LIMITS[1], methods=["POST"])
def account():
    mode = _current_auth_mode()
    email_verified = request.args.get("verified", "").strip() == "1"

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        display_name = (request.form.get("display_name") or "").strip()

        is_valid_submission, security_error = verify_protected_form(
            request.form,
            context=f"auth {mode}",
        )
        if not is_valid_submission:
            flash(security_error, "error")
        elif not supabase_auth_enabled():
            flash("Authentication is not configured yet.", "error")
        elif not email or not password:
            flash("Email and password are required.", "error")
        elif mode == "register" and password != confirm_password:
            flash("Passwords do not match.", "error")
        elif mode == "register" and len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif mode == "register" and not display_name:
            flash("Display name is required.", "error")
        elif mode == "register" and len(display_name) > 80:
            flash("Display name is too long.", "error")
        elif mode == "register":
            try:
                auth_result = sign_up_with_supabase(
                    email,
                    password,
                    email_redirect_to=request.host_url.rstrip("/"),
                    display_name=display_name,
                )
            except ValueError as exc:
                time.sleep(0.8)
                flash(str(exc), "error")
            except RuntimeError as exc:
                flash(str(exc), "error")
            else:
                if auth_result.get("existing_account"):
                    flash(
                        "An account with that email may already exist. Please log in instead.",
                        "info",
                    )
                    return redirect(url_for("auth.account", mode="login"))

                access_token = auth_result.get("access_token")
                user = auth_result.get("user") or {}
                if access_token and user.get("id"):
                    try:
                        profile = load_profile(access_token, user["id"])
                    except RuntimeError as exc:
                        flash(str(exc), "error")
                    else:
                        _start_authenticated_session(user, profile)
                        flash("Account created.", "success")
                        return redirect(_post_login_redirect())
                else:
                    flash(
                        "If this email is new, check your inbox to confirm it. "
                        "If you already have an account, please log in instead.",
                        "info",
                    )
                    return redirect(url_for("auth.account", mode="login"))
        else:
            try:
                auth_result = sign_in_with_supabase(email, password)
            except ValueError as exc:
                time.sleep(0.8)
                flash(str(exc), "error")
            except RuntimeError as exc:
                flash(str(exc), "error")
            else:
                user = auth_result["user"]
                try:
                    profile = load_profile(auth_result["access_token"], user["id"])
                except RuntimeError as exc:
                    flash(str(exc), "error")
                else:
                    _start_authenticated_session(user, profile)
                    return redirect(_post_login_redirect())

    return render_template(
        "auth/account.html",
        auth_mode=mode,
        email_verified=email_verified,
        next_url=request.args.get("next", ""),
        supabase_auth_enabled=supabase_auth_enabled(),
    )


@bp.route("/register", methods=("GET",))
def register():
    return redirect(url_for("auth.account", mode="register", next=request.args.get("next", "")))


@bp.route("/auth/confirm", methods=("GET",))
def confirm():
    token_hash = (request.args.get("token_hash") or "").strip()
    otp_type = (request.args.get("type") or "email").strip().lower()
    next_url = (request.args.get("next") or "").strip()

    if not token_hash:
        flash("Confirmation link is invalid or incomplete.", "error")
        return redirect(url_for("auth.account", mode="login"))

    try:
        verify_confirmation_token(token_hash, otp_type)
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("auth.account", mode="login"))

    if next_url and _is_safe_redirect_target(next_url):
        return redirect(next_url)
    return redirect(url_for("auth.account", mode="login", verified=1))


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("listings.index"))
