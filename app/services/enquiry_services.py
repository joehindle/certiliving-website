import html
import re

import resend
from flask import current_app, url_for


MAX_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 1500


def validate_enquiry_form(name, email, message):
    if not name:
        return "Name is required."
    if not email:
        return "Email is required."
    if not message:
        return "Message is required."
    if len(name) > MAX_NAME_LENGTH:
        return "Name is too long."
    if len(message) > MAX_MESSAGE_LENGTH:
        return "Message is too long."
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return "Invalid email address."
    return None


def send_enquiry_email(listing, name, email, message):
    resend_api_key = current_app.config.get("RESEND_API_KEY")
    to_email = current_app.config.get("ENQUIRY_TO_EMAIL")
    from_email = current_app.config.get("RESEND_FROM_EMAIL")

    if not resend_api_key:
        raise RuntimeError("Missing RESEND_API_KEY")
    if not to_email:
        raise RuntimeError("Missing ENQUIRY_TO_EMAIL")
    if not from_email:
        raise RuntimeError("Missing RESEND_FROM_EMAIL")

    resend.api_key = resend_api_key

    safe_name = html.escape(name)
    safe_email = html.escape(email)
    safe_message = html.escape(message).replace("\n", "<br>")
    safe_title = html.escape(listing["title"])
    safe_city = html.escape(listing["city"])
    listing_url = url_for("listings.detail", listing_id=listing["id"], _external=True)

    resend.Emails.send({
        "from": from_email,
        "to": to_email,
        "subject": f"New enquiry for {listing['title']} ({listing['city']})",
        "html": (
            "<h2>New CertiLiving enquiry</h2>"
            f"<p><strong>Listing:</strong> {safe_title} ({safe_city})</p>"
            f"<p><strong>From:</strong> {safe_name} ({safe_email})</p>"
            f"<p><strong>Message:</strong><br>{safe_message}</p>"
            f"<p><a href=\"{listing_url}\">View listing</a></p>"
        ),
    })
