from functools import wraps
from flask import abort
from flask_login import current_user

def role_required(*roles):
    """Generic dcorator: allow only given rols."""

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
    return role_required("admin")(view_func)

def staff_required(view_func):
    return role_required("staff")(view_func)

def trekker_required(view_func):
    return role_required("trekker")(view_func)