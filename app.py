import os
from datetime import datetime
from decimal import Decimal

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
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
    # Use absolute path for database
    db_path = os.path.join(BASE_DIR, "shifaa.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
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
        # Redirect authenticated users to dashboard
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("base.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        # Redirect authenticated users to dashboard
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email_input = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if not name or not email_input or not password:
                flash("Please fill in all fields.", "error")
            elif password != confirm:
                flash("Passwords do not match.", "error")
            elif len(password) < 6:
                flash("Password must be at least 6 characters long.", "error")
            else:
                # Append @shifaaherbal.com if not already present
                if "@" in email_input:
                    email = email_input
                    if not email.endswith("@shifaaherbal.com"):
                        flash("Email must be from @shifaaherbal.com domain.", "error")
                        return render_template("auth/register.html")
                else:
                    email = f"{email_input}@shifaaherbal.com"
                
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
                    # Automatically log in the user after registration
                    login_user(user)
                    flash("Account created successfully! Welcome to Shifaa Herbal.", "success")
                    return redirect(url_for("dashboard"))

        return render_template("auth/register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        # Redirect authenticated users to dashboard
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        
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
        
        from models import Order, Appointment, CartItem
        # Get user stats for dashboard
        recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter_by(
            user_id=current_user.id, 
            status="scheduled"
        ).filter(Appointment.appointment_date >= datetime.utcnow()).order_by(Appointment.appointment_date).limit(5).all()
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        
        return render_template("user/dashboard.html", recent_orders=recent_orders, upcoming_appointments=upcoming_appointments, cart_count=cart_count)

    # ========== USER ROUTES ==========
    
    # Products
    @app.route("/products")
    def products():
        from models import Product
        category = request.args.get("category", "")
        search = request.args.get("search", "")
        query = Product.query.filter_by(is_active=True)
        
        if category:
            query = query.filter_by(category=category)
        if search:
            query = query.filter(Product.name.contains(search) | Product.description.contains(search))
        
        products_list = query.all()
        categories = db.session.query(Product.category).distinct().all()
        categories = [c[0] for c in categories if c[0]]
        
        return render_template("user/products.html", products=products_list, categories=categories, current_category=category, search=search)
    
    @app.route("/products/<int:product_id>")
    def product_detail(product_id):
        from models import Product
        product = Product.query.get_or_404(product_id)
        return render_template("user/product_detail.html", product=product)
    
    # Cart
    @app.route("/cart")
    @login_required
    def cart():
        from models import CartItem
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        total = sum(item.product.price * item.quantity for item in cart_items)
        return render_template("user/cart.html", cart_items=cart_items, total=total)
    
    @app.route("/cart/add/<int:product_id>", methods=["POST"])
    @login_required
    def add_to_cart(product_id):
        from models import CartItem, Product
        product = Product.query.get_or_404(product_id)
        quantity = int(request.form.get("quantity", 1))
        
        cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            cart_item.quantity += quantity
        else:
            cart_item = CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity)
            db.session.add(cart_item)
        
        db.session.commit()
        flash(f"{product.name} added to cart.", "success")
        return redirect(request.referrer or url_for("products"))
    
    @app.route("/cart/update/<int:item_id>", methods=["POST"])
    @login_required
    def update_cart(item_id):
        from models import CartItem
        cart_item = CartItem.query.get_or_404(item_id)
        if cart_item.user_id != current_user.id:
            flash("Unauthorized.", "error")
            return redirect(url_for("cart"))
        
        quantity = int(request.form.get("quantity", 1))
        if quantity <= 0:
            db.session.delete(cart_item)
        else:
            cart_item.quantity = quantity
        db.session.commit()
        return redirect(url_for("cart"))
    
    @app.route("/cart/remove/<int:item_id>", methods=["POST"])
    @login_required
    def remove_from_cart(item_id):
        from models import CartItem
        cart_item = CartItem.query.get_or_404(item_id)
        if cart_item.user_id != current_user.id:
            flash("Unauthorized.", "error")
            return redirect(url_for("cart"))
        
        db.session.delete(cart_item)
        db.session.commit()
        flash("Item removed from cart.", "success")
        return redirect(url_for("cart"))
    
    # Checkout
    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        from models import CartItem, Order, OrderItem
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        
        if not cart_items:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("cart"))
        
        if request.method == "POST":
            shipping_address = request.form.get("shipping_address", current_user.address or "")
            delivery_option = request.form.get("delivery_option", "standard")
            
            # Calculate total
            total = sum(item.product.price * item.quantity for item in cart_items)
            
            # Create order
            import random
            order_number = f"SHF{random.randint(100000, 999999)}"
            order = Order(
                user_id=current_user.id,
                order_number=order_number,
                total_amount=total,
                shipping_address=shipping_address,
                delivery_option=delivery_option,
                status="pending"
            )
            db.session.add(order)
            db.session.flush()
            
            # Create order items
            for cart_item in cart_items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=cart_item.product_id,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price
                )
                db.session.add(order_item)
            
            # Clear cart
            CartItem.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            
            flash(f"Order #{order_number} placed successfully!", "success")
            return redirect(url_for("order_detail", order_id=order.id))
        
        total = sum(item.product.price * item.quantity for item in cart_items)
        return render_template("user/checkout.html", cart_items=cart_items, total=total)
    
    # Orders
    @app.route("/orders")
    @login_required
    def orders():
        from models import Order
        orders_list = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
        return render_template("user/orders.html", orders=orders_list)
    
    @app.route("/orders/<int:order_id>")
    @login_required
    def order_detail(order_id):
        from models import Order
        order = Order.query.get_or_404(order_id)
        if order.user_id != current_user.id:
            flash("Unauthorized.", "error")
            return redirect(url_for("orders"))
        return render_template("user/order_detail.html", order=order)
    
    @app.route("/orders/<int:order_id>/reorder", methods=["POST"])
    @login_required
    def reorder(order_id):
        from models import Order, OrderItem, CartItem
        order = Order.query.get_or_404(order_id)
        if order.user_id != current_user.id:
            flash("Unauthorized.", "error")
            return redirect(url_for("orders"))
        
        for order_item in order.items:
            cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=order_item.product_id).first()
            if cart_item:
                cart_item.quantity += order_item.quantity
            else:
                cart_item = CartItem(user_id=current_user.id, product_id=order_item.product_id, quantity=order_item.quantity)
                db.session.add(cart_item)
        
        db.session.commit()
        flash("Items added to cart.", "success")
        return redirect(url_for("cart"))
    
    # Practitioners
    @app.route("/practitioners")
    def practitioners():
        from models import Practitioner
        practitioners_list = Practitioner.query.filter_by(is_active=True).all()
        return render_template("user/practitioners.html", practitioners=practitioners_list)
    
    @app.route("/practitioners/<int:practitioner_id>")
    def practitioner_detail(practitioner_id):
        from models import Practitioner
        practitioner = Practitioner.query.get_or_404(practitioner_id)
        return render_template("user/practitioner_detail.html", practitioner=practitioner)
    
    # Appointments
    @app.route("/appointments")
    @login_required
    def appointments():
        from models import Appointment
        appointments_list = Appointment.query.filter_by(user_id=current_user.id).order_by(Appointment.appointment_date.desc()).all()
        return render_template("user/appointments.html", appointments=appointments_list)
    
    @app.route("/appointments/book/<int:practitioner_id>", methods=["GET", "POST"])
    @login_required
    def book_appointment(practitioner_id):
        from models import Practitioner, Appointment
        practitioner = Practitioner.query.get_or_404(practitioner_id)
        
        if request.method == "POST":
            appointment_date_str = request.form.get("appointment_date")
            appointment_time = request.form.get("appointment_time")
            appointment_type = request.form.get("appointment_type", "general advice")
            notes = request.form.get("notes", "")
            
            try:
                appointment_datetime = datetime.strptime(f"{appointment_date_str} {appointment_time}", "%Y-%m-%d %H:%M")
            except ValueError:
                flash("Invalid date or time format.", "error")
                return render_template("user/book_appointment.html", practitioner=practitioner)
            
            appointment = Appointment(
                user_id=current_user.id,
                practitioner_id=practitioner_id,
                appointment_type=appointment_type,
                appointment_date=appointment_datetime,
                notes=notes,
                status="scheduled"
            )
            db.session.add(appointment)
            db.session.commit()
            flash("Appointment booked successfully!", "success")
            return redirect(url_for("appointments"))
        
        return render_template("user/book_appointment.html", practitioner=practitioner)
    
    @app.route("/appointments/<int:appointment_id>")
    @login_required
    def appointment_detail(appointment_id):
        from models import Appointment
        appointment = Appointment.query.get_or_404(appointment_id)
        if appointment.user_id != current_user.id:
            flash("Unauthorized.", "error")
            return redirect(url_for("appointments"))
        return render_template("user/appointment_detail.html", appointment=appointment)
    
    # Profile
    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            current_user.name = request.form.get("name", current_user.name)
            current_user.phone = request.form.get("phone", current_user.phone)
            current_user.address = request.form.get("address", current_user.address)
            
            new_password = request.form.get("new_password", "")
            if new_password:
                if len(new_password) < 6:
                    flash("Password must be at least 6 characters.", "error")
                else:
                    current_user.password_hash = generate_password_hash(new_password)
                    flash("Password updated.", "success")
            
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("profile"))
        
        return render_template("user/profile.html")
    
    # Health Information
    @app.route("/health-info")
    def health_info():
        return render_template("user/health_info.html")
    
    # Community
    @app.route("/community")
    def community():
        return render_template("user/community.html")
    
    # Support
    @app.route("/support")
    def support():
        return render_template("user/support.html")

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
    # Development mode with debug enabled
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='127.0.0.1', port=5000, debug=True)


