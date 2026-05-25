# Requirements Document

## Introduction

This document defines the requirements for upgrading Fluency Tutoring from a static React marketing website into a full-featured, single-tutor language learning platform modelled on Preply. The platform enables students to register, browse the tutor's profile, book and pay for lessons, attend video sessions, exchange messages, and leave reviews — all within a single product. The backend is built with Python + FastAPI, PostgreSQL, and Docker. The database schema and authentication system are designed from the outset to support multiple tutors in a future v2 release, even though v1 ships with a single tutor managed by an admin.

The existing React frontend is extended (not replaced) with new pages and components. Existing marketing sections (Hero, About, Offerings, Pricing, Testimonials, Contact, Footer) are retained and enhanced with mobile navigation, scroll animations, an FAQ section, and an improved footer.

---

## Glossary

- **Platform**: The complete Fluency Tutoring web application, including frontend, backend API, and database.
- **Student**: A registered user with the `student` role who books and attends lessons.
- **Tutor**: A registered user with the `tutor` role who delivers lessons. V1 has exactly one Tutor, created and managed by the Admin.
- **Admin**: A registered user with the `admin` role who manages the Platform configuration, bookings, students, and availability.
- **Auth_Service**: The backend component responsible for JWT issuance, validation, and role enforcement.
- **Booking_Service**: The backend component responsible for creating, confirming, cancelling, and querying lesson bookings.
- **Payment_Service**: The backend component responsible for Stripe checkout session creation and webhook processing.
- **Availability_Service**: The backend component responsible for managing and querying tutor availability slots.
- **Messaging_Service**: The backend component responsible for storing and delivering messages between Students and the Tutor.
- **Video_Service**: The frontend component responsible for embedding the video lesson room via Daily.co or Whereby.
- **Review_Service**: The backend component responsible for storing and retrieving lesson reviews and ratings.
- **Notification_Service**: The backend component responsible for sending transactional emails via Resend or SendGrid.
- **API**: The FastAPI backend application exposing all service endpoints.
- **JWT**: JSON Web Token used for stateless authentication.
- **Availability_Slot**: A time block defined by the Tutor or Admin during which a lesson can be booked.
- **Booking**: A confirmed reservation of an Availability_Slot by a Student, associated with a Payment.
- **Lesson**: A Booking that has been paid for and is either upcoming, in-progress, or completed.
- **Video_Room**: An embedded video call session associated with a Lesson.
- **Review**: A rating (1–5 stars) and optional text comment submitted by a Student after a completed Lesson.
- **Dashboard**: The authenticated web page showing role-specific information and actions.
- **Stripe**: The third-party payment processor used for lesson payments.
- **CEFR**: Common European Framework of Reference for Languages (A1–C2 levels).

---

## Requirements

### Requirement 1: Student Registration and Login

**User Story:** As a prospective student, I want to create an account and log in, so that I can book lessons and access my personal dashboard.

#### Acceptance Criteria

1. THE Platform SHALL provide a registration form that collects first name, last name, email address, password, and current CEFR level (A0–C2).
2. WHEN a registration form is submitted with a valid email and a password of at least 8 characters, THE Auth_Service SHALL create a Student account with the `student` role and return a JWT.
3. WHEN a registration form is submitted with an email address already associated with an existing account, THE Auth_Service SHALL return an error indicating the email is already in use.
4. IF a registration form is submitted with a password shorter than 8 characters, THEN THE Auth_Service SHALL return a validation error specifying the minimum length requirement.
5. WHEN a login form is submitted with a valid email and matching password, THE Auth_Service SHALL return a signed JWT containing the user's ID, email, and role.
6. WHEN a login form is submitted with an email that does not match any account, THE Auth_Service SHALL return a generic authentication error without revealing whether the email exists.
7. WHEN a login form is submitted with a correct email but incorrect password, THE Auth_Service SHALL return a generic authentication error.
8. THE Auth_Service SHALL sign all JWTs with a secret key stored in an environment variable and set an expiry of 24 hours.
9. WHEN a request is received with an expired or invalid JWT, THE Auth_Service SHALL return a 401 Unauthorized response.
10. THE Platform SHALL provide a password reset flow: WHEN a Student submits a valid email address to the reset endpoint, THE Notification_Service SHALL send a password reset email containing a single-use token valid for 1 hour.
11. WHEN a password reset token is submitted alongside a new password of at least 8 characters, THE Auth_Service SHALL update the account password and invalidate the token.
12. IF a password reset token has expired or has already been used, THEN THE Auth_Service SHALL return an error indicating the token is invalid.

