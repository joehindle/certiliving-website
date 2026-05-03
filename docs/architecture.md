# CertiLiving Architecture

This project uses a small Flask app structure that separates HTTP routing,
business logic, templates, and infrastructure concerns.

## App Layout

- `app/__init__.py` creates the Flask app, loads configuration, registers
  extensions, adds request hooks, and registers blueprints.
- `app/routes/` contains Flask blueprints and route handlers. Route files should
  stay focused on HTTP concerns: reading request data, calling services, and
  returning redirects or rendered templates.
- `app/services/` contains reusable application logic that can be shared across
  routes. Services should avoid knowing about specific pages where possible.
- `app/templates/` contains Jinja templates for public pages, auth pages, and
  dashboard/admin pages.
- `app/static/` contains CSS, JavaScript, and image assets.
- `app/security.py` centralises reusable form protection helpers such as
  honeypot checks, Turnstile verification, and rate-limit constants.
- `app/db.py` owns database connection setup and teardown.

## Route Packages

- `app/routes/listings.py` handles public listing pages.
- `app/routes/auth.py` handles account login, registration, logout, and auth
  session state.
- `app/routes/landlord.py` handles landlord dashboard listing management.
- `app/routes/admin/` handles admin dashboard features:
  - `__init__.py` creates the admin blueprint and registers admin sections.
  - `listings.py` manages listing CRUD.
  - `users.py` manages profile roles and account approval status.
  - `enquiries.py` manages student enquiries.

## Services

- `listing_forms.py` parses listing form input and builds safe preview objects.
- `listing_images.py` handles image validation, Cloudflare R2 uploads, cleanup,
  and deletion.
- `listing_filters.py` builds public listing filter/search/pagination context.
- `listing_queries.py` contains reusable listing query helpers for highlighted
  and similar listings.
- `enquiry_services.py` sends enquiry email through Resend.
- `supabase_auth.py` wraps Supabase Auth calls and profile lookups.

## Auth And Roles

Supabase Auth owns email/password authentication and email verification.
Application roles and account approval status are stored in the `profiles`
table. The Flask session stores the current user's ID, email, roles, and account
status after login.

Admins can access `/admin`. Landlords can access `/dashboard`, but pending
landlord accounts cannot create or manage listings until an admin approves them.

## Form Protection

Forms use shared protections where appropriate:

- CSRF token checked by the Flask `before_request` hook.
- Honeypot fields to catch basic bot submissions.
- Cloudflare Turnstile verification when Turnstile keys are configured.
- Flask-Limiter rate limits on auth, enquiries, and listing writes.

## Deployment

The app is deployed as a Docker-backed Flask/Gunicorn service. Environment
variables provide database, Supabase, Resend, Turnstile, and R2 configuration.
