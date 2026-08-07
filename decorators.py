from functools import wraps
from flask import abort
from flask_login import current_user
from models import ROLE_ADMIN, ROLE_STAFF, ROLE_TREKKER


def role_required(*roles):
    """Generic decorator: allow only given roles."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def admin_required(view_func):
    return role_required(ROLE_ADMIN)(view_func)


def staff_required(view_func):
    return role_required(ROLE_STAFF)(view_func)


def trekker_required(view_func):
    return role_required(ROLE_TREKKER)(view_func)
