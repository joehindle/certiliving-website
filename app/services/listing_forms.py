def clean_optional(value):
    text = (value or "").strip()
    return text or None


def parse_listing_form(form):
    return {
        "title": form["title"].strip(),
        "city": form["city"].strip(),
        "rent_pcm": form["rent_pcm"],
        "room_type": clean_optional(form.get("room_type")),
        "bills_included": form.get("bills_included") == "on",
        "available_from": clean_optional(form.get("available_from")),
        "description": (form.get("description") or "").strip(),
    }


def normalize_supporting_photo_urls(photo_urls):
    if not photo_urls:
        return []
    if isinstance(photo_urls, str):
        return [photo_urls]
    return [photo_url for photo_url in photo_urls if photo_url]


def listing_preview_from_form(
    form,
    existing_photo_url=None,
    existing_supporting_photo_urls=None,
):
    return {
        "title": (form.get("title") or "").strip(),
        "city": (form.get("city") or "").strip(),
        "rent_pcm": (form.get("rent_pcm") or "").strip(),
        "photo_url": existing_photo_url,
        "supporting_photo_urls": normalize_supporting_photo_urls(
            existing_supporting_photo_urls
        ),
        "room_type": clean_optional(form.get("room_type")),
        "bills_included": form.get("bills_included") == "on",
        "available_from": clean_optional(form.get("available_from")),
        "description": (form.get("description") or "").strip(),
    }
