# CertiLiving

A full-stack student accommodation compliance platform built solo in Flask.

**Live site:** [certiliving.co.uk](https://certiliving.co.uk)

---

## What it does

CertiLiving lets landlords list verified student accommodation and lets students browse, filter, and enquire directly. The admin panel is for CertiLiving staff to manage listings on behalf of landlords — creating, editing, uploading images, and removing listings as needed, without touching any code.

- Public listings directory with filters (city, room type, bills included, rent range) and sorting
- Listing detail pages with image carousel and enquiry form
- Admin dashboard for full listing CRUD with image upload to Cloudflare R2
- Enquiry notifications delivered by email via Resend API
- Bot and spam protection on public-facing forms

---

## Milestones

### [v1.0 – Initial release](https://github.com/joehindle/certiliving-website/releases/tag/v1.0) — March 2026

Shipped a working end-to-end platform in 11 days: public listings, detail pages, enquiry form, admin panel, single image upload to Cloudflare R2, email delivery via Resend, and deployment to Render with PostgreSQL. The goal was to get something real in front of landlords as quickly as possible.

### [v2.0 – Production hardening and multi-image support](https://github.com/joehindle/certiliving-website/releases/tag/v2.0) — April 2026

Seven weeks after the initial release, v2.0 adds the features that take a working app to a production-ready one.

- Multi-image support per listing with a JS carousel on the detail page
- Supporting photos stored in Cloudflare R2 with deduplication and cleanup on failure
- Cloudflare Turnstile bot protection and honeypot spam filtering on the enquiry form
- Full test suite covering admin, listings, DB, config, and smoke tests
- GitHub Actions CI/CD pipeline with automated deploy to Render on merge to main
- Dockerfile added for containerised deployment

---

## What I learned

**Integrating third-party APIs from scratch.** Cloudflare R2, Resend, and Cloudflare Turnstile were all new to me going into this project. Each one involved reading API documentation, handling edge cases (missing credentials, failed uploads, network timeouts), and making decisions about how tightly to couple them to the core app.

**Defensive backend design.** The v1 image upload logic was straightforward — upload one file, store the URL. By v2, with multiple images per listing, I had to think carefully about failure states: what happens if the second of three uploads errors? The answer was to track all successfully uploaded URLs and delete them on exception, so the database never ends up pointing at orphaned files in R2.

**Testing as a forcing function for better structure.** Writing the test suite for v2 surfaced a few places where the app factory and route logic were too tightly coupled to test cleanly. Fixing those made the codebase better independent of the tests themselves.

**Shipping over perfecting.** v1 had no tests, no CI, and no multi-image support. It also had real landlords using it within days of being built. Getting something working and in front of users early shaped v2 more usefully than any amount of upfront planning would have.

---

## Tech stack

- **Backend:** Python, Flask
- **Database:** PostgreSQL (`psycopg`)
- **Templates:** Jinja2 + custom CSS
- **Storage:** Cloudflare R2 via `boto3`
- **Email:** Resend
- **Rate limiting:** Flask-Limiter
- **CI/CD:** GitHub Actions → Render
- **Containerisation:** Docker

---

## Screenshots

### Home Page
<img src="docs/screenshots/home.png" width="650" alt="Homepage" />

### Listings Page
<img src="docs/screenshots/listings.png" width="650" alt="Listings" />

<details>
  <summary>More screenshots</summary>

  <p><strong>Listing Detail Page</strong></p>
  <img src="docs/screenshots/listing.png" width="650" alt="Listing detail" />

  <p><strong>Admin Dashboard</strong></p>
  <img src="docs/screenshots/admin.png" width="650" alt="Admin dashboard" />

  <p><strong>Create Listing (Admin)</strong></p>
  <img src="docs/screenshots/createlisting.png" width="650" alt="Create listing (Admin)" />

</details>
