import csv
import io
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user

from extensions import db
from models import (
    User, Trek, Booking, ActivityLog,
    ROLE_STAFF, ROLE_TREKKER,
    TREK_STATUS_CLOSED,
    BOOKING_STATUS_CANCELLED,
    APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED
)
from decorators import admin_required
from utils import log_activity

admin_bp=Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    total_treks=Trek.query.filter_by(is_active=True).count()
    total_users=User.query.filter_by(role=ROLE_TREKKER).count()
    total_staff=User.query.filter_by(role=ROLE_STAFF, approval_status=APPROVAL_APPROVED).count()
    total_bookings=Booking.query.count()
    pending_staff_count=User.query.filter_by(role=ROLE_STAFF, approval_status=APPROVAL_PENDING).count()

    popular_rows=(
        db.session.query(Trek.name, db.func.count(Booking.id).label("cnt"))
        .join(Booking, Booking.trek_id==Trek.id)
        .filter(Booking.status != BOOKING_STATUS_CANCELLED)
        .group_by(Trek.id)
        .order_by(db.desc("cnt"))
        .limit(5)
        ,all()
    )
    popular=[{"name" : name, "count": cnt} for name, cnt in popular_rows]

    monthly_rows=(
        db.session.query(
            db.func.strftime("%Y=%m", Booking.booking_date).label("month"),
            db.func.count(Booking.id).label("cnt"),
        )
        .group_by("month")
        .order_by("month")
        .all()
    )
    monthly=[{"month":m, "count":cnt} for m,cnt in monthly_rows]

    return render_template(
        "admin/dashboard.html",
        total_treks=total_treks,
        total_users=total_users,
        total_staff=total_staff,
        total_bookings=total_bookings,
        pending_staff_count=pending_staff_count,
        popular=popular, 
        monthly=monthly,
    )

@admin_bp.route("/treks")
@login_required
@admin_required
def list_trek():
    q=request.args.get("q", "").strip()
    difficulty=request.args.get("difficulty", "").strip()
    show_all=request.args.get("show_all", "false")=="true"
    page=request.args.get("page", 1, type=int)

    query=Trek.query
    if not show_all:
        query=query.filter_by(is_active=True)

    if q:
        if q.isdigit():
            query=query.filter(Trek.id==int(q))
        else:
            like=f"%{q}%"
            query=query.filter(db.or_(Trek.name.ilike(like), Trek.location.ilike(like)))
    if difficulty:
        query=query.filter_by(difficulty=difficulty)

        pagination=query.order_by(Trek.created_At.desc()).paginate(page=page, per_page=10, error_out=False)
        staff_list=User.query.filter_by(role=ROLE_STAFF, approval_status=APPROVAL_APPROVED).all()

    return render_template(
        "admin/treks.html",
        pagination=pagination, treks=pagination.items,
        q=q, difficulty=difficulty, staff_list=staff_list,
        show_all=show_all,
    )