---

### Requirement 2: Tutor Profile Page

**User Story:** As a prospective student, I want to view the tutor's profile, so that I can learn about their background, qualifications, and teaching style before booking.

#### Acceptance Criteria

1. THE Platform SHALL display a public Tutor Profile page at a stable URL that requires no authentication to view.
2. THE Tutor Profile page SHALL display the tutor's display name, profile photo, spoken languages, teaching specialisms, CEFR levels taught, years of experience, and a biography.
3. THE Tutor Profile page SHALL display the tutor's average star rating and total number of completed Reviews.
4. THE Tutor Profile page SHALL display the most recent 5 Reviews, each showing the reviewer's first name, star rating, written comment, and the date of the review.
5. THE Tutor Profile page SHALL display a "Book a Lesson" call-to-action that navigates authenticated Students to the booking flow and navigates unauthenticated visitors to the registration page.
6. THE Admin SHALL be able to update all tutor profile fields via the Admin Dashboard without requiring a code deployment.
7. WHEN tutor profile data is updated by the Admin, THE Platform SHALL reflect the updated data on the Tutor Profile page within 5 seconds of the update being saved.

---

### Requirement 3: Availability Calendar

**User Story:** As a tutor (or admin acting on behalf of the tutor), I want to define available time slots, so that students can only book lessons at times I am free.

#### Acceptance Criteria

1. THE Availability_Service SHALL store Availability_Slots with a start datetime, end datetime, duration in minutes, and a status of `available` or `booked`.
2. THE Admin Dashboard SHALL provide a calendar interface for creating, editing, and deleting Availability_Slots.
3. WHEN an Availability_Slot is created with a start datetime that overlaps an existing slot for the same Tutor, THE Availability_Service SHALL return a conflict error and reject the creation.
4. WHEN a Student views the booking calendar, THE Availability_Service SHALL return only Availability_Slots with status `available` and a start datetime in the future.
5. THE Availability_Service SHALL support recurring slot creation: WHEN the Admin defines a weekly recurring pattern, THE Availability_Service SHALL generate individual Availability_Slots for each occurrence up to 8 weeks in advance.
6. WHEN an Availability_Slot is deleted by the Admin and a confirmed Booking exists for that slot, THE Booking_Service SHALL cancel the Booking and THE Notification_Service SHALL send a cancellation email to the affected Student.
7. THE Availability_Service SHALL store all datetimes in UTC and THE Platform SHALL display times converted to the viewing user's local timezone.

---

### Requirement 4: Lesson Booking

**User Story:** As a student, I want to select an available time slot and confirm a booking, so that I can schedule a lesson with the tutor.

#### Acceptance Criteria

1. WHILE a Student is authenticated, THE Booking_Service SHALL allow the Student to select an available Availability_Slot and initiate a booking.
2. WHEN a booking is initiated, THE Booking_Service SHALL set the Booking status to `pending_payment` and reserve the Availability_Slot for 15 minutes to prevent double-booking.
3. IF the 15-minute reservation window expires before payment is completed, THEN THE Booking_Service SHALL release the Availability_Slot back to `available` status and cancel the pending Booking.
4. WHEN a Booking transitions to `confirmed` status, THE Availability_Service SHALL update the associated Availability_Slot status to `booked`.
5. THE Booking_Service SHALL prevent a Student from booking the same Availability_Slot more than once.
6. WHEN a confirmed Booking is cancelled by a Student more than 24 hours before the Lesson start time, THE Booking_Service SHALL set the Booking status to `cancelled` and THE Payment_Service SHALL initiate a full refund via Stripe.
7. WHEN a confirmed Booking is cancelled by a Student within 24 hours of the Lesson start time, THE Booking_Service SHALL set the Booking status to `cancelled` and THE Payment_Service SHALL not issue a refund.
8. WHEN a Booking is cancelled for any reason, THE Notification_Service SHALL send a cancellation confirmation email to the Student.
9. THE Booking_Service SHALL expose a Student's booking history, returning Bookings sorted by start datetime descending.
10. THE database schema SHALL include a `tutor_id` foreign key on the Bookings table referencing the Tutors table, to support multi-tutor expansion in v2.

---

