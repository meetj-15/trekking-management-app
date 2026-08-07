import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Config:
    _secret = os.environ.get("SECRET_KEY")
    # In production (DEBUG not set) raise an error rather than use a weak fallback.
    if not _secret and not os.environ.get("FLASK_DEBUG", "0") == "1":
        _secret = "dev-only-" + secrets.token_hex(16)  # safe for local dev
    SECRET_KEY = _secret or secrets.token_hex(32)

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, "trekking.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ITEMS_PER_PAGE = 10
