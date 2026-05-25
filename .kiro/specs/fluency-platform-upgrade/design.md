# Design Document: Fluency Platform Upgrade

## Overview

Upgrade the static React marketing site into a full-featured single-tutor language learning platform. Students register, book and pay for lessons, attend video sessions, message the tutor, and leave reviews. The schema is designed for multi-tutor expansion (v2) from day one.

**Stack:** React (Vite) · FastAPI · PostgreSQL · Alembic · Docker Compose · Nginx · Stripe · Daily.co · Resend · JWT (24 h, bcrypt-12, Redis/DB denylist)

---

## Architecture

### Docker Compose Services

| Service | Image / Build | Ports (internal) | Notes |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | Named volume `pgdata`; env vars from `.env` |
| `api` | `./backend` (Python 3.12) | 8000 | `uvicorn app.main:app`; `depends_on: db` |
| `frontend` | `./fluency-tutoring` (Nginx) | 80 | Vite build artefacts served by Nginx |
| `proxy` | `nginx:alpine` | **80, 443** | Routes `/api/*` → `api:8000`; `/*` → `frontend:80`; HTTP→HTTPS 301 |

All secrets injected via environment variables; no hardcoded values.

---

## Project Folder Structure

```
fluency-platform-upgrade/
├── docker-compose.yml
├── .env.example
├── fluency-tutoring/               # Existing React frontend (extended)
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                 # React Router v6 route definitions
│       ├── style.css
│       ├── context/
│       │   ├── AuthContext.jsx     # JWT state, login/logout helpers
│       │   └── NotificationContext.jsx  # Unread message count
│       ├── components/             # Existing marketing components (retained)
│       │   ├── Nav.jsx             # Enhanced: hamburger, auth-aware links
│       │   ├── Hero.jsx
│       │   ├── About.jsx
│       │   ├── Offerings.jsx
│       │   ├── Pricing.jsx
│       │   ├── Testimonials.jsx
│       │   ├── Contact.jsx
│       │   ├── Footer.jsx          # Enhanced: social/legal links
│       │   └── FAQ.jsx             # New: accordion FAQ
│       ├── pages/
│       │   ├── Home.jsx
│       │   ├── auth/
│       │   │   ├── Register.jsx
│       │   │   ├── Login.jsx
│       │   │   └── ResetPassword.jsx
│       │   ├── tutor/
│       │   │   └── TutorProfile.jsx
│       │   ├── booking/
│       │   │   ├── BookingCalendar.jsx
│       │   │   ├── BookingSuccess.jsx
│       │   │   └── BookingCancelled.jsx
│       │   ├── lesson/
│       │   │   └── LessonRoom.jsx  # Daily.co embed + waiting room
│       │   ├── dashboard/
│       │   │   ├── StudentDashboard.jsx
│       │   │   └── AdminDashboard.jsx
│       │   ├── messages/
│       │   │   └── Inbox.jsx
│       │   └── reviews/
│       │       └── ReviewForm.jsx
│       ├── hooks/
│       │   ├── useAuth.js
│       │   ├── useApi.js           # Axios instance with JWT interceptor
│       │   └── useUnreadCount.js
│       └── utils/
│           ├── dateUtils.js        # UTC ↔ local timezone
│           └── formatCurrency.js  # Cents → display string
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── alembic.ini
    └── app/
        ├── main.py                 # App factory, middleware, router registration
        ├── core/
        │   ├── config.py           # pydantic-settings; reads all env vars
        │   ├── security.py         # JWT encode/decode, bcrypt, denylist
        │   ├── dependencies.py     # get_db, get_current_user, require_role
        │   └── logging.py          # Structured JSON logging
        ├── db/
        │   ├── base.py             # SQLAlchemy declarative base
        │   ├── session.py          # Async engine + session factory
        │   └── migrations/         # Alembic env.py + versions/
        ├── routers/
        │   ├── auth.py
        │   ├── users.py
        │   ├── tutors.py
        │   ├── availability.py
        │   ├── bookings.py
        │   ├── payments.py
        │   ├── messages.py
        │   └── reviews.py
        ├── models/                 # SQLAlchemy ORM models (one file per domain)
        ├── schemas/                # Pydantic request/response schemas
        ├── services/               # Business logic (one file per domain)
        └── tasks/                  # Background tasks (slot expiry, email retry)
```

