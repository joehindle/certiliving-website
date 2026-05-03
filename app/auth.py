import json
import time
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse, urljoin
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

    if not response_payload.get("access_token"):
        raise RuntimeError("Login did not return an access token.")

    user = response_payload.get("user") or {}
    if not user or not user.get("id"):
        raise RuntimeError("Login did not return a user record.")
    return response_payload


def _sign_up_with_supabase(email, password):
    supabase_url = (current_app.config.get("SUPABASE_URL") or "").strip().rstrip("/")
    publishable_key = (current_app.config.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    request_obj = Request(
        f"{supabase_url}/auth/v1/signup",
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
            try:
                error_payload = json.loads(exc.read().decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                error_payload = {}
            message = (
                error_payload.get("msg")
                or error_payload.get("message")
                or "Could not create account."
            )
            raise ValueError(message) from exc
        current_app.logger.exception("Supabase sign-up failed with status=%s", exc.code)
        raise RuntimeError("Registration is unavailable right now.") from exc
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        current_app.logger.exception("Supabase sign-up request failed")
        raise RuntimeError("Registration is unavailable right now.") from exc

    user = response_payload.get("user") or {}
    if not user or not user.get("id"):
        raise RuntimeError("Registration did not return a user record.")
    return response_payload


def _load_profile(access_token, user_id):
    supabase_url = (current_app.config.get("SUPABASE_URL") or "").strip().rstrip("/")
    publishable_key = (current_app.config.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
    request_obj = Request(
        (
            f"{supabase_url}/rest/v1/profiles"
            f"?select=id,email,role&"
            f"id=eq.{quote(user_id)}"
        ),
        headers={
            "apikey": publishable_key,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(request_obj, timeout=10) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        current_app.logger.exception(
            "Supabase profile lookup failed with status=%s for user_id=%s",
            exc.code,
            user_id,
        )
        raise RuntimeError("Account profile could not be loaded.") from exc
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        current_app.logger.exception(
            "Supabase profile lookup request failed for user_id=%s",
            user_id,
        )
        raise RuntimeError("Account profile could not be loaded.") from exc

    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Account profile was not found.")
    return rows[0]


def _verify_auth_turnstile():
    from .listings import _verify_turnstile_token

    turnstile_token = request.form.get("cf-turnstile-response", "").strip()
    remoteip = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote_addr
    )
    return _verify_turnstile_token(turnstile_token, remoteip)


def _is_spam_auth_submission(form):
    return bool((form.get("website") or "").strip())


def _start_authenticated_session(user, profile):
    session.clear()
    session["auth_provider"] = "supabase"
    session["auth_user_id"] = user.get("id")
    session["auth_email"] = (profile.get("email") or user.get("email") or "").strip().lower()
    session["auth_roles"] = _normalize_profile_roles(profile)


@bp.route("/account", methods=("GET", "POST"), endpoint="account")
@bp.route("/login", methods=("GET", "POST"), endpoint="login")
@limiter.limit("5 per minute")
@limiter.limit("30 per hour")
def account():
    mode = _current_auth_mode()
    email_verified = request.args.get("verified", "").strip() == "1"

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if _is_spam_auth_submission(request.form):
            current_app.logger.warning(
                "Blocked spam auth submission for email=%s mode=%s",
                email,
                mode,
            )
            flash("Please try again.", "error")
        elif not _supabase_auth_enabled():
            flash("Authentication is not configured yet.", "error")
        elif not email or not password:
            flash("Email and password are required.", "error")
        elif mode == "register" and password != confirm_password:
            flash("Passwords do not match.", "error")
        elif mode == "register" and len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            is_human, turnstile_errors = _verify_auth_turnstile()
            if not is_human:
                current_app.logger.warning(
                    "Blocked invalid auth security check for email=%s mode=%s errors=%s",
                    email,
                    mode,
                    turnstile_errors,
                )
                flash("Please complete the security check and try again.", "error")
            else:
                if mode == "register":
                    try:
                        auth_result = _sign_up_with_supabase(email, password)
                    except ValueError as exc:
                        time.sleep(0.8)
                        flash(str(exc), "error")
                    except RuntimeError as exc:
                        flash(str(exc), "error")
                    else:
                        access_token = auth_result.get("access_token")
                        user = auth_result.get("user") or {}
                        if access_token and user.get("id"):
                            try:
                                profile = _load_profile(access_token, user["id"])
                            except RuntimeError as exc:
                                flash(str(exc), "error")
                            else:
                                _start_authenticated_session(user, profile)
                                flash("Account created.", "success")
                                return redirect(_post_login_redirect())
                        else:
                            flash("Account created. Check your email to confirm your address, then log in.", "success")
                            return redirect(url_for("auth.account", mode="login"))
                else:
                    try:
                        auth_result = _sign_in_with_supabase(email, password)
                    except ValueError as exc:
                        time.sleep(0.8)
                        flash(str(exc), "error")
                    except RuntimeError as exc:
                        flash(str(exc), "error")
                    else:
                        user = auth_result["user"]
                        try:
                            profile = _load_profile(auth_result["access_token"], user["id"])
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
        supabase_auth_enabled=_supabase_auth_enabled(),
    )


@bp.route("/register", methods=("GET",))
def register():
    return redirect(url_for("auth.account", mode="register", next=request.args.get("next", "")))


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    return redirect(url_for("listings.index"))
