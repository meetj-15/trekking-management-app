from extensions import db
from models import ActivityLog, Booking, Trek, BOOKING_STATUS_WAITLISTED, BOOKING_STATUS_BOOKED
from sqlalchemy import update


def log_activity(actor_id, action, target_type=None, target_id=None, details=None):
    """Write one row to the audit trail. Called after every state-changing action"""
    entry = ActivityLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.session.add(entry)
    db.session.commit()

def promote_waitlist(trek_id, num_slots):
    """Promotes up to num_slots users from the waitlist for a given trek."""
    if num_slots <= 0:
        return
        
    waitlisted_bookings = (
        Booking.query.filter_by(trek_id=trek_id, status=BOOKING_STATUS_WAITLISTED)
        .order_by(Booking.waitlist_position)
        .limit(num_slots)
        .all()
    )
    
    for booking in waitlisted_bookings:
        result = db.session.execute(
            update(Trek)
            .where(Trek.id == trek_id, Trek.available_slots > 0)
            .values(available_slots=Trek.available_slots - 1)
        )
        if result.rowcount == 1:
            booking.status = BOOKING_STATUS_BOOKED
            booking.waitlist_position = None
            log_activity(
                booking.user_id, "auto-promoted from waitlist", "Trek", trek_id
            )
        else:
            break