---

## Database Schema

All PKs are UUID v4. All timestamps are `TIMESTAMPTZ` (UTC). Monetary amounts are `INTEGER` (cents).

### `users`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK, default gen_random_uuid() |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE |
| `password_hash` | `VARCHAR(255)` | NOT NULL |
| `first_name` | `VARCHAR(100)` | NOT NULL |
| `last_name` | `VARCHAR(100)` | NOT NULL |
| `role` | `VARCHAR(20)` | NOT NULL — `student` \| `tutor` \| `admin` |
| `cefr_level` | `VARCHAR(5)` | nullable — A0–C2 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

Indexes: `users_email_idx` UNIQUE on `email`.

---

### `tutors`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | NOT NULL, FK → `users.id`, UNIQUE |
| `display_name` | `VARCHAR(150)` | NOT NULL |
| `bio` | `TEXT` | nullable |
| `photo_url` | `VARCHAR(500)` | nullable |
| `spoken_languages` | `JSONB` | NOT NULL, default `[]` |
| `specialisms` | `JSONB` | NOT NULL, default `[]` |
| `cefr_levels_taught` | `JSONB` | NOT NULL, default `[]` |
| `years_experience` | `INTEGER` | nullable |
| `avg_rating` | `NUMERIC(3,1)` | NOT NULL, default 0.0 |
| `review_count` | `INTEGER` | NOT NULL, default 0 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

---

### `availability_slots`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `tutor_id` | `UUID` | NOT NULL, FK → `tutors.id` |
| `start_at` | `TIMESTAMPTZ` | NOT NULL |
| `end_at` | `TIMESTAMPTZ` | NOT NULL |
| `duration_minutes` | `INTEGER` | NOT NULL |
| `status` | `VARCHAR(20)` | NOT NULL — `available` \| `booked` |
| `recurrence_group_id` | `UUID` | nullable — links slots from same recurring pattern |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

Indexes: `slots_tutor_start_idx` on `(tutor_id, start_at)`; `slots_status_idx` on `status`.

---

### `bookings`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `student_id` | `UUID` | NOT NULL, FK → `users.id` |
| `tutor_id` | `UUID` | NOT NULL, FK → `tutors.id` |
| `slot_id` | `UUID` | NOT NULL, FK → `availability_slots.id`, UNIQUE |
| `status` | `VARCHAR(30)` | NOT NULL — `pending_payment` \| `confirmed` \| `cancelled` \| `completed` \| `refunded` |
| `price_cents` | `INTEGER` | NOT NULL |
| `currency` | `VARCHAR(3)` | NOT NULL, default `USD` |
| `stripe_session_id` | `VARCHAR(255)` | nullable, UNIQUE |
| `stripe_payment_intent_id` | `VARCHAR(255)` | nullable |
| `video_room_url` | `VARCHAR(500)` | nullable |
| `reserved_until` | `TIMESTAMPTZ` | nullable — 15-min hold window |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

Indexes: `bookings_student_idx` on `student_id`; `bookings_tutor_idx` on `tutor_id`; `bookings_status_idx` on `status`.

---

### `payments`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `booking_id` | `UUID` | NOT NULL, FK → `bookings.id` |
| `stripe_event_id` | `VARCHAR(255)` | NOT NULL, UNIQUE — idempotency key |
| `event_type` | `VARCHAR(100)` | NOT NULL |
| `amount_cents` | `INTEGER` | NOT NULL |
| `currency` | `VARCHAR(3)` | NOT NULL |
| `status` | `VARCHAR(30)` | NOT NULL — `succeeded` \| `refunded` \| `failed` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

---

