SIMILAR_LISTINGS_LIMIT = 6


def get_highlighted_listings(db, limit=SIMILAR_LISTINGS_LIMIT):
    return db.execute(
        "SELECT * FROM listings WHERE status = 'published' ORDER BY created DESC LIMIT %s",
        (limit,),
    ).fetchall()


def get_similar_listings(db, listing, limit=SIMILAR_LISTINGS_LIMIT):
    similar_listings = db.execute(
        """
        SELECT *
        FROM listings
        WHERE id != %s AND city = %s AND status = 'published'
        ORDER BY ABS(rent_pcm - %s) ASC, created DESC
        LIMIT %s
        """,
        (listing["id"], listing["city"], listing["rent_pcm"], limit),
    ).fetchall()

    if len(similar_listings) >= limit:
        return similar_listings

    needed = limit - len(similar_listings)
    exclude_ids = [row["id"] for row in similar_listings]
    exclude_ids.append(listing["id"])
    placeholders = ",".join("%s" for _ in exclude_ids)
    fallback_listings = db.execute(
        f"""
        SELECT *
        FROM listings
        WHERE id NOT IN ({placeholders}) AND status = 'published'
        ORDER BY created DESC
        LIMIT %s
        """,
        (*exclude_ids, needed),
    ).fetchall()
    return list(similar_listings) + list(fallback_listings)
