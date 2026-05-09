# CertiLiving – Student Housing Platform

**Role:** Full Stack Developer (Personal Project)
**Tech Stack:** Python, Flask, PostgreSQL, Supabase (Auth), Cloudflare R2 (S3 Storage), Cloudflare Turnstile, Pytest, HTML/CSS/JS.

## Key Features & Achievements for CV

**Role-Based Access Control & Secure Authentication**
- Integrated **Supabase Authentication** to handle secure user registration, login, and session management.
- Architected a robust multi-role system (`Student`, `Landlord`, `Admin`) with strict server-side routing protection (`@role_required` decorators) and distinct dashboard interfaces for each persona.
- Implemented a secure onboarding pipeline where Landlord accounts default to a `pending` state, restricting them to submitting a single "pending review" property until an Admin manually verifies and approves the account.

**Complex Relational Data & Automated Workflows**
- Designed and managed a relational **PostgreSQL** database schema (using `psycopg`) featuring complex table joins between `listings`, user `profiles`, and `enquiries`.
- Developed an automated state-machine workflow: Upon an Admin changing a landlord's account status to `approved`, the system automatically executes a bulk SQL update to instantly publish any of their existing `pending_review` listings.
- Built a dynamic backend filtering system allowing Admins to query and filter properties by specific owners via custom SQL dropdowns.

**Cloud Object Storage Integration**
- Built an end-to-end image upload pipeline integrating with **Cloudflare R2** (S3-compatible API).
- Handled secure multipart-form data parsing to process, upload, and serve property cover images and galleries, alongside functionality to permanently delete orphaned images from the bucket when a listing is removed.

**Security & Anti-Abuse Mechanisms**
- Integrated **Flask-Limiter** to enforce strict rate-limiting on sensitive endpoints (login, registration, listing creation) to mitigate brute-force and spam attacks.
- Deployed **Cloudflare Turnstile** CAPTCHA on public forms to block automated bot submissions.
- Strictly enforced parameterized SQL queries to prevent SQL Injection and utilized Jinja2 auto-escaping to mitigate XSS vulnerabilities.

**Robust Automated Testing**
- Engineered a comprehensive testing suite using **Pytest** with high code coverage (`pytest-cov`).
- Leveraged mocking and dependency injection (via `MonkeyPatch` and `FakeDB` classes) to effectively isolate unit tests, ensuring that core business logic, routing constraints, and form validations are continuously verified in CI/CD pipelines without relying on a live database.
