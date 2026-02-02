import os
from datetime import datetime
from decimal import Decimal
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
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
    # Currency: Kenyan Shillings
    app.config["CURRENCY_SYMBOL"] = os.getenv("CURRENCY_SYMBOL", "KSh")
    app.config["CURRENCY_CODE"] = os.getenv("CURRENCY_CODE", "KES")
    # M-Pesa Till Number
    app.config["MPESA_TILL_NUMBER"] = os.getenv("MPESA_TILL_NUMBER", "622255")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"

    from models import User  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_currency():
        return {
            "currency_symbol": app.config["CURRENCY_SYMBOL"],
            "currency_code": app.config["CURRENCY_CODE"],
        }

    @app.template_filter("currency")
    def currency_filter(value):
        if value is None:
            return ""
        return f"{app.config['CURRENCY_SYMBOL']} {float(value):,.2f}"

    def admin_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("login"))
            if current_user.role != "admin":
                flash("Access denied. Admin only.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated

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
            from models import Order, Product, Appointment
            product_count = Product.query.count()
            order_count = Order.query.count()
            user_count = User.query.count()
            from models import Practitioner
            practitioner_count = Practitioner.query.count()
            pending_orders = Order.query.filter_by(status="pending").count()
            total_revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)).scalar() or 0
            recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
            upcoming_appointments = Appointment.query.filter(Appointment.appointment_date >= datetime.utcnow(), Appointment.status=="scheduled").order_by(Appointment.appointment_date).limit(5).all()
            low_stock = Product.query.filter(Product.stock > 0, Product.stock < 10).count()
            return render_template(
                "admin/dashboard.html",
                product_count=product_count,
                order_count=order_count,
                user_count=user_count,
                practitioner_count=practitioner_count,
                pending_orders=pending_orders,
                recent_orders=recent_orders,
                upcoming_appointments=upcoming_appointments,
                low_stock=low_stock,
                total_revenue=total_revenue,
            )
        
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
            contact_name = request.form.get("contact_name", current_user.name)
            contact_email = request.form.get("contact_email", current_user.email)
            contact_phone = request.form.get("contact_phone", current_user.phone or "")
            
            # Save checkout info to session and redirect to payment page
            session["checkout_info"] = {
                "shipping_address": shipping_address,
                "delivery_option": delivery_option,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "contact_phone": contact_phone,
            }
            
            return redirect(url_for("payment"))
        
        total = sum(item.product.price * item.quantity for item in cart_items)
        return render_template("user/checkout.html", cart_items=cart_items, total=float(total))
    
    # Payment
    @app.route("/payment", methods=["GET", "POST"])
    @login_required
    def payment():
        from models import CartItem, Order, OrderItem
        
        # Check if checkout info exists in session
        if "checkout_info" not in session:
            flash("Please complete checkout first.", "warning")
            return redirect(url_for("checkout"))
        
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        if not cart_items:
            flash("Your cart is empty.", "warning")
            session.pop("checkout_info", None)
            return redirect(url_for("cart"))
        
        checkout_info = session["checkout_info"]
        total = sum(item.product.price * item.quantity for item in cart_items)
        
        if request.method == "POST":
            # User confirmed payment - create order
            import random
            order_number = f"SHF{random.randint(100000, 999999)}"
            order = Order(
                user_id=current_user.id,
                order_number=order_number,
                total_amount=total,
                shipping_address=checkout_info["shipping_address"],
                delivery_option=checkout_info["delivery_option"],
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
            
            # Clear cart and session
            CartItem.query.filter_by(user_id=current_user.id).delete()
            session.pop("checkout_info", None)
            db.session.commit()
            
            flash("Order received! Pay via M-Pesa to Till No. " + app.config["MPESA_TILL_NUMBER"] + " to complete payment.", "success")
            return redirect(url_for("order_detail", order_id=order.id))
        
        return render_template("user/payment.html", cart_items=cart_items, total=float(total), checkout_info=checkout_info)
    
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
        
        # Fetch user's orders and appointments
        from models import Order, Appointment
        recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter_by(user_id=current_user.id).filter(Appointment.appointment_date >= datetime.utcnow()).order_by(Appointment.appointment_date.asc()).limit(5).all()
        
        return render_template("user/profile.html", recent_orders=recent_orders, upcoming_appointments=upcoming_appointments)
    
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

    # ========== ADMIN ROUTES ==========
    @app.route("/admin/products")
    @login_required
    @admin_required
    def admin_products():
        from models import Product
        category = request.args.get("category", "")
        search = request.args.get("search", "")
        query = Product.query
        if category:
            query = query.filter_by(category=category)
        if search:
            query = query.filter(Product.name.contains(search) | Product.description.contains(search))
        products_list = query.order_by(Product.name).all()
        categories = db.session.query(Product.category).distinct().all()
        categories = [c[0] for c in categories if c[0]]
        return render_template("admin/products.html", products=products_list, categories=categories, current_category=category, search=search)

    @app.route("/admin/products/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_product_new():
        from models import Product
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "")
            price = request.form.get("price", "0")
            stock = int(request.form.get("stock", 0) or 0)
            category = request.form.get("category", "").strip()
            image_url = request.form.get("image_url", "").strip()
            usage_instructions = request.form.get("usage_instructions", "")
            warnings = request.form.get("warnings", "")
            is_active = request.form.get("is_active") == "on"
            if not name:
                flash("Product name is required.", "error")
                return render_template("admin/product_form.html", product=None)
            try:
                price_val = Decimal(price)
            except Exception:
                flash("Invalid price.", "error")
                return render_template("admin/product_form.html", product=None)
            product = Product(
                name=name,
                description=description or None,
                price=price_val,
                stock=stock,
                category=category or None,
                image_url=image_url or None,
                usage_instructions=usage_instructions or None,
                warnings=warnings or None,
                is_active=is_active,
            )
            db.session.add(product)
            db.session.commit()
            flash(f"Product «{product.name}» created.", "success")
            return redirect(url_for("admin_products"))
        return render_template("admin/product_form.html", product=None)

    @app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_product_edit(product_id):
        from models import Product
        product = Product.query.get_or_404(product_id)
        if request.method == "POST":
            product.name = request.form.get("name", "").strip()
            product.description = request.form.get("description", "") or None
            try:
                product.price = Decimal(request.form.get("price", "0"))
            except Exception:
                pass
            product.stock = int(request.form.get("stock", 0) or 0)
            product.category = request.form.get("category", "").strip() or None
            product.image_url = request.form.get("image_url", "").strip() or None
            product.usage_instructions = request.form.get("usage_instructions", "") or None
            product.warnings = request.form.get("warnings", "") or None
            product.is_active = request.form.get("is_active") == "on"
            if not product.name:
                flash("Product name is required.", "error")
                return render_template("admin/product_form.html", product=product)
            db.session.commit()
            flash(f"Product «{product.name}» updated.", "success")
            return redirect(url_for("admin_products"))
        return render_template("admin/product_form.html", product=product)

    @app.route("/admin/products/<int:product_id>/toggle", methods=["POST"])
    @login_required
    @admin_required
    def admin_product_toggle(product_id):
        from models import Product
        product = Product.query.get_or_404(product_id)
        product.is_active = not product.is_active
        db.session.commit()
        status = "active" if product.is_active else "inactive"
        flash(f"Product «{product.name}» is now {status}.", "success")
        return redirect(request.referrer or url_for("admin_products"))

    @app.route("/admin/orders")
    @login_required
    @admin_required
    def admin_orders():
        from models import Order
        status_filter = request.args.get("status", "")
        query = Order.query.order_by(Order.created_at.desc())
        if status_filter:
            query = query.filter_by(status=status_filter)
        orders_list = query.all()
        return render_template("admin/orders.html", orders=orders_list, status_filter=status_filter)

    @app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_order_detail(order_id):
        from models import Order
        order = Order.query.get_or_404(order_id)
        if request.method == "POST":
            new_status = request.form.get("status", "").strip()
            if new_status in ("pending", "processing", "shipped", "delivered", "cancelled"):
                order.status = new_status
                order.updated_at = datetime.utcnow()
                db.session.commit()
                flash(f"Order #{order.order_number} status updated to {new_status}.", "success")
            return redirect(url_for("admin_order_detail", order_id=order.id))
        return render_template("admin/order_detail.html", order=order)

    @app.route("/admin/users")
    @login_required
    @admin_required
    def admin_users():
        search = request.args.get("search", "")
        query = User.query.order_by(User.name)
        if search:
            query = query.filter(User.name.contains(search) | User.email.contains(search))
        users_list = query.all()
        return render_template("admin/users.html", users=users_list, search=search)

    @app.route("/admin/practitioners")
    @login_required
    @admin_required
    def admin_practitioners():
        from models import Practitioner
        practitioners_list = Practitioner.query.order_by(Practitioner.name).all()
        return render_template("admin/practitioners.html", practitioners=practitioners_list)

    @app.route("/admin/practitioners/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_practitioner_new():
        from models import Practitioner
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            title = request.form.get("title", "").strip()
            bio = request.form.get("bio", "")
            specialties = request.form.get("specialties", "").strip()
            image_url = request.form.get("image_url", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            is_active = request.form.get("is_active") == "on"
            if not name:
                flash("Practitioner name is required.", "error")
                return render_template("admin/practitioner_form.html", practitioner=None)
            practitioner = Practitioner(
                name=name,
                title=title or None,
                bio=bio or None,
                specialties=specialties or None,
                image_url=image_url or None,
                email=email or None,
                phone=phone or None,
                is_active=is_active,
            )
            db.session.add(practitioner)
            db.session.commit()
            flash(f"Practitioner «{practitioner.name}» created.", "success")
            return redirect(url_for("admin_practitioners"))
        return render_template("admin/practitioner_form.html", practitioner=None)

    @app.route("/admin/practitioners/<int:practitioner_id>/edit", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_practitioner_edit(practitioner_id):
        from models import Practitioner
        practitioner = Practitioner.query.get_or_404(practitioner_id)
        if request.method == "POST":
            practitioner.name = request.form.get("name", "").strip()
            practitioner.title = request.form.get("title", "").strip() or None
            practitioner.bio = request.form.get("bio", "") or None
            practitioner.specialties = request.form.get("specialties", "").strip() or None
            practitioner.image_url = request.form.get("image_url", "").strip() or None
            practitioner.email = request.form.get("email", "").strip() or None
            practitioner.phone = request.form.get("phone", "").strip() or None
            practitioner.is_active = request.form.get("is_active") == "on"
            if not practitioner.name:
                flash("Practitioner name is required.", "error")
                return render_template("admin/practitioner_form.html", practitioner=practitioner)
            db.session.commit()
            flash(f"Practitioner «{practitioner.name}» updated.", "success")
            return redirect(url_for("admin_practitioners"))
        return render_template("admin/practitioner_form.html", practitioner=practitioner)

    @app.route("/admin/practitioners/<int:practitioner_id>/toggle", methods=["POST"])
    @login_required
    @admin_required
    def admin_practitioner_toggle(practitioner_id):
        from models import Practitioner
        practitioner = Practitioner.query.get_or_404(practitioner_id)
        practitioner.is_active = not practitioner.is_active
        db.session.commit()
        status = "active" if practitioner.is_active else "inactive"
        flash(f"Practitioner «{practitioner.name}» is now {status}.", "success")
        return redirect(request.referrer or url_for("admin_practitioners"))

    @app.route("/admin/appointments")
    @login_required
    @admin_required
    def admin_appointments():
        from models import Appointment
        status_filter = request.args.get("status", "")
        query = Appointment.query.order_by(Appointment.appointment_date.desc())
        if status_filter:
            query = query.filter_by(status=status_filter)
        appointments_list = query.all()
        return render_template("admin/appointments.html", appointments=appointments_list, status_filter=status_filter)

    @app.route("/admin/sales")
    @login_required
    @admin_required
    def admin_sales():
        from datetime import timedelta
        from models import Order
        date_from_str = request.args.get("date_from", "").strip()
        date_to_str = request.args.get("date_to", "").strip()
        delivered_only = request.args.get("delivered_only") == "on"
        query = Order.query
        if delivered_only:
            query = query.filter_by(status="delivered")
        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
                query = query.filter(Order.created_at >= date_from)
            except ValueError:
                pass
        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, "%Y-%m-%d")
                end_of_day = date_to + timedelta(days=1)
                query = query.filter(Order.created_at < end_of_day)
            except ValueError:
                pass
        orders_in_period = query.order_by(Order.created_at.desc()).all()
        order_count = len(orders_in_period)
        revenue = sum(float(o.total_amount) for o in orders_in_period)
        total_all_time = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)).scalar() or 0
        total_orders_all_time = Order.query.count()
        return render_template(
            "admin/sales.html",
            date_from=date_from_str,
            date_to=date_to_str,
            delivered_only=delivered_only,
            order_count=order_count,
            revenue=revenue,
            total_orders_all_time=total_orders_all_time,
            total_revenue_all_time=float(total_all_time) if total_all_time else 0,
            orders=orders_in_period[:50],
        )

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


