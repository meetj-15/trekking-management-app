from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import (
    User,
    ROLE_ADMIN,
    ROLE_STAFF,
    ROLE_TREKKER,
    APPROVAL_PENDING,
    APPROVAL_APPROVED,
)
from utils import log_activity

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.post_login_redirect"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role")
        contact = request.form.get("contact", "").strip()

        if role not in (ROLE_STAFF, ROLE_TREKKER):
            flash("Invalid role selected.", "danger")
            return redirect(url_for("auth.register"))

        if not name or not email or not password:
            flash("Name, email and password are required.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("auth.register"))

        user = User(name=name, email=email, role=role, contact=contact)
        user.set_password(password)
        user.approval_status = (
            APPROVAL_PENDING if role == ROLE_STAFF else APPROVAL_APPROVED
        )

        db.session.add(user)
        db.session.commit()
        log_activity(user.id, f"{role} account registered", "User", user.id)

        if role == ROLE_STAFF:
            flash("Registration submitted. Log in once admin approves.", "info")
        else:
            flash("Registration successful, log in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.post_login_redirect"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))

        if user.is_blacklisted:
            flash("This account is blacklisted. Contact admin.", "danger")
            return redirect(url_for("auth.login"))

        if user.role == ROLE_STAFF and user.approval_status != APPROVAL_APPROVED:
            flash("Your staff account is pending admin approval.", "warning")
            return redirect(url_for("auth.login"))

        login_user(user)
        log_activity(user.id, "logged in")
        return redirect(url_for("auth.post_login_redirect"))

    return render_template("auth/login.html")


@auth_bp.route("/post-login-redirect")
@login_required
def post_login_redirect():
    if current_user.role == ROLE_ADMIN:
        return redirect(url_for("admin.dashboard"))
    if current_user.role == ROLE_STAFF:
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("trekker.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    log_activity(current_user.id, "logged out")
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("auth.login"))
