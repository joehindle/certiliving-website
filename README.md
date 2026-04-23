# CertiLiving Website

CertiLiving is a Flask web application for publishing and managing verified student accommodation listings.

- Public users can browse listings, apply filters, and send enquiries.
- Admin users can log in and create, edit, and delete listings.
- Listing enquiries are saved to PostgreSQL and can trigger email notifications.
- Listing images are uploaded to Cloudflare R2.

Live site: `https://certiliving.co.uk`

## What This Project Is For

This project is built to support a simple marketplace-style workflow for student housing:

1. Admin adds listings from the `/admin` dashboard.
2. Students browse listings from the public pages.
3. Students send enquiries from a listing detail page.
4. Team receives enquiry notifications by email (via Resend).

## Core Features

- Home page with highlighted recent listings
- Listings directory with:
  - city and room-type filters
  - bills-included toggle
  - min/max rent filters
  - sorting (newest, price ascending, price descending)
  - pagination
- Listing detail page with "similar listings"
- Enquiry form with server-side validation and CSRF protection
- Rate-limited admin login (`/admin/login`)
- Admin CRUD for listings, including image upload/delete to Cloudflare R2

## Tech Stack

- Backend: Python, Flask
- Database: PostgreSQL (`psycopg`)
- Templates/UI: Jinja2 + custom CSS
- Email: Resend
- File storage: Cloudflare R2 (S3-compatible via `boto3`)
- Rate limiting: Flask-Limiter

## Project Structure

```text
app/
  __init__.py        # App factory, config loading, CSRF checks, blueprint wiring
  db.py              # DB connection + CLI commands (init-db, reset-db)
  schema.sql         # Postgres schema for listings and enquiries
  listings.py        # Public routes and enquiry handling
  admin.py           # Admin auth and listing management
  templates/         # Public and admin HTML templates
  static/css/        # Stylesheets
run.py               # Local development entrypoint
```

## Local Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root (or set variables in your shell):

```dotenv
# Required
SECRET_KEY=replace-with-a-random-secret
ADMIN_PASSWORD=replace-with-admin-password
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME

# Optional but needed for full functionality
RESEND_API_KEY=
RESEND_FROM_EMAIL=onboarding@resend.dev
ENQUIRY_TO_EMAIL=team@certiliving.co.uk

R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
R2_PUBLIC_BASE_URL=
```

Notes:
- `SECRET_KEY`, `ADMIN_PASSWORD`, and `DATABASE_URL` are required at startup.
- If Resend variables are missing, enquiry emails fail (the enquiry is still saved in DB).
- If R2 variables are missing, listing image upload fails in admin.

### 3. Initialize database schema

```bash
flask --app run.py init-db
```

This is non-destructive and creates tables if they do not already exist.

### 4. Run the app

```bash
python run.py
```

The site will be available at `http://127.0.0.1:5000`.

## Database CLI Commands

- `flask --app run.py init-db`
  - Creates tables from `app/schema.sql` if missing.
- `flask --app run.py reset-db --yes`
  - Destructive reset: drops existing data, asks for confirmation, then re-initializes tables.

## Data Model (High Level)

- `listings`: core listing content (title, city, rent, room type, availability, photo URL, created timestamp)
- `enquiries`: student enquiries linked to a listing (`ON DELETE CASCADE`)

## Security and Validation

- CSRF token validation for state-changing requests
- Admin session-based auth gate for `/admin/*`
- Rate limiting on admin login route
- Basic enquiry form validation (required fields, email format, length limits)

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

## Deployment Notes

- Use a production WSGI server such as `gunicorn`.
- Set all required environment variables in your hosting provider.
- Ensure your Postgres, Resend, and R2 credentials are configured for the deployment environment.

## Docker

This project includes a Docker image definition in [`Dockerfile`](/Users/hindl/certiliving-website/Dockerfile).

Build it locally:

```bash
docker build -t certiliving .
```

The container starts `gunicorn` and binds to the `PORT` environment variable if it is set, or `10000` by default.

For local container runs, use a local development database and dev-only environment values. Do not point the container at production credentials.

## GitHub Actions + Render

This repository includes a GitHub Actions workflow at [`.github/workflows/ci-cd.yml`](/Users/hindl/certiliving-website/.github/workflows/ci-cd.yml).

- On pull requests, it installs dependencies, compiles the Python files, runs a Flask smoke check, and executes `pytest` with coverage reporting.
- On pushes to `main`, it runs the same checks and then triggers a Render deploy hook.

To finish the setup:

1. Create your Render web service if it does not already exist.
2. If you deploy it as a Render Docker service, Render will use the `Dockerfile` and its `CMD` automatically. If you deploy it as a native Python service, set the start command to `gunicorn run:app`.
3. Add a GitHub secret named `RENDER_DEPLOY_HOOK_URL` with the deploy hook URL from Render.

Render should also have the app environment variables set, especially `SECRET_KEY`, `ADMIN_PASSWORD`, and `DATABASE_URL`.
