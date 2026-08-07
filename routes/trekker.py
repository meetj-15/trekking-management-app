from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import update
from extensions import db
from models import (
    Trek,
    Booking,
    Review,
    TREK_STATUS_OPEN,
    BOOKING_STATUS_BOOKED,
    BOOKING_STATUS_WAITLISTED,
    BOOKING_STATUS_CANCELLED,
    BOOKING_STATUS_COMPLETED,
)
from decorators import trekker_required
from utils import log_activity

trekker_bp = Blueprint("trekker", __name__, url_prefix="/trekker")


@trekker_bp.route("/dashboard")
@login_required
@trekker_required
def dashboard():
    q = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    page = request.args.get("page", 1, type=int)

    query = Trek.query.filter_by(is_active=True, status=TREK_STATUS_OPEN)
    if q:
        query = query.filter(Trek.name.ilike(f"%{q}%"))
    if location:
        query = query.filter(Trek.location.ilike(f"%{location}%"))
    if difficulty:
        query = query.filter_by(difficulty=difficulty)

    pagination = query.order_by(Trek.created_at.desc()).paginate(
        page=page, per_page=9, error_out=False
    )

    my_active_trek_ids = {
        b.trek_id
        for b in Booking.query.filter_by(user_id=current_user.id).filter(
            Booking.status.in_([BOOKING_STATUS_BOOKED, BOOKING_STATUS_WAITLISTED])
        )
    }

    return render_template(
        "trekker/dashboard.html",
        pagination=pagination,
        treks=pagination.items,
        q=q,
        location=location,
        difficulty=difficulty,
        my_active_trek_ids=my_active_trek_ids,
    )


@trekker_bp.route("/treks/<int:trek_id>/book", methods=["POST"])
@login_required
@trekker_required
def book_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    if not trek.is_active or trek.status != TREK_STATUS_OPEN:
        flash("This trek isn't open for booking right now.", "danger")
        return redirect(url_for("trekker.dashboard"))

    already = (
        Booking.query.filter_by(user_id=current_user.id, trek_id=trek.id)
        .filter(Booking.status.in_([BOOKING_STATUS_BOOKED, BOOKING_STATUS_WAITLISTED]))
        .first()
    )
    if already:
        flash(
            "You already have an active booking or waitlist spot for this trek.",
            "warning",
        )
        return redirect(url_for("trekker.dashboard"))

    result = db.session.execute(
        update(Trek)
        .where(Trek.id == trek.id, Trek.available_slots > 0)
        .values(available_slots=Trek.available_slots - 1)
    )

    if result.rowcount == 1:
        booking = Booking(
            user_id=current_user.id, trek_id=trek.id, status=BOOKING_STATUS_BOOKED
        )
        db.session.add(booking)
        db.session.commit()
        log_activity(current_user.id, "booked trek", "Trek", trek.id)
        flash(f"Booking confirmed for {trek.name}!", "success")
    else:
        db.session.rollback()
        last_position = (
            db.session.query(db.func.max(Booking.waitlist_position))
            .filter_by(trek_id=trek.id, status=BOOKING_STATUS_WAITLISTED)
            .scalar()
            or 0
        )
        booking = Booking(
            user_id=current_user.id,
            trek_id=trek.id,
            status=BOOKING_STATUS_WAITLISTED,
            waitlist_position=last_position + 1,
        )
        db.session.add(booking)
        db.session.commit()
        log_activity(current_user.id, "joined waitlist", "Trek", trek.id)
        flash(
            f"{trek.name} is full — you've been waitlisted (position {last_position + 1}).",
            "info",
        )

    return redirect(url_for("trekker.dashboard"))


@trekker_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
@trekker_required
def cancel_booking(booking_id):
    booking = Booking.query.filter_by(
        id=booking_id, user_id=current_user.id
    ).first_or_404()

    if booking.status not in (BOOKING_STATUS_BOOKED, BOOKING_STATUS_WAITLISTED):
        flash("This booking can no longer be cancelled.", "warning")
        return redirect(url_for("trekker.my_bookings"))

    was_booked = booking.status == BOOKING_STATUS_BOOKED
    booking.status = BOOKING_STATUS_CANCELLED
    trek = booking.trek

    if was_booked:
        trek.available_slots += 1
        db.session.commit()

        next_in_line = (
            Booking.query.filter_by(trek_id=trek.id, status=BOOKING_STATUS_WAITLISTED)
            .order_by(Booking.waitlist_position)
            .first()
        )
        if next_in_line:
            result = db.session.execute(
                update(Trek)
                .where(Trek.id == trek.id, Trek.available_slots > 0)
                .values(available_slots=Trek.available_slots - 1)
            )
            if result.rowcount == 1:
                next_in_line.status = BOOKING_STATUS_BOOKED
                next_in_line.waitlist_position = None
                db.session.commit()
                log_activity(
                    next_in_line.user_id, "auto-promoted from waitlist", "Trek", trek.id
                )
    else:
        db.session.commit()

    log_activity(current_user.id, "cancelled booking", "Booking", booking.id)
    flash("Booking cancelled.", "info")
    return redirect(url_for("trekker.my_bookings"))


@trekker_bp.route("/bookings")
@login_required
@trekker_required
def my_bookings():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.booking_date.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    reviewed_trek_ids = {
        r.trek_id for r in Review.query.filter_by(user_id=current_user.id)
    }
    return render_template(
        "trekker/bookings.html",
        pagination=pagination,
        bookings=pagination.items,
        reviewed_trek_ids=reviewed_trek_ids,
    )


@trekker_bp.route("/treks/<int:trek_id>/review", methods=["POST"])
@login_required
@trekker_required
def add_review(trek_id):
    completed = Booking.query.filter_by(
        user_id=current_user.id, trek_id=trek_id, status=BOOKING_STATUS_COMPLETED
    ).first()
    if not completed:
        flash("You can only review treks you've completed.", "danger")
        return redirect(url_for("trekker.my_bookings"))

    if Review.query.filter_by(user_id=current_user.id, trek_id=trek_id).first():
        flash("You've already reviewed this trek.", "warning")
        return redirect(url_for("trekker.my_bookings"))

    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip()
    if not rating or rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "danger")
        return redirect(url_for("trekker.my_bookings"))

    db.session.add(
        Review(user_id=current_user.id, trek_id=trek_id, rating=rating, comment=comment)
    )
    db.session.commit()
    log_activity(current_user.id, "left a review", "Trek", trek_id)
    flash("Thanks for your review!", "success")
    return redirect(url_for("trekker.my_bookings"))


@trekker_bp.route("/profile", methods=["GET", "POST"])
@login_required
@trekker_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name).strip()
        current_user.contact = request.form.get("contact", current_user.contact).strip()
        new_password = request.form.get("password", "").strip()
        if new_password:
            current_user.set_password(new_password)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("trekker.profile"))

    return render_template("trekker/profile.html")