### Requirement 5: Stripe Payment

**User Story:** As a student, I want to pay for a lesson securely using my credit or debit card, so that my booking is confirmed.

#### Acceptance Criteria

1. WHEN a Student initiates a booking, THE Payment_Service SHALL create a Stripe Checkout Session for the lesson price and return the session URL to the frontend.
2. THE Platform SHALL redirect the Student to the Stripe-hosted Checkout page to complete payment.
3. WHEN Stripe sends a `checkout.session.completed` webhook event, THE Payment_Service SHALL verify the webhook signature using the Stripe webhook secret stored in an environment variable, then update the associated Booking status to `confirmed`.
4. IF the Stripe webhook signature verification fails, THEN THE Payment_Service SHALL return a 400 response and take no further action.
5. WHEN Stripe sends a `charge.refund.updated` webhook event confirming a refund, THE Payment_Service SHALL record the refund against the Booking and update the Booking status to `refunded`.
6. THE Payment_Service SHALL store the Stripe Payment Intent ID and Checkout Session ID against each Booking for reconciliation.
7. WHEN a Student is redirected back to the Platform after a successful Stripe Checkout, THE Platform SHALL display a booking confirmation page showing the Lesson date, time, and a link to the Student Dashboard.
8. WHEN a Student is redirected back to the Platform after a cancelled Stripe Checkout, THE Platform SHALL display a message indicating the payment was not completed and offer the option to retry.
9. THE Payment_Service SHALL support the lesson prices defined in the Pricing section (single session, monthly package, intensive package) as configurable values stored in the database, not hardcoded in application code.

---

### Requirement 6: Video Lesson Room

**User Story:** As a student or tutor, I want to join a video call directly within the platform, so that I can attend the lesson without installing additional software.

#### Acceptance Criteria

1. THE Platform SHALL embed a video call interface using the Daily.co or Whereby API within a dedicated Lesson page accessible only to the Student and Tutor associated with that Booking.
2. WHEN a Student navigates to the Lesson page more than 10 minutes before the scheduled start time, THE Video_Service SHALL display a waiting room message showing the time remaining until the Lesson begins.
3. WHEN the current time is within 10 minutes of the Lesson start time, THE Video_Service SHALL activate the video room embed and allow the Student to join.
4. WHEN a Lesson's scheduled end time has passed, THE Video_Service SHALL display a session-ended message and provide a link to submit a Review.
5. THE Video_Service SHALL generate a unique room URL per Booking and store it against the Booking record.
6. IF a Student attempts to access the Lesson page for a Booking that does not belong to their account, THEN THE Platform SHALL return a 403 Forbidden response.
7. THE Notification_Service SHALL send a reminder email to the Student 24 hours before the Lesson start time containing the Lesson date, time, and a direct link to the Lesson page.

---

### Requirement 7: Student–Tutor Messaging

**User Story:** As a student, I want to send messages to my tutor before and after lessons, so that I can ask questions, share materials, and follow up on lesson content.

#### Acceptance Criteria

1. THE Messaging_Service SHALL provide an inbox interface accessible to authenticated Students and the Tutor showing all message threads.
2. WHEN a Student sends a message, THE Messaging_Service SHALL store the message with sender ID, recipient ID, message body, and a UTC timestamp, and deliver it to the recipient's inbox.
3. THE Messaging_Service SHALL mark messages as `read` WHEN the recipient opens the message thread.
4. THE Platform SHALL display an unread message count badge on the navigation for authenticated users with unread messages.
5. WHEN a new message is received, THE Notification_Service SHALL send an email notification to the recipient if the recipient has not viewed the message within 5 minutes.
6. THE Messaging_Service SHALL support text messages up to 5,000 characters in length.
7. IF a Student attempts to send a message to a user who is not their assigned Tutor, THEN THE Messaging_Service SHALL return a 403 Forbidden response.
8. THE Messaging_Service SHALL return message threads paginated in batches of 50 messages, ordered by timestamp ascending.

---

### Requirement 8: Reviews and Ratings

**User Story:** As a student, I want to leave a star rating and written review after a completed lesson, so that I can share my experience and help other students make informed decisions.

#### Acceptance Criteria

