# Fluency German — Online Tutoring Platform

A full-stack platform for one-to-one online German lessons. Students find a tutor, book an available slot, pay online and join the lesson by video. Tutors manage their availability, bookings, messages and reviews.

I built and deployed this platform myself on AWS EC2, and I use it as the base for my German tutoring work. The application, infrastructure and CI/CD pipeline are all in this repository.

> **Status:** the platform is currently being relaunched. The code, tests and pipeline run; the production server is offline until paid services (Stripe, Daily.co video) are reconnected.

---

## Features

- **Accounts and authentication:** registration, login and logout with JWT, password reset by email, and a token denylist so logged-out tokens can't be reused
- **Rate limiting** on authentication endpoints
- **Tutor profiles** and **availability slots** that tutors create, edit and remove
- **Bookings:** students book a free slot; the slot is held for 15 minutes while they pay
- **Cancellation policy:** students can cancel up to 12 hours before a lesson for a full refund; with less notice the lesson counts as used. Cancellations by the tutor are always refunded
- **Payments with Stripe Checkout**, confirmed through a Stripe webhook
- **Video lessons:** a Daily.co video room is created automatically for each confirmed booking
- **Messaging** between students and tutors, with read status
- **Reviews**, with admins able to hide or unhide a review
- **Email notifications** through Resend (sent in the background, so pages never wait for email), including a lesson reminder 24 hours before each lesson
- **Background jobs** inside the API: release unpaid reservations after 15 minutes, mark finished lessons as completed (so students can review them), and send lesson reminders

---

## Architecture

```
                 Internet
                    │
            ┌───────▼────────┐
            │  Nginx proxy   │   ports 80 → 443 (HTTP redirects to HTTPS)
            └──┬──────────┬──┘
     /api/*    │          │   everything else
       ┌───────▼───┐  ┌───▼──────────┐
       │  API      │  │  Frontend    │
       │  FastAPI  │  │  React (Nginx│
       │  :8000    │  │  static) :80 │
       └─────┬─────┘  └──────────────┘
             │
       ┌─────▼──────┐
       │ PostgreSQL │   persistent volume (pgdata)
       └────────────┘

External services: Stripe (payments) · Daily.co (video) · Resend (email)
```

All four services run with **Docker Compose** on a single EC2 instance. Only the proxy publishes ports; the API, frontend and database are reachable only inside the Docker network. The database has a health check, and the API waits for it to be healthy before starting. On startup, the API runs database migrations (Alembic) before launching the server.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, React Router, Vite, Axios, served by Nginx |
| Backend | Python 3.12, FastAPI, Uvicorn, SQLAlchemy (async), asyncpg, Alembic, Pydantic |
| Database | PostgreSQL 16 |
| Auth and security | JWT (python-jose), bcrypt, slowapi rate limiting |
| Integrations | Stripe, Daily.co, Resend |
| Infrastructure | Docker, Docker Compose, Nginx reverse proxy with TLS, AWS EC2 |
| CI/CD | GitHub Actions, GitHub Container Registry, Trivy |
| Testing | pytest, pytest-asyncio, Hypothesis |

---

## Repository Structure

```
fluency-platform/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── routers/          # API endpoints (auth, tutors, bookings, payments, ...)
│   │   ├── services/         # business logic (booking, payment, video, notification, ...)
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── tasks/            # background tasks (lesson reminders)
│   │   └── main.py           # app setup, CORS, rate limiting, routers
│   ├── tests/                # pytest test suite
│   ├── Dockerfile
│   └── entrypoint.sh         # runs migrations, then starts Uvicorn
├── fluency-tutoring/         # React frontend (Vite)
│   ├── src/pages/            # auth, booking, dashboard, lesson, messages, reviews, tutor
│   ├── Dockerfile            # multi-stage: Node build → Nginx
│   └── nginx.conf
├── proxy/nginx.conf          # reverse proxy and TLS termination
├── docker-compose.yml        # one file: builds locally, or pulls pipeline images on the server
├── .github/workflows/ci-cd.yml
└── .env.example              # all required environment variables
```

---

## API Overview

All endpoints are served under `/api`.

| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/reset-password/request`, `/auth/reset-password/confirm` |
| Tutors | `GET /tutors/{id}`, `PATCH /tutors/{id}` |
| Availability | `GET`, `POST /availability`, `PATCH`, `DELETE /availability/{slot_id}` |
| Bookings | `POST`, `GET /bookings`, `GET /bookings/{id}`, `POST /bookings/{id}/cancel` |
| Payments | `POST /payments/checkout`, `POST /payments/webhook` |
| Messages | `GET /messages/threads`, `GET /messages/threads/{user_id}`, `POST /messages`, `PATCH /messages/{id}/read` |
| Reviews | `POST`, `GET /reviews`, `PATCH /reviews/{id}/visibility` |

Interactive API docs are available at `/docs` when `ENVIRONMENT` is not `production`; they are switched off in production.

---

## Running Locally

**Requirements:** Docker and Docker Compose.

```bash
git clone https://github.com/sundayinibehe75-afk/fluency-platform.git
cd fluency-platform
cp .env.example .env      # then fill in the values
docker compose up -d --build
```

The proxy expects TLS certificates in `proxy/certs/`. For local testing, a self-signed certificate is enough.

### First-time setup: admin account and slots

Sign-up only creates student accounts. The tutor uses an **admin** account, created once from the server. The login comes from environment variables, never from the code:

```bash
docker compose exec -e ADMIN_EMAIL=you@example.com -e ADMIN_PASSWORD='a-long-password' api python seed.py
docker compose exec api python add_slots.py   # optional: sample slots for the next 7 days
```

### Configuration

All settings come from environment variables. See `.env.example` for descriptions.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string |
| `POSTGRES_PASSWORD` | Database password |
| `JWT_SECRET` | Long random secret for signing tokens |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Stripe payments and webhook verification |
| `RESEND_API_KEY` | Transactional email |
| `DAILY_API_KEY` | Video rooms |
| `FRONTEND_URL` | Public URL, used for CORS and email links |
| `ENVIRONMENT` | `development`, `staging` or `production` |
| `EMAIL_FROM` | Optional sender, default `Fluency German <noreply@fluencygerman.com>` (domain must be verified in Resend) |

Secrets are never committed. The `.env` file is created on each machine from `.env.example`.

---

## Testing

```bash
cd backend
pip install -r requirements.txt
python -m pytest -q tests
```

Unit tests cover availability, messaging, notifications, reviews, video rooms and security properties (including property-based tests with Hypothesis) and need no database.

Integration tests (`tests/test_booking_flow.py`) cover the booking, payment, cancellation and refund rules against a real PostgreSQL database built from the Alembic migrations. They run when `TEST_DATABASE_URL` is set and are skipped otherwise; the CI pipeline provides a PostgreSQL service for them:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/fluency_test python -m pytest -q tests
```

---

## CI/CD Pipeline

Every push to `main` runs the GitHub Actions pipeline in `.github/workflows/ci-cd.yml`:

1. **Test:** backend unit and integration tests (pytest, with a PostgreSQL service) and the frontend build run in parallel.
2. **Build:** Docker images for the API and frontend are built and tagged with the commit SHA and `latest`.
3. **Scan:** each image is scanned with **Trivy**; any fixable HIGH or CRITICAL vulnerability stops the pipeline.
4. **Push:** images that pass the scan are pushed to GitHub Container Registry.
5. **Approve:** the `production` environment requires a manual approval before deployment.
6. **Deploy:** the pipeline connects to the server over SSH, pulls the new images and restarts the stack, then runs a health check.

Deployment secrets (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`) are stored in the GitHub `production` environment.

---

## Deployment

On the server (Ubuntu on AWS EC2):

```bash
cd ~/fluency-platform
export IMAGE_TAG=<commit-sha>        # or leave unset to use "latest"
docker compose pull api frontend
docker compose up -d --no-build
```

The server runs the images built and scanned by the pipeline, not images built on the server. Rolling back means deploying an earlier commit SHA.

---

## Author

**Inibehe Emmanuel Sunday** — DevOps & Cloud Engineer and German tutor
[LinkedIn](https://www.linkedin.com/in/emmanuel-sunday-210a08323) · [GitHub](https://github.com/sundayinibehe75-afk)
