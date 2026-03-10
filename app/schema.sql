-- LISTINGS (Properties / Rooms)
CREATE TABLE IF NOT EXISTS listings (
    id BIGSERIAL PRIMARY KEY,

    title TEXT NOT NULL,
    description TEXT NOT NULL,

    city TEXT NOT NULL,
    address TEXT,

    rent_pcm INTEGER NOT NULL,
    deposit INTEGER,

    room_type TEXT,
    bills_included BOOLEAN DEFAULT FALSE,

    available_from DATE,

    photo_url TEXT,

    created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


-- ENQUIRIES (Student interest)
CREATE TABLE IF NOT EXISTS enquiries (
    id BIGSERIAL PRIMARY KEY,

    listing_id BIGINT NOT NULL,
    student_name TEXT NOT NULL,
    student_email TEXT NOT NULL,
    message TEXT NOT NULL,

    created TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
);
