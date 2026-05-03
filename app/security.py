import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app, request


AUTH_RATE_LIMITS = ("5 per minute", "30 per hour")
ENQUIRY_RATE_LIMITS = ("5 per minute", "30 per hour")
LISTING_WRITE_RATE_LIMITS = ("3 per minute", "20 per hour")
HONEYPOT_FIELD_NAME = "website"


def is_honeypot_filled(form, field_name=HONEYPOT_FIELD_NAME):
    # Real users never see this hidden field. Bots often fill every input.
    return bool((form.get(field_name) or "").strip())


def request_remote_ip():
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote_addr
    )


def verify_turnstile_token(token, remoteip=None):
    secret_key = current_app.config.get("TURNSTILE_SECRET_KEY")
    site_key = current_app.config.get("TURNSTILE_SITE_KEY")
    if not secret_key or not site_key:
        return True, []

    if not token:
        return False, ["missing-input-response"]

    payload = {
        "secret": secret_key,
        "response": token,
    }
    if remoteip:
        payload["remoteip"] = remoteip

    request_data = urlencode(payload).encode("utf-8")
    request_obj = Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=request_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request_obj, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        current_app.logger.exception("Turnstile validation failed")
        return False, ["internal-error"]

    return bool(result.get("success")), result.get("error-codes", [])


def verify_protected_form(form, context="form"):
    if is_honeypot_filled(form):
        current_app.logger.warning("Blocked spam %s submission", context)
        return False, "Please try again."

    turnstile_token = form.get("cf-turnstile-response", "").strip()
    is_human, turnstile_errors = verify_turnstile_token(
        turnstile_token,
        request_remote_ip(),
    )
    if not is_human:
        current_app.logger.warning(
            "Blocked invalid %s Turnstile submission errors=%s",
            context,
            turnstile_errors,
        )
        return False, "Please complete the security check and try again."
    return True, None
