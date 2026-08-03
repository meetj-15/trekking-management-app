from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False) 
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='trekker')
    is_blacklisted = db.Column(db.Boolean, default=False)
    is_approved=db.Column(db.Boolean, default=False)

    bookings = db.relationship('Booking', backref='user', lazy=True, cascade="all, delete-orphan")

    assigned_treks = db.relationship('Trek', backref='staff_member', lazy=True, foreign_keys='Trek.assigned_staff_id')

class Trek(db.Model):
    __tablename__ = 'treks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(50), nullable=False)
    duration = db.Column(db.Integer, nullable=False) 
    available_slots = db.Column(db.Integer, nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    status = db.Column(db.String(50), nullable=False, default='Pending') 
    
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)

    bookings = db.relationship('Booking', backref='trek', lazy=True, cascade="all, delete-orphan")

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey('treks.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='Confirmed')