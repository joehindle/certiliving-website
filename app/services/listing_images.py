from pathlib import Path
import mimetypes
import uuid

import boto3
from botocore.client import Config
from flask import current_app
from werkzeug.utils import secure_filename

from .listing_forms import normalize_supporting_photo_urls


def dedupe_photo_urls(photo_urls):
    deduped = []
    seen = set()
    for photo_url in photo_urls or []:
        if photo_url and photo_url not in seen:
            deduped.append(photo_url)
            seen.add(photo_url)
    return deduped


def build_r2_client():
    account_id = current_app.config.get("R2_ACCOUNT_ID")
    access_key = current_app.config.get("R2_ACCESS_KEY_ID")
    secret_key = current_app.config.get("R2_SECRET_ACCESS_KEY")
    if not account_id or not access_key or not secret_key:
        raise RuntimeError("R2 credentials are missing.")

    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_listing_image(photo_file):
    filename = secure_filename(photo_file.filename or "")
    if not filename:
        return None

    ext = Path(filename).suffix.lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    if ext not in allowed_exts:
        raise ValueError("Please upload a JPG, PNG, WEBP, or GIF image.")

    content_type = (
        photo_file.mimetype
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )
    if not content_type.startswith("image/"):
        raise ValueError("Invalid file type. Please upload an image.")

    key = f"listings/{uuid.uuid4().hex}{ext}"
    bucket = current_app.config.get("R2_BUCKET")
    base_url = (current_app.config.get("R2_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    missing = []
    if not bucket:
        missing.append("R2_BUCKET")
    if not base_url:
        missing.append("R2_PUBLIC_BASE_URL")
    if missing:
        raise RuntimeError("Missing R2 config: " + ", ".join(missing))

    client = build_r2_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=photo_file.stream,
        ContentType=content_type,
    )
    return f"{base_url}/{key}"


def delete_r2_image(photo_url):
    if not photo_url:
        return

    try:
        base_url = (current_app.config.get("R2_PUBLIC_BASE_URL") or "").strip().rstrip("/")
        if not base_url:
            return
        if not photo_url.startswith(base_url + "/"):
            return

        key = photo_url[len(base_url) + 1:]
        if not key:
            return

        bucket = current_app.config.get("R2_BUCKET")
        if not bucket:
            return

        client = build_r2_client()
        client.delete_object(Bucket=bucket, Key=key)
    except Exception:
        current_app.logger.exception("Failed to delete R2 image: %s", photo_url)


def delete_r2_images(photo_urls):
    for photo_url in photo_urls or []:
        delete_r2_image(photo_url)


def upload_listing_images(photo_files):
    uploaded_urls = []
    for photo_file in photo_files or []:
        if photo_file and photo_file.filename:
            uploaded_urls.append(upload_listing_image(photo_file))
    return uploaded_urls


def process_listing_images(
    cover_photo_file=None,
    supporting_photo_files=None,
    existing_cover_photo_url=None,
    existing_supporting_photo_urls=None,
    replace_supporting=False,
):
    uploaded_urls = []
    cover_photo_url = existing_cover_photo_url
    supporting_photo_urls = normalize_supporting_photo_urls(
        existing_supporting_photo_urls
    )

    try:
        if cover_photo_file and cover_photo_file.filename:
            cover_photo_url = upload_listing_image(cover_photo_file)
            uploaded_urls.append(cover_photo_url)
        elif not cover_photo_url:
            raise ValueError("Cover photo is required.")

        new_supporting_photo_urls = upload_listing_images(supporting_photo_files)
        uploaded_urls.extend(new_supporting_photo_urls)
        if replace_supporting and new_supporting_photo_urls:
            supporting_photo_urls = new_supporting_photo_urls
        else:
            supporting_photo_urls.extend(new_supporting_photo_urls)
        return cover_photo_url, dedupe_photo_urls(supporting_photo_urls)
    except Exception:
        delete_r2_images(uploaded_urls)
        raise