### `messages`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `sender_id` | `UUID` | NOT NULL, FK → `users.id` |
| `recipient_id` | `UUID` | NOT NULL, FK → `users.id` |
| `body` | `TEXT` | NOT NULL, max 5000 chars (enforced in app layer) |
| `is_read` | `BOOLEAN` | NOT NULL, default false |
| `sent_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

Indexes: `messages_recipient_idx` on `(recipient_id, is_read)`; `messages_thread_idx` on `(sender_id, recipient_id, sent_at)`.

---

### `reviews`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `booking_id` | `UUID` | NOT NULL, FK → `bookings.id`, UNIQUE |
| `student_id` | `UUID` | NOT NULL, FK → `users.id` |
| `tutor_id` | `UUID` | NOT NULL, FK → `tutors.id` |
| `rating` | `SMALLINT` | NOT NULL, CHECK (rating BETWEEN 1 AND 5) |
| `comment` | `TEXT` | nullable, max 1000 chars |
| `is_hidden` | `BOOLEAN` | NOT NULL, default false |
| `submitted_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

Indexes: `reviews_tutor_idx` on `(tutor_id, is_hidden, submitted_at DESC)`.

---

### `price_configs`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `product_key` | `VARCHAR(100)` | NOT NULL, UNIQUE |
| `price_cents` | `INTEGER` | NOT NULL |
| `currency` | `VARCHAR(3)` | NOT NULL, default `USD` |
| `label` | `VARCHAR(255)` | NOT NULL |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

---

### `password_reset_tokens`

| Column | Type | Constraints |
|---|---|---|
| `id` | `UUID` | PK |
| `user_id` | `UUID` | NOT NULL, FK → `users.id` |
| `token_hash` | `VARCHAR(255)` | NOT NULL, UNIQUE |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL |
| `used` | `BOOLEAN` | NOT NULL, default false |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, default NOW() |

---

### `jwt_denylist`

| Column | Type | Constraints |
|---|---|---|
| `jti` | `VARCHAR(255)` | PK |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL |

Pruned by background task: `DELETE WHERE expires_at < NOW()`.

---

## API Routes

All routes are prefixed `/api`. Protected routes require `Authorization: Bearer <token>`. Role abbreviations: `—` = public, `S` = student, `T` = tutor, `A` = admin.

### auth router — `/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create student account; return JWT |
| POST | `/auth/login` | — | Verify credentials; return JWT |
| POST | `/auth/logout` | JWT | Add JTI to denylist |
| POST | `/auth/reset-password/request` | — | Send password reset email |
| POST | `/auth/reset-password/confirm` | — | Apply new password, invalidate token |

### users router — `/users`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/users/me` | JWT | Return current user profile |
| PATCH | `/users/me` | JWT | Update current user profile fields |

### tutors router — `/tutors`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/tutors/{id}` | — | Public tutor profile (includes avg rating, recent reviews) |
| PATCH | `/tutors/{id}` | A | Update tutor profile fields |

### availability router — `/availability`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/availability` | — | List available future slots for a tutor (`?tutor_id=`) |
| POST | `/availability` | A | Create one or more slots (supports `recurrence` body param) |
| PATCH | `/availability/{id}` | A | Update a single slot |
| DELETE | `/availability/{id}` | A | Delete slot; cancels and notifies if booking exists |

### bookings router — `/bookings`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/bookings` | S | Initiate booking → `pending_payment`; reserve slot 15 min |
| GET | `/bookings` | S, A | List bookings (student sees own; admin sees all); sorted by start desc |
| GET | `/bookings/{id}` | S, A | Get single booking detail |
| POST | `/bookings/{id}/cancel` | S, A | Cancel booking; trigger refund if >24 h before start |

### payments router — `/payments`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments/checkout` | S | Create Stripe Checkout Session; return `session_url` |
| POST | `/payments/webhook` | Stripe sig | Handle `checkout.session.completed` and `charge.refund.updated` |

### messages router — `/messages`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/messages/threads` | S, T | List all message threads for current user |
| GET | `/messages/threads/{thread_id}` | S, T | Get paginated messages in thread (50/page, asc) |
| POST | `/messages` | S, T | Send message; 403 if recipient is not assigned tutor |
| PATCH | `/messages/{id}/read` | S, T | Mark message as read |

