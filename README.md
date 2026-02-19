# CertiLiving Website

CertiLiving is a Flask web app for verified student accommodation listings.

## Features
- Featured and full listings pages
- Listing detail pages with similar listings
- Enquiry form with validation, CSRF protection, and email notifications
- Admin dashboard for managing listings
- Image uploads to Cloudflare R2

## Stack
- Python, Flask, SQLite
- Jinja templates, custom CSS
- Cloudflare R2 (image storage)
- Resend (email delivery)

## Run Locally
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set required env vars:
   - `SECRET_KEY`
   - `ADMIN_PASSWORD`
3. Start app:
   ```bash
   python run.py
   ```

## Environment Variables
- Core: `SECRET_KEY`, `ADMIN_PASSWORD`
- Email: `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `ENQUIRY_TO_EMAIL`
- Storage: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`

## Deployment (Render)
- Host provider: **Render**
- Set all required environment variables in Render dashboard
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn run:app`
