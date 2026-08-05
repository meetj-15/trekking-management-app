import os

BASE_DIR=os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR=os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

class Config:
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev12345")
    SQLALCHEMY_DATABASE_URI="sqlite:///"+os.path.join(INSTANCE_DIR, "trekking.db")
    SQLALCHEMY_TRACK_MODIFICATIONS=False

    ITEMS_PER_PAGE=10