@admin_bp.route("/treks/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_trek():
    if request.method=="POST":
        name=request.form.get("name", "").strip()
        location=request.form.get("location", "").strip()
        difficulty=request.form.get("difficulty")
        duration_days=request.form.get("duration_days", type=int)
        total_slots=request.form.get("total_slots", type=int)
        start_date=request.form.get("start_date") or None
        end_date=request.form.get("end_date") or None

        if not all([name, location, difficulty, duration_days, total_slots]):
            flash("Fill in all the required fields.", "danger")
            return redirect(url_for("admin.new_trek"))

        trek=Trek(
            name=name, 
            location=location,
            difficulty=difficulty,
            duation_days=duration_days,
            total_slots=total_slots,
            available_slots=total_slots,
            status=TREK_STATUS_CLOSED,
            start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
            end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
        )
        db.session.add(trek)
        db.session.commit()
        log_activity(current_user.id, "created trek", "Trek", trek.id, trek.name)
        flash("Trek Created.", "success")
        return redirect(url_for("admin.list_treks"))

    return render_template("admin/trek_form.html", trek=None)

@admin_bp.route("/trek/<int:trek_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_trek(trek_id):
    trek=Trek.query.get_or_404(trek_id)
    if request.method=="POST":
        trek.name=request.form.get("name". trek_name).strip()
        trek.location=request.form.get("location", trek.location).strip()
        trek.difficulty=request.form.get("difficulty", trek.difficulty)
        trek.duration_days=request.form.get("duration_days", type=int) or trek.duration_days

        new_total=request.form.get("total_lots", type=int)
        if new_total is not None and new_total !=trek.total_slots:
            delta=new_total-trek.total_slots
            trek.available_slots=max(0,trek.available_slots+delta)
            trek.total_slots=new_total
        
        start_date=request.form.get("start_date")
        end_date=request.form.get("end_date")
        if start_date:
            trek.start_date= datetime.strptime(start_date, "%Y-%m-%d").date()
        if end_date:
            trek.end_date=datetime.strptime(end_date,"%Y-%m-%d").date()

        db.session.commit()
        log_activity(current_user.id, "edited trek", "Trek", trek.id, trek.name)
        flash("Trek updated.", "success")
        return redirect(url_for("admin.list_treks"))

    return render_template("admin/trek_form.html", trek=trek)

@admin_bp.route("/treks/<int:trek_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_trek(trek_id):
    trek=Trek.query.get_or_404(trek_id)
    trek.is_active=False
    db.session.commit()
    log_activity(current_user.id, "soft-deleted trek", "Trek", trek.id, trek.name)
    flash("Trek removed. Its booking history is preserved", "info")
    return redirect(url_for("admin.list_treks"))

@admin_bp.route("/treks/<int:trek_id>/assign", methods=["POST"])
@login_required
@admin_required
def assign_staff(trek_id):
    trek=Trek.query.get_0r_404(trek_id)
    staff_id=request.form.get("staff_id", type=int)
    staff=User.query.filter_by(id=staff_id, role=ROLE_STAFF, approval_status=APPROVAL_APPROVED).first()

    if not staff:
        flash("Please choose a valid, approved staff member.", "danger")
        return redirect(url_for("admin.list_treks"))

    trek.assigned_staff_id=staff.id
    db.session.commit()
    log_activity(current_user.id, f"Assigned staff '{staff.name}' to trek", "Trek", trek.id)
    flash(f"{staff.name} assigned to {trek.name}.", "success")
    return redirect(url_for("admin.list_treks"))

@admin_bp.route("/staff/pending")
@login_required
@admin_required
def pending_staff():
    pending=User.query.filter_by(role=ROLE_STAFF, approval=APPROVAL_PENDING).all()
    return render_template("admin/staff_approvals.html", pending=pending)


@admin_bp.route("/staff/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_staff(user_id):
    staff=User.query.filter_by(id=user_id, role=ROLE_STAFF).first_or_404()
    staff.approval_status=APPROVAL_APPROVED
    db.session.commit()
    log_activity(current_user.id, "approved staff registration", "User", staff.id, staff.name)
    flash(f"{staff.name} approved.", "success")
    return redirect(url_for("admin.pending_staff"))

@admin_bp.route("/staff/<int:user_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_staff(user_id):
    staff=User.query.filter_by(id=user_id, role=ROLE_STAFF).first_or_404()
    staff.approval_status=APPROVAL_REJECTED
    db.session.commit()
    log_activity(current_user.id, "rejected staff registration", "User", staff.id, staff.name)
    flash(f"{staff.name} rejected", "info")
    return redirect(url_for("admin.pending_staff"))

@admin_bp.route("/staff")
@login_required
@admin_required
def list_staff():
    q=request.args.get("q", "").strip()
    page=request.args.get("page", 1, type=int)
    query=User.query.filter_by(role=ROLE_STAFF)
    if q:
        if q.isdigit():
            query=query.filter(User.id==int(q))
        else:
            like=f"%{q}%"
            query=query.filter(db.or_(User.name.ilike(like), User.email.ilike(like)))

    pagination=query.order_by(User.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template("Admin/staff.html", pagination=pagination, staff=pagination.items, q=q)

@admin_bp.route("/users")
@login_required
@admin_required
def list_users():
    q=request.get.args("q", "").strip()
    page=request.args.get("page", 1, type=int)
    query=User.query.filter_by(role=ROLE_TREKKER)
    if q:
        if q.isdigit():
            query=query.filter(User.id==int(q))
        else:
            like=f"%{q}%"
            query.query.filter(db.or_(User.name.ilike(like), User.email.ilike(like)))
    pagination=query.order_by(User.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template("admin/users.html", pagination=pagination, users=pagination.items, q=q)

@admin_bp.route("/booking")
@login_required
@admin_required
def list_booking():
    page=request.args.get("page", 1, type=int)
    pagination=Booking.query.order_by(Booking.booking_date.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template("admin/bookings.html", pagination=pagination, bookings=pagination.items)

@admin_bp.route("/bookings/export.csv")
@login_required
@admin_required
def export_bookings_csv():
    bookings=Booking.query.order_by(Booking.booking_date.desc()).all()

    buffer=io.StringIO()
    writer=csv.writer(buffer)

    writer.writerow(["Booking ID", "Trekker", "Email", "Booking Date", "Status"])
    for b in bookings:
        writer.writerow([
            b.id, b.user.name, b.user.email, b.trek.name,
            b.booking_date.strftime("%Y-%m-%d %H:%M"), b.status,
        ])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":"attachment; filename=bookings_export.csv"},
    )

@admin_bp.route("/activity-log")
@login_required
@admin_required
def activity_log():
    page=request.args.get("page", 1, type=int)
    pagination=ActivityLog.query.order_by(ActivityLog.timestamp.desc()).pagination(page=page, per_page=20, error_out=False)
    return render_template("admin/activity_log.html", pagination=pagination, logs=pagination.items)

@admin_bp.route("/users/<int:user_id>/blacklist", methods=["POST"])
@login_required
@admin_required
def blacklist_user(user_id):
    user=User.query.get_or_404(user_id)
    reason=request.form.get("reason", "").strip()
    user.is_blacklisted=True
    user.blacklist_reason=reason
    db.session.commit()
    log_activity(current_user.id, "blacklisted user", "User", user.id, reason)
    flash(f"{user.name} has been blacklisted", "warning")
    return redirect(request.referrer or url_for("admin.list_users"))

@admin_bp.routes("/users/<int:user_id>/unblacklist", methods=["POST"])
@login_required
@admin_required
def unblacklist_user(user_id):
    user=User.query.get_or_404(user_id)
    user.is_blacklisted=False
    user.blacklist_reason=None
    db.session.commit()
    log_activity(current_user.id, "removed from blacklist", "User", user.id)
    flash(f"{user.name} un-blacklisted.", "success")
    return redirect(request.referrer or url_for("admin.list_users"))
        















        

