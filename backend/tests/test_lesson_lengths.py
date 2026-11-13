"""30- and 60-minute lessons: carving lessons out of free time, joining it
back, prices, plan credits per length. Needs TEST_DATABASE_URL (PostgreSQL)."""
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from tests.test_booking_flow import (  # noqa: F401  (fixtures are used by name)
    _now,
    _tutor,
    _user,
    db,
    migrated_database,
    pytestmark,
)
from tests.test_plans_credits import _quiet


async def _free(db, tutor, start, minutes=120):
    from app.models.availability_slot import AvailabilitySlot

    slot = AvailabilitySlot(
        tutor_id=tutor.id,
        start_at=start,
        end_at=start + timedelta(minutes=minutes),
        duration_minutes=minutes,
        status="available",
    )
    db.add(slot)
    await db.flush()
    return slot


def _start(days=3):
    """A whole hour a few days ahead."""
    return (_now() + timedelta(days=days)).replace(minute=0, second=0, microsecond=0)


async def _free_times(db, tutor):
    from app.models.availability_slot import AvailabilitySlot

    rows = await db.execute(
        select(AvailabilitySlot.start_at, AvailabilitySlot.end_at)
        .where(AvailabilitySlot.tutor_id == tutor.id, AvailabilitySlot.status == "available")
        .order_by(AvailabilitySlot.start_at)
    )
    return [tuple(r) for r in rows.all()]


async def test_calendar_offers_half_hour_starts_for_each_length(db):
    from app.services import availability_service

    _, tutor = await _tutor(db)
    t = _start()
    await _free(db, tutor, t, minutes=90)

    thirty = [o.start_at for o in await availability_service.list_available_slots(db, tutor.id, 30)]
    sixty = [o.start_at for o in await availability_service.list_available_slots(db, tutor.id, 60)]
    assert thirty == [t, t + timedelta(minutes=30), t + timedelta(minutes=60)]
    assert sixty == [t, t + timedelta(minutes=30)]