1. WHEN a Lesson's status is `completed`, THE Platform SHALL present the Student with a review prompt on the Lesson page and via a link in the post-lesson email.
2. THE Review_Service SHALL accept a rating of 1 to 5 stars (integer) and an optional written comment of up to 1,000 characters.
3. WHEN a Review is submitted for a Booking that already has a Review, THE Review_Service SHALL return an error indicating a review has already been submitted for that Lesson.
4. THE Review_Service SHALL calculate the Tutor's average rating as the arithmetic mean of all submitted Review ratings, rounded to one decimal place.
5. THE Review_Service SHALL update the Tutor's average rating and total review count WHEN a new Review is submitted.
6. THE Platform SHALL display Reviews on the Tutor Profile page sorted by submission date descending.
7. IF a Student attempts to submit a Review for a Booking that does not belong to their account, THEN THE Review_Service SHALL return a 403 Forbidden response.
8. THE Admin SHALL be able to hide individual Reviews from public display via the Admin Dashboard without deleting the Review record.

---

### Requirement 9: Admin Dashboard

**User Story:** As an admin, I want a secure dashboard to manage all platform operations, so that I can oversee bookings, students, availability, and platform content without touching the database directly.

#### Acceptance Criteria

1. THE Admin Dashboard SHALL be accessible only to users with the `admin` role; WHEN a non-admin user attempts to access the Admin Dashboard, THE Auth_Service SHALL return a 403 Forbidden response.
2. THE Admin Dashboard SHALL display a summary view showing: total bookings this month, total revenue this month, upcoming lessons in the next 7 days, and total registered students.
3. THE Admin Dashboard SHALL provide a bookings management table showing all Bookings with columns for student name, lesson date/time, status, and payment amount, with the ability to filter by status and date range.
4. THE Admin Dashboard SHALL allow the Admin to manually cancel any confirmed Booking, triggering the same cancellation and notification flow defined in Requirement 4.
5. THE Admin Dashboard SHALL provide a student management table showing all registered Students with columns for name, email, registration date, and total lessons booked.
6. THE Admin Dashboard SHALL provide the availability calendar interface defined in Requirement 3.
7. THE Admin Dashboard SHALL provide a form to update the Tutor's profile fields defined in Requirement 2.
8. THE Admin Dashboard SHALL provide a review moderation interface allowing the Admin to hide or unhide individual Reviews.
9. WHEN the Admin updates any platform content or configuration, THE API SHALL validate the input and return a descriptive error if validation fails.

---

### Requirement 10: Frontend Marketing Enhancements

**User Story:** As a site visitor, I want a polished, mobile-friendly marketing site, so that I can learn about the tutor and the platform on any device.

#### Acceptance Criteria

1. THE Nav component SHALL render a hamburger menu icon on viewports narrower than 768px and hide the horizontal link list.
2. WHEN the hamburger icon is tapped, THE Nav component SHALL toggle a full-width dropdown menu displaying all navigation links.
3. WHEN a navigation link in the dropdown menu is tapped, THE Nav component SHALL close the dropdown menu.
4. THE Platform SHALL include a FAQ section on the marketing homepage displaying at least 6 frequently asked questions as expandable accordion items.
5. WHEN a FAQ accordion item is clicked, THE Platform SHALL expand that item to show the answer and collapse any other currently open item.
6. THE Footer component SHALL display links to the tutor's social media profiles and a WhatsApp contact link.
7. THE Footer component SHALL display the platform's privacy policy and terms of service links.
8. WHEN a page section enters the viewport during scrolling, THE Platform SHALL apply a fade-in or slide-up entrance animation to that section.
9. THE Platform SHALL achieve a Lighthouse performance score of 80 or above on mobile for the marketing homepage.
10. THE Platform SHALL be keyboard-navigable: all interactive elements SHALL be reachable and operable via keyboard alone.

---

### Requirement 11: API and Backend Architecture

**User Story:** As a developer, I want a well-structured FastAPI backend, so that the platform is maintainable, testable, and ready for multi-tutor expansion.

#### Acceptance Criteria

