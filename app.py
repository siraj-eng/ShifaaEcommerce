import os

from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from extensions import db, login_manager

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv()


def create_app():
    app = Flask(__name__)

    # Basic config
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "shifaa.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"

    from models import User  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Routes
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if not name or not email or not password:
                flash("Please fill in all fields.", "error")
            elif password != confirm:
                flash("Passwords do not match.", "error")
            else:
                existing = User.query.filter_by(email=email).first()
                if existing:
                    flash("An account with this email already exists.", "warning")
                else:
                    user = User(
                        name=name,
                        email=email,
                        role="user",
                        password_hash=generate_password_hash(password),
                    )
                    db.session.add(user)
                    db.session.commit()
                    flash("Account created successfully. Please log in.", "success")
                    return redirect(url_for("login"))

        return render_template("auth/register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                flash("Welcome back!", "success")
                next_page = request.args.get("next")
                return redirect(next_page or url_for("dashboard"))
            flash("Invalid email or password", "danger")
        return render_template("auth/login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == "admin":
            return render_template("admin/dashboard.html")
        return render_template("user/dashboard.html")

    @app.cli.command("init-db")
    def init_db():
        """Initialize the database and create an initial admin user if none exists."""
        from models import User  # local import to avoid circular

        db.create_all()
        admin_email = os.getenv("ADMIN_EMAIL", "admin@shifaa.local")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                name="Admin",
                email=admin_email,
                role="admin",
                password_hash=generate_password_hash(admin_password),
            )
            db.session.add(admin)
            db.session.commit()
            print(f"Created default admin user: {admin_email} / {admin_password}")
        else:
            print("Admin user already exists.")

        print("Database initialized.")

    return app


if __name__ == "__main__":
    # Prefer running via: flask --app app:create_app run
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)