async def test_30_minute_lesson_costs_six_dollars_and_leaves_the_rest_free(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    t = _start()
    free = await _free(db, tutor, t, minutes=120)

    booking = await booking_service.create_booking(
        db, student.id, free.id, "single", start_at=t + timedelta(minutes=30), minutes=30
    )
    assert booking.price_cents == 600 and booking.duration_minutes == 30
    assert (booking.start_at, booking.end_at) == (t + timedelta(minutes=30), t + timedelta(minutes=60))
    assert await _free_times(db, tutor) == [
        (t, t + timedelta(minutes=30)),
        (t + timedelta(minutes=30), t + timedelta(minutes=60)),  # held while paying
        (t + timedelta(minutes=60), t + timedelta(minutes=120)),
    ]


async def test_cancelling_joins_the_free_time_back_together(db):
    from app.models.user import User
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    t = _start()
    free = await _free(db, tutor, t, minutes=60)

    with _quiet():
        trial = await booking_service.create_booking(db, student.id, free.id, "trial")
    assert trial.duration_minutes == 60
    admin = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()
    with _quiet():
        await booking_service.cancel_booking(db, trial.id, admin)
    assert await _free_times(db, tutor) == [(t, t + timedelta(minutes=60))]


async def test_two_half_hours_freed_again_can_be_booked_as_one_hour(db):
    from app.services import availability_service, booking_service

    _, tutor = await _tutor(db)
    a, b = await _user(db), await _user(db)
    t = _start()
    free = await _free(db, tutor, t, minutes=60)

    first = await booking_service.create_booking(db, a.id, free.id, "single", minutes=30)
    rest = [o for o in await availability_service.list_available_slots(db, tutor.id, 30) if o.start_at == t + timedelta(minutes=30)][0]
    second = await booking_service.create_booking(db, b.id, rest.id, "single", start_at=rest.start_at, minutes=30)

    # nobody paid: both holds run out
    from app.models.booking import Booking

    for bk in (first, second):
        row = await db.get(Booking, bk.id)
        row.reserved_until = _now() - timedelta(minutes=1)
    await db.flush()
    assert await booking_service.expire_pending_bookings(db) == 2
    sixty = await availability_service.list_available_slots(db, tutor.id, 60)
    assert [o.start_at for o in sixty] == [t]


async def test_trial_must_be_60_minutes(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    free = await _free(db, tutor, _start(), minutes=60)
    with pytest.raises(HTTPException) as exc:
        await booking_service.create_booking(db, student.id, free.id, "trial", minutes=30)
    assert exc.value.status_code == 400


async def test_lesson_must_fit_on_the_half_hour_grid(db):
    from app.services import booking_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    t = _start()
    free = await _free(db, tutor, t, minutes=60)
    for start, minutes in ((t + timedelta(minutes=15), 30), (t + timedelta(minutes=30), 60)):
        with pytest.raises(HTTPException) as exc:
            await booking_service.create_booking(db, student.id, free.id, "single", start_at=start, minutes=minutes)
        assert exc.value.status_code == 409


async def test_plan_credits_only_book_lessons_of_their_length(db):
    from app.services import booking_service, credit_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    t = _start()
    await credit_service.grant_credits(
        db, student_id=student.id, total=4, expires_at=_now() + timedelta(days=30), source="package", lesson_minutes=30
    )
    summary = await credit_service.credit_summary(db, student.id)
    assert summary["credits_by_length"] == {"30": 4, "60": 0} and summary["credits_remaining"] == 4

    free = await _free(db, tutor, t, minutes=120)
    with pytest.raises(HTTPException) as exc:
        await booking_service.create_booking(db, student.id, free.id, "plan", minutes=60)
    assert exc.value.detail["error"] == "NO_CREDITS"
    with _quiet():
        booked = await booking_service.create_booking(db, student.id, free.id, "plan", minutes=30)
    assert booked.status == "confirmed" and booked.duration_minutes == 30


async def test_30_minute_package_gives_30_minute_lessons(db):
    from app.models.credit_grant import CreditGrant
    from app.services import paystack_service

    student = await _user(db)
    meta = {"kind": "package", "student_id": str(student.id), "product_key": "plan_3x_30"}
    await paystack_service.process_successful_charge(db, {"status": "success", "reference": "fg_pk_30", "metadata": meta})
    grant = (await db.execute(select(CreditGrant).where(CreditGrant.student_id == student.id))).scalar_one()
    assert (grant.total, grant.lesson_minutes, grant.amount_cents) == (12, 30, 6500)


async def test_reschedule_keeps_the_lesson_length_and_frees_the_old_time(db):
    from app.models.user import User
    from app.services import booking_service, credit_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    t = _start()
    await credit_service.grant_credits(
        db, student_id=student.id, total=2, expires_at=_now() + timedelta(days=30), source="package", lesson_minutes=30
    )
    free = await _free(db, tutor, t, minutes=60)
    with _quiet():
        lesson = await booking_service.create_booking(db, student.id, free.id, "plan", minutes=30)
        later = await _free(db, tutor, t + timedelta(days=1), minutes=60)
        moved = await booking_service.reschedule_booking(
            db, lesson.id, later.id, student, start_at=later.start_at + timedelta(minutes=30)
        )
    assert moved.duration_minutes == 30
    assert moved.start_at == later.start_at + timedelta(minutes=30)
    free_now = await _free_times(db, tutor)
    assert (t, t + timedelta(minutes=60)) in free_now  # old time joined back into one hour
    assert (later.start_at, later.start_at + timedelta(minutes=30)) in free_now


async def test_late_payment_gets_its_time_back_after_it_was_joined(db):
    from app.models.booking import Booking
    from app.services import availability_service, booking_service, paystack_service

    _, tutor = await _tutor(db)
    student = await _user(db)
    t = _start()
    free = await _free(db, tutor, t, minutes=60)
    created = await booking_service.create_booking(db, student.id, free.id, "single", minutes=30)
    row = await db.get(Booking, created.id)
    row.payment_reference = "fg_bk_late"
    row.reserved_until = _now() - timedelta(minutes=1)
    await db.flush()
    await booking_service.expire_pending_bookings(db)  # time joined back into 10:00-11:00

    with _quiet():
        result = await paystack_service.process_successful_charge(
            db, {"status": "success", "reference": "fg_bk_late", "metadata": {"kind": "booking", "booking_id": str(row.id)}}
        )
    assert result == "booking_confirmed"
    await db.refresh(row)
    assert row.status == "confirmed"
    remaining = [o.start_at for o in await availability_service.list_available_slots(db, tutor.id, 30)]
    assert remaining == [t + timedelta(minutes=30)]
