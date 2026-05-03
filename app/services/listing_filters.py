from urllib.parse import urlencode

from flask import url_for


DEFAULT_SORT = "newest"
DEFAULT_PER_PAGE = 9
ALLOWED_PER_PAGE = {4, 6, 9}


def _parse_optional_int(value):
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _parse_positive_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed >= 1 else default
    except ValueError:
        return default


def _build_filter_state(args):
    city = args.get("city", "").strip()
    room_type = args.get("room_type", "").strip()
    bills_only = args.get("bills_only", "").strip() == "1"
    min_rent_raw = args.get("min_rent", "").strip()
    max_rent_raw = args.get("max_rent", "").strip()
    sort = args.get("sort", DEFAULT_SORT).strip()
    page = _parse_positive_int(args.get("page", "1").strip(), 1)

    per_page_raw = args.get("per_page", "").strip()
    per_page = _parse_positive_int(per_page_raw, DEFAULT_PER_PAGE) if per_page_raw else DEFAULT_PER_PAGE
    if per_page not in ALLOWED_PER_PAGE:
        per_page = DEFAULT_PER_PAGE

    sort_map = {
        "newest": "created DESC",
        "price_asc": "rent_pcm ASC, created DESC",
        "price_desc": "rent_pcm DESC, created DESC",
    }
    if sort not in sort_map:
        sort = DEFAULT_SORT

    return {
        "city": city,
        "room_type": room_type,
        "bills_only": bills_only,
        "min_rent_raw": min_rent_raw,
        "max_rent_raw": max_rent_raw,
        "min_rent": _parse_optional_int(min_rent_raw),
        "max_rent": _parse_optional_int(max_rent_raw),
        "sort": sort,
        "order_by": sort_map[sort],
        "page": page,
        "per_page": per_page,
    }


def _build_where_clause(state):
    where_clauses = ["status = 'published'"]
    params = []
    if state["city"]:
        where_clauses.append("city = %s")
        params.append(state["city"])
    if state["room_type"]:
        where_clauses.append("room_type = %s")
        params.append(state["room_type"])
    if state["bills_only"]:
        where_clauses.append("bills_included = TRUE")
    if state["min_rent"] is not None:
        where_clauses.append("rent_pcm >= %s")
        params.append(state["min_rent"])
    if state["max_rent"] is not None:
        where_clauses.append("rent_pcm <= %s")
        params.append(state["max_rent"])

    where_sql = " WHERE " + " AND ".join(where_clauses)
    return where_sql, params


def _build_url_builder(base_params):
    def build_url(extra=None, drop=None):
        params_copy = dict(base_params)
        if drop:
            for key in drop:
                params_copy.pop(key, None)
        if extra:
            params_copy.update(extra)
        params_copy = {
            key: value for key, value in params_copy.items()
            if value not in ("", None)
        }
        querystring = urlencode(params_copy)
        if querystring:
            return f"{url_for('listings.all_listings')}?{querystring}"
        return url_for("listings.all_listings")

    return build_url


def _build_active_chips(state, build_url):
    chips = []
    if state["city"]:
        chips.append({
            "label": f"City: {state['city']}",
            "remove_url": build_url(drop=["city", "page"]),
        })
    if state["room_type"]:
        chips.append({
            "label": f"Room: {state['room_type']}",
            "remove_url": build_url(drop=["room_type", "page"]),
        })
    if state["bills_only"]:
        chips.append({
            "label": "Bills included",
            "remove_url": build_url(drop=["bills_only", "page"]),
        })
    if state["min_rent_raw"]:
        chips.append({
            "label": f"Min rent: {state['min_rent_raw']}",
            "remove_url": build_url(drop=["min_rent", "page"]),
        })
    if state["max_rent_raw"]:
        chips.append({
            "label": f"Max rent: {state['max_rent_raw']}",
            "remove_url": build_url(drop=["max_rent", "page"]),
        })
    if state["sort"] != DEFAULT_SORT:
        sort_label = "Price low to high" if state["sort"] == "price_asc" else "Price high to low"
        chips.append({
            "label": f"Sort: {sort_label}",
            "remove_url": build_url(extra={"sort": DEFAULT_SORT}, drop=["page"]),
        })
    return chips


def get_filtered_listings_context(db, args):
    state = _build_filter_state(args)
    where_sql, params = _build_where_clause(state)

    total = db.execute(
        "SELECT COUNT(*) AS total FROM listings" + where_sql,
        params,
    ).fetchone()["total"]

    total_pages = max(1, (total + state["per_page"] - 1) // state["per_page"])
    page = min(state["page"], total_pages)
    offset = (page - 1) * state["per_page"]

    query = f"SELECT * FROM listings{where_sql} ORDER BY {state['order_by']} LIMIT %s OFFSET %s"
    listings = db.execute(query, (*params, state["per_page"], offset)).fetchall()

    city_options = db.execute(
        "SELECT DISTINCT city FROM listings WHERE status = 'published' AND city IS NOT NULL AND city != '' ORDER BY city ASC"
    ).fetchall()
    room_type_options = db.execute(
        "SELECT DISTINCT room_type FROM listings WHERE status = 'published' AND room_type IS NOT NULL AND room_type != '' ORDER BY room_type ASC"
    ).fetchall()

    filters = {
        "city": state["city"],
        "room_type": state["room_type"],
        "bills_only": state["bills_only"],
        "min_rent": state["min_rent_raw"],
        "max_rent": state["max_rent_raw"],
        "sort": state["sort"],
        "per_page": str(state["per_page"]),
    }
    base_params = {
        "city": state["city"],
        "room_type": state["room_type"],
        "bills_only": "1" if state["bills_only"] else "",
        "min_rent": state["min_rent_raw"],
        "max_rent": state["max_rent_raw"],
        "sort": state["sort"],
        "per_page": str(state["per_page"]),
    }
    build_url = _build_url_builder(base_params)

    page_links = [
        {
            "page": page_number,
            "url": build_url(extra={"page": page_number}),
            "is_current": page_number == page,
        }
        for page_number in range(1, total_pages + 1)
    ]

    return {
        "listings": listings,
        "filters": filters,
        "city_options": city_options,
        "room_type_options": room_type_options,
        "active_chips": _build_active_chips(state, build_url),
        "pagination": {
            "page": page,
            "total_pages": total_pages,
            "total_results": total,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_url": build_url(extra={"page": page - 1}) if page > 1 else None,
            "next_url": build_url(extra={"page": page + 1}) if page < total_pages else None,
            "page_links": page_links,
        },
    }
