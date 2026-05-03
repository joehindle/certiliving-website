import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import current_app


def supabase_auth_enabled():
    return bool(
        (current_app.config.get("SUPABASE_URL") or "").strip()
        and (current_app.config.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
    )


def _supabase_auth_config():
    return (
        (current_app.config.get("SUPABASE_URL") or "").strip().rstrip("/"),
        (current_app.config.get("SUPABASE_PUBLISHABLE_KEY") or "").strip(),
    )


def sign_in_with_supabase(email, password):
    supabase_url, publishable_key = _supabase_auth_config()
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


def sign_up_with_supabase(email, password, email_redirect_to, display_name=None):
    supabase_url, publishable_key = _supabase_auth_config()
    payload = json.dumps(
        {
            "email": email,
            "password": password,
            "data": {
                "display_name": display_name,
            },
        }
    ).encode("utf-8")
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

    if not isinstance(response_payload, dict) or not response_payload:
        raise RuntimeError("Registration did not return a valid response.")
    response_payload["existing_account"] = _looks_like_existing_signup(response_payload)
    return response_payload


def _looks_like_existing_signup(response_payload):
    user = response_payload.get("user") or {}
    identities = user.get("identities")
    if isinstance(identities, list) and not identities:
        return True

    message = (
        response_payload.get("msg")
        or response_payload.get("message")
        or response_payload.get("error_description")
        or ""
    )
    return "already" in message.lower() and "user" in message.lower()


def load_profile(access_token, user_id):
    supabase_url, publishable_key = _supabase_auth_config()
    request_obj = Request(
        (
            f"{supabase_url}/rest/v1/profiles"
            f"?select=id,email,role,display_name,account_status&"
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


def verify_confirmation_token(token_hash, otp_type):
    supabase_url, publishable_key = _supabase_auth_config()
    payload = json.dumps(
        {
            "token_hash": token_hash,
            "type": otp_type,
        }
    ).encode("utf-8")
    request_obj = Request(
        f"{supabase_url}/auth/v1/verify",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": publishable_key,
        },
        method="POST",
    )

    try:
        with urlopen(request_obj, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        current_app.logger.exception(
            "Supabase confirmation verify failed with status=%s type=%s",
            exc.code,
            otp_type,
        )
        raise RuntimeError("Confirmation link is invalid or expired.") from exc
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        current_app.logger.exception(
            "Supabase confirmation verify request failed for type=%s",
            otp_type,
        )
        raise RuntimeError("Confirmation could not be completed right now.") from exc