### reviews router — `/reviews`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/reviews` | S | Submit review for a completed booking |
| GET | `/reviews` | — | List visible reviews for a tutor (`?tutor_id=`); sorted by date desc |
| PATCH | `/reviews/{id}/visibility` | A | Hide or unhide a review |

### misc

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok"}` (200) or `{"status":"degraded"}` (503) |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

**PBT library:** [Hypothesis](https://hypothesis.readthedocs.io/) (Python), minimum 100 iterations per test.

### Property 1: Datetime serialisation round-trip

*For any* UTC-aware `datetime` object, serialising it to an ISO 8601 string and deserialising it back SHALL produce a datetime equal to the original.

**Validates: Requirements 14.1, 14.2, 14.4**

### Property 2: Monetary amount round-trip

*For any* non-negative integer amount in cents, serialising it to JSON and deserialising it back SHALL produce an integer equal to the original (no floating-point drift).

**Validates: Requirements 14.3, 14.4**

### Property 3: API response fields are snake_case

*For any* API response object, all field names in the serialised JSON SHALL match the pattern `^[a-z][a-z0-9_]*$`.

**Validates: Requirements 14.5**

### Property 4: Password hashing correctness

*For any* plaintext password of 8 or more characters, the bcrypt hash SHALL verify correctly against the original password, and the stored hash SHALL NOT equal the plaintext.

**Validates: Requirements 13.1**

### Property 5: JWT claims round-trip

*For any* user record (id, email, role), encoding it into a JWT and decoding the JWT SHALL produce claims equal to the original values, and the `exp` claim SHALL be exactly 86 400 seconds after the `iat` claim.

**Validates: Requirements 1.5, 1.8**

### Property 6: Slot conflict detection

*For any* pair of time intervals that overlap, attempting to create a second availability slot for the same tutor SHALL be rejected with a 409 conflict error.

**Validates: Requirements 3.3**

### Property 7: No double-booking

*For any* availability slot that has a booking in `confirmed` status, any subsequent attempt to create another booking for that slot SHALL be rejected.

**Validates: Requirements 4.5**

### Property 8: Review rating and message length validation

*For any* submitted review, the stored rating SHALL be an integer in [1, 5]; ratings outside this range SHALL be rejected. *For any* message body, it SHALL be accepted if and only if its character count is ≤ 5 000.

**Validates: Requirements 8.2, 7.6**

### Property 9: Average rating calculation

*For any* non-empty list of integer ratings in [1, 5], the computed tutor average SHALL equal the arithmetic mean of the list rounded to one decimal place.

**Validates: Requirements 8.4**

---

## Error Handling

All 4xx/5xx responses return:

```json
{ "error": "ERROR_CODE", "detail": "Human-readable message." }
```

| Status | Code | Trigger |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Pydantic failure |
| 400 | `STRIPE_WEBHOOK_INVALID` | Signature mismatch |
| 401 | `UNAUTHORIZED` | Missing / expired / denylisted JWT |
| 403 | `FORBIDDEN` | Wrong role or resource ownership |
| 404 | `NOT_FOUND` | Resource missing |
| 409 | `SLOT_CONFLICT` | Overlapping availability slot |
| 409 | `BOOKING_CONFLICT` | Slot already booked |
| 409 | `REVIEW_EXISTS` | Duplicate review |
| 429 | `RATE_LIMITED` | >10 auth requests / 60 s from same IP |
| 503 | `DB_UNAVAILABLE` | Health check: DB unreachable |

Unhandled exceptions are caught by a global handler, logged as structured JSON to stdout (with stack trace), and returned as a generic 500.

---

## Testing Strategy

**Backend:** pytest + pytest-asyncio + httpx async test client + Hypothesis (PBT).

**Frontend:** Vitest + React Testing Library.

Property tests (Properties 1–9 above) each run ≥ 100 Hypothesis iterations and are tagged:

```python
# Feature: fluency-platform-upgrade, Property 1: Datetime serialisation round-trip
```

Unit/integration tests cover: auth flows, booking state machine, Stripe webhook idempotency, slot expiry background task, cancellation refund logic, recurring slot generation, message pagination, review duplicate rejection, admin role enforcement, health endpoint.
