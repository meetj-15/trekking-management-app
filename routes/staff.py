from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import (
    Trek, Booking,
    TREK_STATUS_CLOSED, TREK_STATUS_OPEN, TREK_STATUS_STARTED, TREK_STATUS_COMPLETED, BOOKING_STATUS_BOOKED, BOOKING_STATUS_WAITLISTED, BOOKING_STATUS_COMPLETED,
)
from decorators import staff_required
from utils import log_activity

staff_bp=Blueprint("staff", __name__, url_prefix="/staff")

def _owned_trek_or_403(trek_id):
    trek=Trek.query.get_or_404(trek_id)
    if trek.assigned_staff_id != current_user.id:
        abort(403)
    return trek

@staff_bp.route("/dashboard")
@login_required
@staff_required
def trek_detail(trek_id):
    trek=_owned_trek_or_403(trek_id)
    participants=(
        Booking.query.filter_by(trek_id=trek.id)
        .filter(Booking.status.in_([BOOKING_STATUS_BOOKED, BOOKING_STATUS_COMPLETED]))
        .order_by(Booking.booking_date)
        .all()
    )
    waitlisted=(
        Booking.query.filter_by(trek_id=trek.id, status=BOOKING_STATUS_WAITLISTED)
        .order_by(Booking.waitlist_position)
        .all()
    )
    return render_template("staff/trek_detail.html", trek=trek, participants=participants, waitlisted=waitlisted)

@staff_bp.route("/treks/<int:trek_id>/slots", methods=["POST"])
@login_required
@staff_required
def update_slots(trek_id):
    trek=_owned_trek_or_403(trek_id)
    available=request.form.get("available_slots", type=int)

    if available is None or available<0 or available>trek.total_slots:
        flash("Available slots must be b/w 0 and the total slots count.", "danger")
        return redirect(url_for("staff.trek_detail", trek_id=trek.id))

    trek.available_slots=available
    db.session.commit()
    log_activity(current_user.id, "updated available slots", "Trek", trek.id, str(available))
    flash("Available slots updted.", "success")
    return redirect(url_for("staff.trek_detail", trek_id=trek.id))

@staff_bp.route("/trek/<int:trek_id/status", methods=["POST"])
@login_required
@staff_required
def update_status(trek_id):
    trek=_owned_trek_or_403(trek_id)
    new_status=request.form.get("status")
    valid_next={
        TREK_STATUS_CLOSED: [TREK_STATUS_OPEN],
        TREK_STATUS_OPEN: [TREK_STATUS_CLOSED, TREK_STATUS_STARTED],
        TREK_STATUS_STARTED: [TREK_STATUS_COMPLETED],
        TREK_STATUS_COMPLETED: [],
    }
    if new_status not in valid_next.get(trek.status, []):
        flash(f"Cant move a trek from '{trek.status}' to '{new_status}'.", "danger")
        return redirect(url_for("staff.trek_detail", trek_id=trek.id))

    trek.status=new_status
    if new_status == TREK_STATUS_COMPLETED:
        Booking.query.filter_by(trek_id=trek.id, status=BOOKING_STATUS_BOOKED).update({"status":BOOKING_STATUS_COMPLETED})
    
    db.session.commit()
    log_activity(current_user.id, f"Changed trek status to {new_status}", "Trek", trek.id)
    flash(f"Trek marked as {new_status}.", "success")
    return redirect(url_for("staff.trek_detail", trek_id=trek.id))
    
