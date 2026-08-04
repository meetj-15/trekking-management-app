from flask import Flask, render_template
from flask_login import current_user
from config import Config
from extensions import db, login_manager

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.staff import staff_bp
    from routes.trekker import trekker_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(trekker_bp)
    app.register_blueprint(api_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_user():
        return {"current_user": current_user}

    with app.app_context():
        db.create_all()
        _seed_admin()

    return app

def _seed_admin():
    """Create the single seeded Admin account if it doesn't exist yet.
    Admin never self-registers, per the project rules."""
    from models import User, ROLE_ADMIN
    if User.query.filter_by(role=ROLE_ADMIN).first() is None:
        admin = User(name="System Admin", email="admin@trek.com", role=ROLE_ADMIN)
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("Seeded default admin login -> admin@trek.com / admin123")

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)