1. THE API SHALL be implemented using FastAPI and organised into routers by domain: `auth`, `users`, `tutors`, `availability`, `bookings`, `payments`, `messages`, `reviews`.
2. THE API SHALL use PostgreSQL as its primary data store, with all schema migrations managed by Alembic.
3. THE API SHALL validate all request bodies using Pydantic models and return structured JSON error responses with an `error` field and a `detail` field for all 4xx and 5xx responses.
4. THE database schema SHALL include a `tutors` table with a `user_id` foreign key, enabling the same schema to support multiple tutors in v2 without a breaking migration.
5. THE API SHALL expose a `/health` endpoint that returns a 200 response with `{"status": "ok"}` WHEN the database connection is healthy.
6. IF the database connection is unavailable, THEN THE `/health` endpoint SHALL return a 503 response with `{"status": "degraded"}`.
7. THE API SHALL enforce role-based access control on all protected endpoints using JWT claims, rejecting requests with insufficient role with a 403 response.
8. THE API SHALL be containerised using Docker and orchestrated with Docker Compose alongside the PostgreSQL database, the React frontend served by Nginx, and a reverse proxy Nginx container routing `/api` to the FastAPI service and `/` to the frontend.
9. THE API SHALL read all secrets (database URL, JWT secret, Stripe keys, email API key, video provider API key) from environment variables and SHALL NOT hardcode any secret values.
10. THE API SHALL log all unhandled exceptions with a stack trace to stdout in a structured JSON format.

---

### Requirement 12: Email Notifications

**User Story:** As a student, I want to receive timely email notifications about my bookings and lessons, so that I am always informed about upcoming events and changes.

#### Acceptance Criteria

1. THE Notification_Service SHALL send a welcome email to a Student WHEN their account is successfully created.
2. THE Notification_Service SHALL send a booking confirmation email to a Student WHEN a Booking transitions to `confirmed` status, including the Lesson date, time (in the Student's timezone), and a link to the Lesson page.
3. THE Notification_Service SHALL send a reminder email to a Student 24 hours before each confirmed Lesson, including the Lesson date, time, and a direct link to the Lesson page.
4. THE Notification_Service SHALL send a cancellation email to a Student WHEN a Booking is cancelled, stating the reason (student-initiated, admin-initiated, or payment-expired) and whether a refund has been issued.
5. THE Notification_Service SHALL send a post-lesson email to a Student WHEN a Lesson is marked `completed`, containing a link to submit a Review.
6. THE Notification_Service SHALL send all emails using Resend or SendGrid via their respective REST APIs, with the provider configured via an environment variable.
7. IF an email delivery attempt fails, THEN THE Notification_Service SHALL retry the delivery up to 3 times with exponential backoff before logging the failure and continuing without blocking the primary operation.
8. THE Notification_Service SHALL use HTML email templates that include the Fluency Tutoring branding (logo, brand colours).

---

### Requirement 13: Security and Data Protection

**User Story:** As a platform operator, I want the platform to follow security best practices, so that student data and payment information are protected.

#### Acceptance Criteria

1. THE Auth_Service SHALL hash all passwords using bcrypt with a minimum cost factor of 12 before storing them in the database.
2. THE API SHALL enforce HTTPS for all traffic in production; WHEN an HTTP request is received by the Nginx reverse proxy, THE Nginx reverse proxy SHALL redirect it to HTTPS with a 301 response.
3. THE API SHALL set the following HTTP security headers on all responses: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`.
4. THE API SHALL implement rate limiting on the authentication endpoints: IF more than 10 login or registration requests are received from the same IP address within 60 seconds, THEN THE API SHALL return a 429 Too Many Requests response for subsequent requests within that window.
5. THE Platform SHALL never transmit or store raw card numbers; all payment data SHALL be handled exclusively by Stripe.
6. THE API SHALL validate and sanitise all user-supplied input before processing or storing it to prevent SQL injection and cross-site scripting.
7. THE Auth_Service SHALL invalidate a JWT by maintaining a server-side denylist of logged-out token JTI values until the token's natural expiry.

---

### Requirement 14: Serialisation and Data Integrity

**User Story:** As a developer, I want consistent data serialisation across the API, so that the frontend and backend remain in sync and data round-trips are lossless.

#### Acceptance Criteria

1. THE API SHALL serialise all datetime values as ISO 8601 strings in UTC (e.g., `2025-07-15T14:00:00Z`) in all JSON responses.
2. THE API SHALL deserialise ISO 8601 datetime strings from request bodies into UTC-aware datetime objects before processing.
3. THE API SHALL serialise all monetary amounts as integers representing the smallest currency unit (e.g., cents for USD) in all JSON responses and requests.
4. FOR ALL valid API request payloads, serialising the response and deserialising it back SHALL produce an equivalent object (round-trip property).
5. THE API SHALL return consistent field names in snake_case for all JSON responses.
