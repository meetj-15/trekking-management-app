from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import Trek, User, Booking, ROLE_ADMIN
from decorators import admin_required
api_bp = Blueprint("api", __name__, url_prefix="/api")

def trek_to_dict(t):
    return {
        "id": t.id,
        "name": t.name,
        "location": t.location,
        "difficulty": t.difficulty,
        "duration_days": t.duration_days,
        "total_slots": t.total_slots,
        "available_slots": t.available_slots,
        "status": t.status,
        "assigned_staff_id": t.assigned_staff_id,
        "start_date": t.start_date.isoformat() if t.start_date else None,
        "end_date": t.end_date.isoformat() if t.end_date else None,
    }

def user_to_dict(u):
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "is_blacklisted": u.is_blacklisted,
        "approval_status": u.approval_status,
    }

def booking_to_dict(b):
    return {
        "id": b.id,
        "user_id": b.user_id,
        "trek_id": b.trek_id,
        "status": b.status,
        "booking_date": b.booking_date.isoformat(),
    }

@api_bp.route("/treks", methods=["GET"])
def api_list_treks():
    treks = Trek.query.filter_by(is_active=True).all()
    return jsonify([trek_to_dict(t) for t in treks])

@api_bp.route("/treks/<int:trek_id>", methods=["GET"])
def api_get_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    return jsonify(trek_to_dict(trek))

@api_bp.route("/users", methods=["GET"])
@login_required
@admin_required
def api_list_users():
    return jsonify([user_to_dict(u) for u in User.query.all()])

@api_bp.route("/bookings", methods=["GET"])
@login_required
def api_list_bookings():
    if current_user.role == ROLE_ADMIN:
        bookings = Booking.query.all()
    else:
        bookings = Booking.query.filter_by(user_id=current_user.id).all()
    return jsonify([booking_to_dict(b) for b in bookings])