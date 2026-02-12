DROP TABLE IF EXISTS enquiries;
DROP TABLE IF EXISTS listings;


-- LISTINGS (Properties / Rooms)
CREATE TABLE listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,
    description TEXT NOT NULL,

    city TEXT NOT NULL,
    address TEXT,

    rent_pcm INTEGER NOT NULL,
    deposit INTEGER,

    room_type TEXT,
    bills_included BOOLEAN DEFAULT 0,

    available_from DATE,

    photo_url TEXT,

    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ENQUIRIES (Student interest)
CREATE TABLE enquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    listing_id INTEGER NOT NULL,
    student_name TEXT NOT NULL,
    student_email TEXT NOT NULL,
    message TEXT,

    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
);
