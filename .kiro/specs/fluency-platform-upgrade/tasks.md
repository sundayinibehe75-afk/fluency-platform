# Implementation Plan: Fluency Platform Upgrade

## Overview

Upgrade the static React marketing site into a full-featured single-tutor language learning platform. Tasks are ordered so each phase builds on the previous: infrastructure and project scaffolding first, then backend core (auth, DB, config), then each feature domain, then frontend enhancements, then integration wiring, and finally end-to-end validation.

**Stack:** React (Vite) · FastAPI · PostgreSQL · Alembic · Docker Compose · Nginx · Stripe · Daily.co · Resend · JWT · bcrypt · Hypothesis (PBT)

---

## Tasks

- [x] 1. Project scaffolding and Docker Compose infrastructure
  - Create `docker-compose.yml` at the workspace root defining four services: `db` (postgres:16-alpine, named volume `pgdata`), `api` (build `./backend`), `frontend` (build `./fluency-tutoring`), and `proxy` (nginx:alpine)
  - Create `.env.example` listing all required environment variables: `DATABASE_URL`, `JWT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `RESEND_API_KEY`, `DAILY_API_KEY`, `FRONTEND_URL`, `ENVIRONMENT`
  - Create `proxy/nginx.conf` that routes `/api/*` → `api:8000`, `/*` → `frontend:80`, and redirects HTTP → HTTPS with 301
  - Update `fluency-tutoring/nginx.conf` to proxy `/api` requests upstream (for local dev) and serve the SPA with `try_files $uri /index.html`
  - _Requirements: 11.8, 13.2_

- [x] 2. Backend project structure and core configuration
  - Create `backend/Dockerfile` using Python 3.12-slim, installing dependencies from `requirements.txt` and running `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - Create `backend/requirements.txt` pinning: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `stripe`, `resend`, `httpx`, `hypothesis`, `pytest`, `pytest-asyncio`
  - Create `backend/app/core/config.py` using `pydantic-settings` `BaseSettings` to read all env vars; no defaults for secrets
  - Create `backend/app/core/logging.py` configuring structured JSON logging to stdout; attach as global middleware in `main.py`
  - Create `backend/app/main.py` as the FastAPI app factory: register all routers, attach CORS middleware, attach security-header middleware (`HSTS`, `X-Content-Type-Options`, `X-Frame-Options`, `CSP`), and register a global exception handler that logs unhandled exceptions with stack trace and returns a generic 500
  - _Requirements: 11.1, 11.3, 11.9, 11.10, 13.3_

- [x] 3. Database setup and Alembic migrations
  - Create `backend/app/db/base.py` with the SQLAlchemy async declarative base
  - Create `backend/app/db/session.py` with the async engine and `AsyncSession` factory using `DATABASE_URL` from config
  - Create `backend/app/core/dependencies.py` with `get_db` (yields `AsyncSession`) and stub `get_current_user` / `require_role` dependencies
  - Initialise Alembic (`alembic init`) in `backend/` and configure `alembic.ini` and `env.py` to use the async engine and import all models
  - Create all SQLAlchemy ORM models in `backend/app/models/`: `User`, `Tutor`, `AvailabilitySlot`, `Booking`, `Payment`, `Message`, `Review`, `PriceConfig`, `PasswordResetToken`, `JwtDenylist` — matching the schema defined in the design document (UUID PKs, TIMESTAMPTZ, INTEGER cents, JSONB columns, all indexes)
  - Generate and apply the initial Alembic migration creating all tables
  - _Requirements: 11.2, 11.4, 4.10, 14.1, 14.3_

- [x] 4. Health endpoint
  - Create `backend/app/routers/health.py` implementing `GET /health`: attempt a lightweight DB query; return `{"status": "ok"}` (200) on success or `{"status": "degraded"}` (503) on DB failure
  - Register the health router in `main.py`
  - _Requirements: 11.5, 11.6_

- [x] 5. Authentication — backend
  - Create `backend/app/core/security.py` implementing: `hash_password` (bcrypt, cost 12), `verify_password`, `create_access_token` (HS256, 24 h expiry, `jti` claim), `decode_access_token`, and `is_token_denylisted` (checks `jwt_denylist` table)
  - Update `get_current_user` in `dependencies.py` to decode the Bearer token, check the denylist, and return the user; return 401 on failure
  - Implement `require_role` dependency factory that raises 403 if the user's role is not in the allowed set
  - Create `backend/app/schemas/auth.py` with Pydantic models: `RegisterRequest`, `LoginRequest`, `TokenResponse`, `ResetPasswordRequestBody`, `ResetPasswordConfirmBody`
  - Create `backend/app/services/auth_service.py` implementing: `register_student`, `login`, `logout` (insert JTI into denylist), `request_password_reset` (generate token, hash, store, trigger email), `confirm_password_reset` (validate token, update password, mark used)
  - Create `backend/app/routers/auth.py` wiring the five auth endpoints to the service; apply rate limiting (slowapi or custom middleware) of 10 req/60 s per IP on `/auth/login` and `/auth/register`
  - _Requirements: 1.1–1.12, 13.1, 13.4, 13.7_

  - [ ]* 5.1 Write property test: password hashing correctness
    - **Property 4: Password hashing correctness**
    - For any plaintext password ≥ 8 chars, `verify_password(plain, hash_password(plain))` is True and `hash_password(plain) != plain`
    - **Validates: Requirements 13.1**

  - [ ]* 5.2 Write property test: JWT claims round-trip
    - **Property 5: JWT claims round-trip**
    - For any (id, email, role) triple, `decode_access_token(create_access_token(...))` returns equal claims and `exp - iat == 86400`
    - **Validates: Requirements 1.5, 1.8**

- [x] 6. Checkpoint — auth layer
  - Ensure all auth unit tests and property tests pass; verify `/health`, `/auth/register`, `/auth/login`, and `/auth/logout` respond correctly via `pytest` with the async test client
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Serialisation utilities and Pydantic base schemas
  - Create `backend/app/schemas/base.py` with a shared Pydantic `BaseModel` subclass that: serialises `datetime` as ISO 8601 UTC strings, serialises monetary integers as integers (no float coercion), and uses `model_config = ConfigDict(populate_by_name=True)`
  - Create `backend/app/utils/datetime_utils.py` with `to_utc_iso(dt)` and `from_iso_to_utc(s)` helpers
  - Create `backend/app/utils/currency.py` with `cents_to_display(cents, currency)` helper
  - Ensure all response schemas inherit from the shared base
  - _Requirements: 14.1, 14.2, 14.3, 14.5_

  - [ ]* 7.1 Write property test: datetime serialisation round-trip
    - **Property 1: Datetime serialisation round-trip**
    - For any UTC-aware `datetime`, `from_iso_to_utc(to_utc_iso(dt)) == dt`
    - **Validates: Requirements 14.1, 14.2, 14.4**

  - [ ]* 7.2 Write property test: monetary amount round-trip
    - **Property 2: Monetary amount round-trip**
    - For any non-negative integer cents value, JSON serialise → deserialise produces the same integer (no float drift)
    - **Validates: Requirements 14.3, 14.4**

  - [ ]* 7.3 Write property test: API response fields are snake_case
    - **Property 3: API response fields are snake_case**
    - For any response schema instance, all keys in `model.model_dump()` match `^[a-z][a-z0-9_]*$`
    - **Validates: Requirements 14.5**

- [x] 8. Tutor profile — backend
  - Create `backend/app/models/tutor.py` (already scaffolded in task 3; ensure JSONB fields and `avg_rating`/`review_count` columns are present)
  - Create `backend/app/schemas/tutors.py` with `TutorProfileResponse` (includes `avg_rating`, `review_count`, last 5 reviews) and `TutorUpdateRequest`
  - Create `backend/app/services/tutor_service.py` implementing `get_tutor_profile(tutor_id)` (joins reviews) and `update_tutor_profile(tutor_id, data)` (admin only)
  - Create `backend/app/routers/tutors.py` with `GET /tutors/{id}` (public) and `PATCH /tutors/{id}` (admin)
  - _Requirements: 2.1–2.7, 9.7_

- [x] 9. Availability — backend
  - Create `backend/app/schemas/availability.py` with `SlotCreate` (supports optional `recurrence` object with `pattern: weekly`, `weeks_ahead: int ≤ 8`), `SlotResponse`, `SlotUpdate`
  - Create `backend/app/services/availability_service.py` implementing:
    - `list_available_slots(tutor_id)` — returns future `available` slots only
    - `create_slots(data)` — single or recurring; generates individual slots up to 8 weeks; rejects overlapping slots with 409
    - `update_slot(slot_id, data)` — admin only
    - `delete_slot(slot_id)` — cancels associated booking and triggers notification if one exists
  - Create `backend/app/routers/availability.py` wiring the four endpoints
  - _Requirements: 3.1–3.7, 9.6_

  - [ ]* 9.1 Write property test: slot conflict detection
    - **Property 6: Slot conflict detection**
    - For any pair of overlapping time intervals for the same tutor, the second `create_slots` call SHALL raise a 409 conflict
    - **Validates: Requirements 3.3**

- [x] 10. Bookings — backend
  - Create `backend/app/schemas/bookings.py` with `BookingCreate`, `BookingResponse`, `BookingCancelRequest`
  - Create `backend/app/services/booking_service.py` implementing:
    - `create_booking(student_id, slot_id)` — sets status `pending_payment`, sets `reserved_until = now + 15 min`, prevents duplicate booking (409)
    - `confirm_booking(booking_id)` — sets status `confirmed`, updates slot to `booked`
    - `cancel_booking(booking_id, actor)` — sets status `cancelled`; if >24 h before start, triggers refund; sends cancellation email
    - `get_booking(booking_id, user)` — enforces ownership or admin role
    - `list_bookings(user)` — student sees own, admin sees all; sorted by start desc
    - `expire_pending_bookings()` — background task: release slots where `reserved_until < now` and status is `pending_payment`
  - Create `backend/app/routers/bookings.py` wiring the four endpoints
  - Register `expire_pending_bookings` as a FastAPI background task or APScheduler job
  - _Requirements: 4.1–4.10, 9.3, 9.4_

  - [ ]* 10.1 Write property test: no double-booking
    - **Property 7: No double-booking**
    - For any slot with a `confirmed` booking, a second `create_booking` call for the same slot SHALL be rejected with 409
    - **Validates: Requirements 4.5**

- [x] 11. Payments — backend
  - Create `backend/app/schemas/payments.py` with `CheckoutSessionResponse` and `WebhookPayload`
  - Create `backend/app/services/payment_service.py` implementing:
    - `create_checkout_session(booking_id, student)` — looks up `price_configs`, creates Stripe Checkout Session, stores `stripe_session_id` on booking, returns `session_url`
    - `handle_webhook(raw_body, stripe_signature)` — verifies signature (400 on failure); on `checkout.session.completed` calls `confirm_booking`; on `charge.refund.updated` records refund and sets booking to `refunded`; uses `stripe_event_id` as idempotency key
    - `initiate_refund(booking_id)` — calls Stripe Refunds API
  - Create `backend/app/routers/payments.py` wiring `POST /payments/checkout` (student auth) and `POST /payments/webhook` (no auth, raw body)
  - Seed `price_configs` table with the three pricing tiers from the existing Pricing component
  - _Requirements: 5.1–5.9, 9.9_

- [x] 12. Checkpoint — booking and payment flow
  - Write pytest integration tests covering: booking creation → Stripe checkout → webhook confirmation → slot status update → cancellation with refund logic
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Messaging — backend
  - Create `backend/app/schemas/messages.py` with `MessageCreate`, `MessageResponse`, `ThreadResponse`
  - Create `backend/app/services/messaging_service.py` implementing:
    - `list_threads(user_id)` — returns all threads for the user
    - `get_thread(thread_id, user_id)` — returns paginated messages (50/page, asc); marks messages as read
    - `send_message(sender_id, recipient_id, body)` — validates recipient is the assigned tutor (403 otherwise); validates body ≤ 5000 chars; stores message; schedules 5-min delayed email notification
    - `mark_read(message_id, user_id)` — sets `is_read = true`
  - Create `backend/app/routers/messages.py` wiring the four endpoints
  - _Requirements: 7.1–7.8_

- [x] 14. Reviews — backend
  - Create `backend/app/schemas/reviews.py` with `ReviewCreate`, `ReviewResponse`, `ReviewVisibilityUpdate`
  - Create `backend/app/services/review_service.py` implementing:
    - `submit_review(booking_id, student_id, rating, comment)` — validates booking is `completed` and belongs to student; rejects duplicate (409); stores review; recalculates `avg_rating` and `review_count` on `tutors` table
    - `list_reviews(tutor_id)` — returns visible reviews sorted by `submitted_at` desc
    - `set_visibility(review_id, is_hidden)` — admin only
  - Create `backend/app/routers/reviews.py` wiring the three endpoints
  - _Requirements: 8.1–8.8, 9.8_

  - [ ]* 14.1 Write property test: review rating and message length validation
    - **Property 8: Review rating and message length validation**
    - For any rating outside [1, 5], `submit_review` SHALL be rejected; for any message body with `len > 5000`, `send_message` SHALL be rejected
    - **Validates: Requirements 8.2, 7.6**

  - [ ]* 14.2 Write property test: average rating calculation
    - **Property 9: Average rating calculation**
    - For any non-empty list of ratings in [1, 5], `calculate_avg_rating(ratings) == round(mean(ratings), 1)`
    - **Validates: Requirements 8.4**

- [x] 15. Email notifications — backend
  - Create `backend/app/services/notification_service.py` implementing `send_email(to, template_name, context)` using the Resend REST API (provider selected via env var); implement retry logic: up to 3 attempts with exponential backoff; log failure without blocking caller
  - Create HTML email templates in `backend/app/templates/`: `welcome.html`, `booking_confirmation.html`, `lesson_reminder.html`, `cancellation.html`, `post_lesson.html` — all using Fluency Tutoring branding (logo, brand colours)
  - Wire notification calls into the relevant services: welcome on register, booking confirmation on `confirmed`, reminder 24 h before lesson (background task), cancellation on cancel, post-lesson on `completed`
  - Create `backend/app/tasks/reminder_task.py` as a scheduled background task that queries upcoming lessons in the next 24–25 h window and sends reminder emails
  - _Requirements: 12.1–12.8_

- [x] 16. Video lesson room — backend
  - Create `backend/app/services/video_service.py` implementing `create_room(booking_id)` using the Daily.co REST API: creates a room with `exp` set to lesson end time + 30 min; stores `video_room_url` on the booking
  - Call `create_room` when a booking transitions to `confirmed`
  - _Requirements: 6.1, 6.5_

- [x] 17. Checkpoint — all backend domains
  - Run the full pytest suite; ensure all unit tests, integration tests, and property tests pass
  - Verify structured JSON logs appear on stdout for unhandled exceptions
  - Ensure all tests pass, ask the user if questions arise.

- [x] 18. Frontend — React Router and auth context
  - Install dependencies: `react-router-dom@6`, `axios`, `@daily-co/daily-js`; update `package.json`
  - Rename `fluency-tutoring/src/index.jsx` entry point to wrap the app in `<BrowserRouter>`; update `App.jsx` to define all routes using React Router v6 `<Routes>` / `<Route>`
  - Create `fluency-tutoring/src/context/AuthContext.jsx` storing JWT in `localStorage`, exposing `user`, `login(token)`, `logout()` helpers; call logout endpoint on `logout()`
  - Create `fluency-tutoring/src/context/NotificationContext.jsx` polling `/api/messages/threads` every 30 s to compute unread count
  - Create `fluency-tutoring/src/hooks/useAuth.js`, `useApi.js` (Axios instance with `Authorization` interceptor and 401 redirect), `useUnreadCount.js`
  - Create `fluency-tutoring/src/utils/dateUtils.js` (UTC ↔ local timezone) and `formatCurrency.js` (cents → display string)
  - _Requirements: 1.5, 4.1, 7.4_

- [x] 19. Frontend — authentication pages
  - Create `fluency-tutoring/src/pages/auth/Register.jsx`: form collecting first name, last name, email, password, CEFR level; POST to `/api/auth/register`; store JWT; redirect to student dashboard
  - Create `fluency-tutoring/src/pages/auth/Login.jsx`: form with email and password; POST to `/api/auth/login`; store JWT; redirect to dashboard
  - Create `fluency-tutoring/src/pages/auth/ResetPassword.jsx`: two-step flow — request form (email) and confirm form (token + new password)
  - Add auth-aware links to `Nav.jsx`: show Login/Register when unauthenticated; show Dashboard/Logout when authenticated
  - _Requirements: 1.1–1.12_

- [x] 20. Frontend — tutor profile page
  - Create `fluency-tutoring/src/pages/tutor/TutorProfile.jsx`: fetch `GET /api/tutors/{id}`; display all profile fields, average rating, review count, and the 5 most recent reviews
  - Add a "Book a Lesson" CTA that navigates authenticated students to `/booking` and unauthenticated visitors to `/register`
  - _Requirements: 2.1–2.6_

- [x] 21. Frontend — booking calendar and payment flow
  - Create `fluency-tutoring/src/pages/booking/BookingCalendar.jsx`: fetch available slots from `GET /api/availability?tutor_id=...`; display as a calendar grid; on slot selection POST to `/api/bookings` then POST to `/api/payments/checkout`; redirect to Stripe Checkout URL
  - Create `fluency-tutoring/src/pages/booking/BookingSuccess.jsx`: display lesson date/time and link to student dashboard (shown after Stripe success redirect)
  - Create `fluency-tutoring/src/pages/booking/BookingCancelled.jsx`: display payment-not-completed message with retry option (shown after Stripe cancel redirect)
  - _Requirements: 4.1–4.3, 5.1–5.8_

- [x] 22. Frontend — lesson room
  - Create `fluency-tutoring/src/pages/lesson/LessonRoom.jsx`: fetch booking detail; if >10 min before start, show waiting room countdown; if within 10 min, embed Daily.co `<DailyIframe>` using `video_room_url`; if past end time, show session-ended message with link to review form
  - Enforce ownership: redirect to 403 page if booking does not belong to current user
  - _Requirements: 6.1–6.6_

- [x] 23. Frontend — student dashboard
  - Create `fluency-tutoring/src/pages/dashboard/StudentDashboard.jsx`: display upcoming and past bookings fetched from `GET /api/bookings`; show cancel button for upcoming bookings (>24 h); link to lesson room for upcoming lessons; link to review form for completed lessons
  - _Requirements: 4.9, 6.7_

- [x] 24. Frontend — messaging inbox
  - Create `fluency-tutoring/src/pages/messages/Inbox.jsx`: fetch threads from `GET /api/messages/threads`; display thread list; on thread select fetch messages from `GET /api/messages/threads/{id}` (paginated); render message list; provide send-message form (POST `/api/messages`); mark messages read on open
  - Display unread badge in `Nav.jsx` using `NotificationContext`
  - _Requirements: 7.1–7.8_

- [x] 25. Frontend — review form
  - Create `fluency-tutoring/src/pages/reviews/ReviewForm.jsx`: star rating selector (1–5) and optional comment textarea (max 1000 chars); POST to `/api/reviews`; show success confirmation; disable form if review already submitted
  - _Requirements: 8.1–8.3_

- [x] 26. Frontend — admin dashboard
  - Create `fluency-tutoring/src/pages/dashboard/AdminDashboard.jsx` with four tabs:
    - **Overview**: summary stats (total bookings this month, revenue, upcoming lessons, total students) fetched from a dedicated admin stats endpoint
    - **Bookings**: filterable table of all bookings; cancel button per row
    - **Students**: table of all students with name, email, registration date, lesson count
    - **Availability**: calendar interface for creating/editing/deleting slots (calls availability endpoints)
    - **Tutor Profile**: form to update tutor profile fields (PATCH `/api/tutors/{id}`)
    - **Reviews**: moderation table with hide/unhide toggle per review
  - Protect route: redirect non-admin users to home
  - _Requirements: 9.1–9.9_

- [x] 27. Frontend — marketing enhancements
  - Update `fluency-tutoring/src/components/Nav.jsx`: add hamburger icon (visible on viewports < 768 px); toggle full-width dropdown on click; close dropdown on link tap; add auth-aware links
  - Create `fluency-tutoring/src/components/FAQ.jsx`: accordion with ≥ 6 items; clicking an item expands it and collapses any other open item
  - Update `fluency-tutoring/src/components/Footer.jsx`: add social media links, WhatsApp contact link, privacy policy link, and terms of service link
  - Add scroll-triggered fade-in / slide-up entrance animations to each marketing section using `IntersectionObserver` (no external animation library required)
  - Add `FAQ` to `fluency-tutoring/src/pages/Home.jsx` between Testimonials and Contact
  - _Requirements: 10.1–10.8_

- [x] 28. Frontend — accessibility and performance
  - Audit all interactive elements for keyboard navigability: ensure all buttons, links, form fields, and accordion items have correct `tabIndex`, `aria-*` attributes, and visible focus styles
  - Ensure all images have descriptive `alt` text; form inputs have associated `<label>` elements; colour contrast meets WCAG AA
  - Verify the Vite build produces code-split chunks; add `loading="lazy"` to below-the-fold images
  - _Requirements: 10.9, 10.10_

- [x] 29. Checkpoint — frontend
  - Run `npm run build` in `fluency-tutoring/`; confirm zero build errors
  - Run Vitest unit tests for auth context, booking calendar slot selection, FAQ accordion toggle, and Nav hamburger toggle
  - Ensure all tests pass, ask the user if questions arise.

- [x] 30. Integration wiring and end-to-end validation
  - Verify Docker Compose `docker compose up --build` starts all four services without errors
  - Confirm Nginx proxy correctly routes `/api/*` to the FastAPI service and `/*` to the frontend
  - Confirm HTTP → HTTPS redirect is active on the proxy container
  - Confirm all security headers (`HSTS`, `X-Content-Type-Options`, `X-Frame-Options`, `CSP`) are present on API responses
  - Confirm the `/api/health` endpoint returns `{"status": "ok"}` when the DB is up
  - _Requirements: 11.8, 13.2, 13.3_

- [x] 31. Final checkpoint — full test suite
  - Run the complete pytest suite (`pytest backend/` with `--asyncio-mode=auto`); all tests must pass
  - Run `npm run test -- --run` in `fluency-tutoring/`; all Vitest tests must pass
  - Confirm all 9 Hypothesis property tests execute ≥ 100 iterations each without counterexamples
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints (tasks 6, 12, 17, 29, 31) ensure incremental validation at logical phase boundaries
- Property tests (Properties 1–9) validate universal correctness guarantees using Hypothesis
- Unit tests validate specific examples, edge cases, and error conditions
- The database schema is designed for multi-tutor v2 from day one (`tutor_id` FK on bookings, separate `tutors` table)
- All secrets are read from environment variables; `.env.example` documents every required variable
