from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

ROLE_ADMIN="admin"
ROLE_STAFF="staff"
ROLE_TREKKER="trekker"

TREK_STATUS_CLOSED="Closed"
TREK_STATUS_OPEN="Open"
TREK_STATUS_STARTED="Started"
TREK_STATUS_COMPLETED="Completed"

BOOKING_STATUS_BOOKED="Booked"
BOOKING_STATUS_WAITLISTED="Waitlisted"
BOOKING_STATUS_CANCELLED="Cancelled"
BOOKING_STATUS_COMPLETED="Completed"

APPROVAL_PENDING="Pending"
APPROVAL_APPROVED="Approved"
APPROVAL_REJECTED="Rejected"

class User(UserMixin, db.Model):
    __tablename__="users"
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(120), nullable=False)
    email=db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash=db.Column(db.String(255), nullable=False)
    role=db.Column(db.String(20), nullable=False)
    contact=db.Column(db.String(50))

    is_blacklisted=db.Column(db.Boolean, default=False, nullable=False)
    blacklist_reason=db.Column(db.String(255))

    approval_status=db.Column(db.String(20), default=APPROVAL_APPROVED, nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

    treks_assigned=db.relationship(
        "Trek", backref="assigned_staff", foreign_key="Trek.assigned_staff_id"
    )
    bookings=db.relationship("Booking", backref="user", foreign_key="Booking.user_id")
    reviews=db.relationship("Review", backref="user", foreign_key="Review.user_id")

    def set_password(self, password):
        self.password_hash=generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return not self.is_blacklisted

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"

class Trek(db.Model):
    __tablename__="treks"
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(150), nullable=False)
    location=db.Column(db.String(150), nullable=False)
    difficulty=db.Column(db.String(20), nullable=False)
    duration_days=db.Column(db.Integer, nullable=False)
    assigned_staff_id=db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status=db.Column(db.String(20), nullable=False, default=TREK_STATUS_CLOSED)
    is_active=db.Column(db.Boolean, default=True, nullable=False)
    start_date=db.Column(db.Date, nullable=True)
    end_date=db.Column(db.Date, nullable=True)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)
    bookings=db.relationship("Booking", backref="trek", foreign_keys="Booking.trek_id")
    reviews=db.relationship("Review", backref="trek", foreign_keys="Review.trek_id")

    @property
    def average_rating(self):
        if not self.reviews:
            return None
        return round(sum(r.rating for r in self.reviews)/len(self.reviews), 1)
    
    def __repr__(self):
        return f"<Trek {self.name}>"

class Booking(db.Model):
    __tablename__="bookings"
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    trek_id=db.Column(db.Integer, db.ForeignKey("treks.id"), nullable=False)
    booking_date=db.Column(db.DateTime, default=datetime.utcnow)
    status=db.Column(db.String(20), nullable=False, default=BOOKING_STATUS_BOOKED)
    waitlist_position=db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"<Booking user={self.user_id} trek={self.trek_id} status={self.status}>"

class Review(db.Model):
    __tablename__="reviews"
    id=db.Column(db.Ineger, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    trek_id=db.Column(db.Integer, db.ForeignKey("treks.id"), nullable=False)
    rating=db.Column(db.Integer, nullable=False)
    comment=db.Column(db.String(500))
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class ActivityLog(db.Model):
    __tablename__="activity_logs"
    id=db.Column(db.Integer, primary_key=True)
    actor_id=db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action=db.Column(db.String(255), nullable=False)
    target_type=db.Column(db.String(50))
    target_id=db.Column(db.Integer)
    details=db.Column(db.String(500))
    timestap=db.Column(db.DateTime, default=datetime.utcnow)
    actor=db.relationship("User", foreign_key=[actor_id])


