import os
import re
import json
import time
from datetime import datetime
from decimal import Decimal
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from extensions import db, login_manager

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv()


def create_app():
    app = Flask(__name__)

    # #region agent log
    def _dbg(hypothesisId: str, location: str, message: str, data: dict | None = None):
        try:
            payload = {
                "sessionId": "6e968a",
                "runId": "pre-fix",
                "hypothesisId": hypothesisId,
                "location": location,
                "message": message,
                "data": data or {},
                "timestamp": int(time.time() * 1000),
            }
            with open("debug-6e968a.log", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass
    # #endregion agent log

    # ========== SECURITY CONFIGURATION ==========
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me-in-production")
    
    # Database configuration
    db_path = os.path.join(BASE_DIR, "shifaa.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": 10,
        "pool_recycle": 3600,
        "pool_pre_ping": True,
    }
    
    # Business configuration
    app.config["CURRENCY_SYMBOL"] = os.getenv("CURRENCY_SYMBOL", "KES")
    app.config["CURRENCY_CODE"] = os.getenv("CURRENCY_CODE", "KES")
    app.config["MPESA_TILL_NUMBER"] = os.getenv("MPESA_TILL_NUMBER", "622255")
    
    # Security settings
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    
    # Pagination settings
    app.config["PRODUCTS_PER_PAGE"] = 12
    app.config["ORDERS_PER_PAGE"] = 10
    app.config["APPOINTMENTS_PER_PAGE"] = 10

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ========== HELPER FUNCTIONS ==========
    
    def validate_password_strength(password):
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not re.search(r"\d", password):
            return False, "Password must contain at least one number."
        if not re.search(r"[A-Za-z]", password):
            return False, "Password must contain at least one letter."
        return True, ""
    
    def validate_email_domain(email):
        allowed_domains = ["@shifaaherbal.com", "@shifaa.com"]
        for domain in allowed_domains:
            if email.endswith(domain):
                return True, ""
        return False, f"Email must be from {', '.join(allowed_domains)} domain."
    
    def sanitize_input(text):
        if not text:
            return ""
        return text.strip().replace("<", "&lt;").replace(">", "&gt;")

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
                flash("Please log in to access the admin area.", "warning")
                return redirect(url_for("admin_login"))
            if current_user.role != "admin":
                flash("Access denied. Admin privileges required.", "error")
                return redirect(url_for("admin_login"))
            return f(*args, **kwargs)
        return decorated

    # ========== AUTHENTICATION ROUTES ==========
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))
        return render_template("base.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        
        if request.method == "POST":
            first_name = sanitize_input(request.form.get("first_name", ""))
            last_name = sanitize_input(request.form.get("last_name", ""))
            email_input = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            
            name = f"{first_name} {last_name}".strip()

            if not first_name or not last_name or not email_input or not password:
                flash("Please fill in all fields.", "error")
                return render_template("auth/register.html")
            
            if password != confirm:
                flash("Passwords do not match.", "error")
                return render_template("auth/register.html")
            
            is_valid, password_msg = validate_password_strength(password)
            if not is_valid:
                flash(password_msg, "error")
                return render_template("auth/register.html")
            
            if "@" in email_input:
                email = email_input
            else:
                email = f"{email_input}@shifaaherbal.com"
            
            is_valid_domain, domain_msg = validate_email_domain(email)
            if not is_valid_domain:
                flash(domain_msg, "error")
                return render_template("auth/register.html")
            
            existing = User.query.filter_by(email=email).first()
            if existing:
                flash("An account with this email already exists. Please login.", "warning")
                return redirect(url_for("login"))
            
            try:
                user = User(
                    name=name,
                    email=email,
                    role="user",
                    password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                )
                db.session.add(user)
                db.session.commit()
                
                login_user(user)
                flash(f"Welcome to Shifaa Herbal, {name}!", "success")
                return redirect(url_for("dashboard"))
                
            except Exception as e:
                db.session.rollback()
                print(f"Registration error: {e}")
                flash("An error occurred during registration. Please try again.", "error")
                return render_template("auth/register.html")

        return render_template("auth/register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            if current_user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("dashboard"))
        
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            
            user = User.query.filter_by(email=email).first()
            
            if user and check_password_hash(user.password_hash, password):
                login_user(user, remember=False)
                next_page = request.args.get("next")
                
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                
                if user.role == "admin":
                    return redirect(url_for("admin_dashboard"))
                return redirect(url_for("dashboard"))
            
            flash("Invalid email or password. Please try again.", "danger")
        
        return render_template("auth/login.html")

    @app.route("/admin-login", methods=["GET", "POST"])
    def admin_login():
        if current_user.is_authenticated and current_user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            
            user = User.query.filter_by(email=email).first()
            
            if user and check_password_hash(user.password_hash, password) and user.role == "admin":
                login_user(user, remember=False)
                flash(f"Welcome back, {user.name}!", "success")
                return redirect(url_for("admin_dashboard"))
            
            flash("Invalid admin credentials. Please try again.", "danger")
        
        return render_template("auth/admin_login.html")

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login_alt():
        return redirect(url_for("admin_login"))

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    # ========== DASHBOARD ==========
    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        
        from models import Order, Appointment, CartItem
        recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter_by(
            user_id=current_user.id, 
            status="scheduled"
        ).filter(Appointment.appointment_date >= datetime.utcnow()).order_by(Appointment.appointment_date).limit(5).all()
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        
        return render_template(
            "user/dashboard.html",
            recent_orders=recent_orders,
            upcoming_appointments=upcoming_appointments,
            cart_count=cart_count,
        )

    @app.route("/admin-dashboard")
    @login_required
    @admin_required
    def admin_dashboard():
        from models import Order, Product, Appointment, Practitioner
        
        product_count = Product.query.count()
        order_count = Order.query.count()
        user_count = User.query.count()
        practitioner_count = Practitioner.query.count()
        pending_orders = Order.query.filter_by(status="pending").count()
        total_revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)).scalar() or 0
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter(
            Appointment.appointment_date >= datetime.utcnow(), 
            Appointment.status == "scheduled"
        ).order_by(Appointment.appointment_date).limit(5).all()
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

    # ========== PRODUCT ROUTES ==========
    @app.route("/products")
    def products():
        from models import Product
        category = request.args.get("category", "")
        search = request.args.get("search", "")
        page = request.args.get('page', 1, type=int)
        
        query = Product.query.filter_by(is_active=True)
        
        if category:
            query = query.filter_by(category=category)
        if search:
            search_term = sanitize_input(search)
            query = query.filter(Product.name.contains(search_term) | Product.description.contains(search_term))
        
        paginated_products = query.order_by(Product.name).paginate(
            page=page, per_page=app.config["PRODUCTS_PER_PAGE"], error_out=False
        )
        
        categories = db.session.query(Product.category).distinct().all()
        categories = [c[0] for c in categories if c[0]]
        
        return render_template("user/products.html", 
                             products=paginated_products.items,
                             pagination=paginated_products,
                             categories=categories, 
                             current_category=category, 
                             search=search)
    
    @app.route("/products/<int:product_id>")
    def product_detail(product_id):
        from models import Product, CartItem
        product = db.session.get(Product, product_id)
        if not product:
            flash("Product not found.", "error")
            return redirect(url_for("products"))
        
        # Calculate cart count for logged-in users
        cart_count = 0
        if current_user.is_authenticated:
            cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        
        return render_template("user/product_detail.html", product=product, cart_count=cart_count)

    # ========== CART ROUTES ==========
    @app.route("/cart/count")
    @login_required
    def cart_count():
        """Return current user's cart count as JSON"""
        from models import CartItem
        cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        return jsonify({'cart_count': cart_count})

    @app.route("/cart/sync")
    @login_required
    def cart_sync():
        """Return full cart data for real-time sync"""
        from models import CartItem, Product
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        
        cart_data = []
        total_quantity = 0
        total_amount = 0
        
        for item in cart_items:
            item_total = item.product.price * item.quantity
            total_quantity += item.quantity
            total_amount += item_total
            
            cart_data.append({
                'id': item.id,
                'product_id': item.product_id,
                'name': item.product.name,
                'price': float(item.product.price),
                'quantity': item.quantity,
                'total': float(item_total),
                'stock': item.product.stock,
                'is_active': item.product.is_active,
                'image_url': item.product.image_url
            })
        
        return jsonify({
            'cart_items': cart_data,
            'total_quantity': total_quantity,
            'total_amount': float(total_amount),
            'cart_count': len(cart_items),
            'shipping_cost': (total_quantity // 72 + (1 if total_quantity % 72 > 0 else 0)) * 300
        })

    @app.route("/add-to-cart/<int:product_id>", methods=["POST"])
    @login_required
    def add_to_cart_ajax(product_id):
        from models import CartItem, Product
        
        try:
            data = request.get_json()
            quantity = data.get('quantity', 1)
            
            if quantity < 1:
                return jsonify({'success': False, 'message': 'Quantity must be at least 1'}), 400
            
            product = db.session.get(Product, product_id)
            if not product or not product.is_active:
                return jsonify({'success': False, 'message': 'Product not available'}), 400
            
            if product.stock < quantity:
                return jsonify({
                    'success': False,
                    'message': f'Only {product.stock} items in stock'
                }), 400
            
            cart_item = CartItem.query.filter_by(
                user_id=current_user.id, 
                product_id=product_id
            ).first()
            
            if cart_item:
                cart_item.quantity += quantity
            else:
                cart_item = CartItem(
                    user_id=current_user.id, 
                    product_id=product_id, 
                    quantity=quantity
                )
                db.session.add(cart_item)
            
            db.session.commit()
            cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
            
            return jsonify({
                'success': True,
                'cart_count': cart_count,
                'message': f'{product.name} added to cart'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': 'An error occurred. Please try again.'
            }), 400
    
    @app.route("/cart")
    @login_required
    def cart():
        from models import CartItem
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        total = sum(item.product.price * item.quantity for item in cart_items)
        return render_template("user/cart.html", cart_items=cart_items, total=total)
    
    @app.route("/cart/update/<int:item_id>", methods=["POST"])
    @login_required
    def update_cart(item_id):
        from models import CartItem
        cart_item = db.session.get(CartItem, item_id)
        if not cart_item or cart_item.user_id != current_user.id:
            flash("Unauthorized action.", "error")
            return redirect(url_for("cart"))

        # #region agent log
        _dbg(
            "A",
            "app.py:update_cart:entry",
            "update_cart called",
            {
                "item_id": item_id,
                "raw_quantity": request.form.get("quantity"),
                "qty_before": getattr(cart_item, "quantity", None),
            },
        )
        # #endregion agent log

        quantity = int(request.form.get("quantity", 1))
        if quantity <= 0:
            db.session.delete(cart_item)
            # Remove flash message to prevent display on login page
        else:
            cart_item.quantity = quantity
            # Remove flash message to prevent display on login page

        # #region agent log
        _dbg(
            "B",
            "app.py:update_cart:before_commit",
            "update_cart about to commit",
            {"item_id": item_id, "parsed_quantity": quantity, "qty_after": getattr(cart_item, "quantity", None)},
        )
        # #endregion agent log

        db.session.commit()
        return redirect(url_for("cart"))
    
    @app.route("/cart/remove/<int:item_id>", methods=["POST"])
    @login_required
    def remove_from_cart(item_id):
        from models import CartItem
        cart_item = db.session.get(CartItem, item_id)
        if not cart_item or cart_item.user_id != current_user.id:
            flash("Unauthorized action.", "error")
            return redirect(url_for("cart"))
        
        db.session.delete(cart_item)
        db.session.commit()
        # Remove flash message to prevent display on login page
        return redirect(url_for("cart"))

    # ========== CHECKOUT & PAYMENT ==========
    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        from models import CartItem, Product
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        
        if not cart_items:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("cart"))
        
        # Check stock availability and prevent checkout if insufficient stock
        stock_issues = []
        for item in cart_items:
            if not item.product.is_active:
                stock_issues.append(f"{item.product.name} is no longer available")
            elif item.quantity > item.product.stock:
                if item.product.stock == 0:
                    stock_issues.append(f"{item.product.name} is out of stock")
                else:
                    stock_issues.append(f"Only {item.product.stock} {item.product.name} available (you have {item.quantity} in cart)")
        
        if stock_issues:
            flash("Cannot proceed to checkout - Stock Issues:", "error")
            for issue in stock_issues:
                flash(issue, "error")
            return redirect(url_for("cart"))
        
        if request.method == "POST":
            shipping_address = sanitize_input(request.form.get("shipping_address", current_user.address or ""))
            delivery_option = request.form.get("delivery_option", "standard")
            contact_name = sanitize_input(request.form.get("contact_name", current_user.name))
            contact_email = request.form.get("contact_email", current_user.email).strip().lower()
            contact_phone = sanitize_input(request.form.get("contact_phone", current_user.phone or ""))
            shipping_cost_raw = request.form.get("shipping_cost")
            
            if not shipping_address:
                flash("Please enter your shipping address.", "error")
                return redirect(url_for("checkout"))
            
            if not contact_name:
                flash("Please enter your contact name.", "error")
                return redirect(url_for("checkout"))
            
            if not contact_email or not re.match(r"[^@]+@[^@]+\.[^@]+", contact_email):
                flash("Please enter a valid email address.", "error")
                return redirect(url_for("checkout"))

            shipping_cost = 0.0
            try:
                shipping_cost = float(shipping_cost_raw) if shipping_cost_raw else 0.0
            except (TypeError, ValueError):
                shipping_cost = 0.0

            # #region agent log
            _dbg(
                "C",
                "app.py:checkout:save_session",
                "Saving checkout_info and redirecting to payment",
                {
                    "delivery_option": delivery_option,
                    "shipping_cost": shipping_cost,
                    "shipping_address_len": len(shipping_address or ""),
                    "cart_items": len(cart_items),
                },
            )
            # #endregion agent log
            
            session["checkout_info"] = {
                "shipping_address": shipping_address,
                "delivery_option": delivery_option,
                "shipping_cost": shipping_cost,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "contact_phone": contact_phone,
            }
            
            return redirect(url_for("payment"))
        
        total = sum(item.product.price * item.quantity for item in cart_items)
        total_quantity = sum(item.quantity for item in cart_items)
        
        return render_template("user/checkout.html", cart_items=cart_items, total=float(total), total_quantity=total_quantity)
    
    @app.route("/payment", methods=["GET", "POST"])
    @login_required
    def payment():
        from models import CartItem, Order, OrderItem
        import random

        # #region agent log
        _dbg(
            "D",
            "app.py:payment:entry",
            "payment route entered",
            {"has_checkout_info": "checkout_info" in session, "method": request.method},
        )
        # #endregion agent log
        
        if "checkout_info" not in session:
            flash("Please complete the checkout process first.", "warning")
            return redirect(url_for("checkout"))
        
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        if not cart_items:
            flash("Your cart is empty.", "warning")
            session.pop("checkout_info", None)
            return redirect(url_for("cart"))
        
        checkout_info = session["checkout_info"]
        total = sum(item.product.price * item.quantity for item in cart_items)
        shipping_cost = float(checkout_info.get("shipping_cost", 0) or 0)
        grand_total = float(total) + shipping_cost

        # #region agent log
        _dbg(
            "E",
            "app.py:payment:computed",
            "Computed payment totals",
            {
                "delivery_option": checkout_info.get("delivery_option"),
                "items": len(cart_items),
                "subtotal": float(total),
                "shipping_cost": shipping_cost,
                "grand_total": grand_total,
            },
        )
        # #endregion agent log
        
        if request.method == "POST":
            order_number = f"SHF{random.randint(100000, 999999)}"
            order = Order(
                user_id=current_user.id,
                order_number=order_number,
                total_amount=grand_total,
                shipping_address=checkout_info["shipping_address"],
                delivery_option=checkout_info["delivery_option"],
                status="pending"
            )
            db.session.add(order)
            db.session.flush()
            
            for cart_item in cart_items:
                # Decrement product stock
                product = cart_item.product
                if product.stock >= cart_item.quantity:
                    product.stock -= cart_item.quantity
                else:
                    # Handle insufficient stock (shouldn't happen due to checkout validation)
                    flash(f"Insufficient stock for {product.name}. Order cancelled.", "error")
                    db.session.rollback()
                    return redirect(url_for("cart"))
                
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=cart_item.product_id,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price
                )
                db.session.add(order_item)
            
            CartItem.query.filter_by(user_id=current_user.id).delete()
            session.pop("checkout_info", None)
            db.session.commit()
            
            flash(f"Order #{order_number} received! Pay via M-Pesa to Till No. {app.config['MPESA_TILL_NUMBER']} to complete payment.", "success")
            return redirect(url_for("order_detail", order_id=order.id))
        
        return render_template(
            "user/payment.html",
            cart_items=cart_items,
            total=float(total),
            shipping_cost=shipping_cost,
            grand_total=grand_total,
            checkout_info=checkout_info,
        )

    # ========== ORDER ROUTES ==========
    @app.route("/orders")
    @login_required
    def orders():
        from models import Order
        page = request.args.get('page', 1, type=int)
        
        paginated_orders = Order.query.filter_by(user_id=current_user.id)\
            .order_by(Order.created_at.desc())\
            .paginate(page=page, per_page=app.config["ORDERS_PER_PAGE"], error_out=False)
        
        return render_template("user/orders.html", 
                             orders=paginated_orders.items,
                             pagination=paginated_orders)
    
    @app.route("/orders/<int:order_id>")
    @login_required
    def order_detail(order_id):
        from models import Order
        order = db.session.get(Order, order_id)
        if not order or (order.user_id != current_user.id and current_user.role != "admin"):
            flash("Order not found or unauthorized access.", "error")
            return redirect(url_for("orders"))
        
        return render_template("user/order_detail.html", order=order)

    @app.route("/orders/<int:order_id>/reorder", methods=["POST"])
    @login_required
    def reorder(order_id):
        from models import Order, OrderItem, CartItem
        order = db.session.get(Order, order_id)
        if not order or order.user_id != current_user.id:
            flash("Unauthorized action.", "error")
            return redirect(url_for("orders"))
        
        for order_item in order.items:
            cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=order_item.product_id).first()
            if cart_item:
                cart_item.quantity += order_item.quantity
            else:
                cart_item = CartItem(user_id=current_user.id, product_id=order_item.product_id, quantity=order_item.quantity)
                db.session.add(cart_item)
        
        db.session.commit()
        flash("Items added to your cart.", "success")
        return redirect(url_for("cart"))

    # ========== PRACTITIONER ROUTES ==========
    @app.route("/practitioners")
    def practitioners():
        from models import Practitioner
        page = request.args.get('page', 1, type=int)
        
        paginated_practitioners = Practitioner.query.filter_by(is_active=True)\
            .order_by(Practitioner.name)\
            .paginate(page=page, per_page=app.config["PRODUCTS_PER_PAGE"], error_out=False)
        
        return render_template("user/practitioners.html", 
                             practitioners=paginated_practitioners.items,
                             pagination=paginated_practitioners)
    
    @app.route("/practitioners/<int:practitioner_id>")
    def practitioner_detail(practitioner_id):
        from models import Practitioner
        practitioner = db.session.get(Practitioner, practitioner_id)
        if not practitioner or not practitioner.is_active:
            flash("Practitioner not found.", "error")
            return redirect(url_for("practitioners"))
        return render_template("user/practitioner_detail.html", practitioner=practitioner)

    # ========== APPOINTMENT ROUTES ==========
    @app.route("/appointments")
    @login_required
    def appointments():
        from models import Appointment
        page = request.args.get('page', 1, type=int)
        
        paginated_appointments = Appointment.query.filter_by(user_id=current_user.id)\
            .order_by(Appointment.appointment_date.desc())\
            .paginate(page=page, per_page=app.config["APPOINTMENTS_PER_PAGE"], error_out=False)
        
        return render_template("user/appointments.html", 
                             appointments=paginated_appointments.items,
                             pagination=paginated_appointments)
    
    @app.route("/appointments/book/<int:practitioner_id>", methods=["GET", "POST"])
    @login_required
    def book_appointment(practitioner_id):
        from models import Practitioner, Appointment
        practitioner = db.session.get(Practitioner, practitioner_id)
        if not practitioner or not practitioner.is_active:
            flash("This practitioner is currently unavailable.", "error")
            return redirect(url_for("practitioners"))
        
        if request.method == "POST":
            appointment_date_str = request.form.get("appointment_date")
            appointment_time = request.form.get("appointment_time")
            appointment_type = request.form.get("appointment_type", "general advice")
            notes = sanitize_input(request.form.get("notes", ""))
            
            try:
                appointment_datetime = datetime.strptime(f"{appointment_date_str} {appointment_time}", "%Y-%m-%d %H:%M")
            except ValueError:
                flash("Invalid date or time format.", "error")
                return render_template("user/book_appointment.html", practitioner=practitioner)
            
            if appointment_datetime < datetime.utcnow():
                flash("Cannot book appointments in the past.", "error")
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
        appointment = db.session.get(Appointment, appointment_id)
        if not appointment or (appointment.user_id != current_user.id and current_user.role != "admin"):
            flash("Appointment not found or unauthorized access.", "error")
            return redirect(url_for("appointments"))
        
        return render_template("user/appointment_detail.html", appointment=appointment)

    # ========== PROFILE ROUTES ==========
    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            current_user.name = sanitize_input(request.form.get("name", current_user.name))
            current_user.phone = sanitize_input(request.form.get("phone", current_user.phone))
            current_user.address = sanitize_input(request.form.get("address", current_user.address))
            
            new_password = request.form.get("new_password", "")
            if new_password:
                is_valid, msg = validate_password_strength(new_password)
                if is_valid:
                    current_user.password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
                    flash("Password updated successfully.", "success")
                else:
                    flash(msg, "error")
                    return redirect(url_for("profile"))
            
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("profile"))
        
        from models import Order, Appointment
        recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
        upcoming_appointments = Appointment.query.filter_by(user_id=current_user.id).filter(
            Appointment.appointment_date >= datetime.utcnow()
        ).order_by(Appointment.appointment_date.asc()).limit(5).all()
        
        return render_template("user/profile.html", 
                             recent_orders=recent_orders, 
                             upcoming_appointments=upcoming_appointments)

    # ========== STATIC PAGES ==========
    @app.route("/health-info")
    def health_info():
        return render_template("user/health_info.html")
    
    @app.route("/community")
    def community():
        return render_template("user/community.html")
    
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
        page = request.args.get('page', 1, type=int)
        
        query = Product.query
        if category:
            query = query.filter_by(category=category)
        if search:
            query = query.filter(Product.name.contains(search) | Product.description.contains(search))
        
        paginated_products = query.order_by(Product.name).paginate(
            page=page, per_page=app.config["PRODUCTS_PER_PAGE"], error_out=False
        )
        
        categories = db.session.query(Product.category).distinct().all()
        categories = [c[0] for c in categories if c[0]]
        
        return render_template("admin/products.html", 
                             products=paginated_products.items,
                             pagination=paginated_products,
                             categories=categories, 
                             current_category=category, 
                             search=search)

    @app.route("/admin/products/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_product_new():
        from models import Product
        if request.method == "POST":
            name = sanitize_input(request.form.get("name", ""))
            description = sanitize_input(request.form.get("description", ""))
            price = request.form.get("price", "0")
            stock = int(request.form.get("stock", 0) or 0)
            category = sanitize_input(request.form.get("category", ""))
            image_url = sanitize_input(request.form.get("image_url", ""))
            usage_instructions = sanitize_input(request.form.get("usage_instructions", ""))
            warnings = sanitize_input(request.form.get("warnings", ""))
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
        product = db.session.get(Product, product_id)
        if not product:
            flash("Product not found.", "error")
            return redirect(url_for("admin_products"))
        
        if request.method == "POST":
            product.name = sanitize_input(request.form.get("name", ""))
            product.description = sanitize_input(request.form.get("description", "")) or None
            try:
                product.price = Decimal(request.form.get("price", "0"))
            except Exception:
                pass
            product.stock = int(request.form.get("stock", 0) or 0)
            product.category = sanitize_input(request.form.get("category", "")) or None
            product.image_url = sanitize_input(request.form.get("image_url", "")) or None
            product.usage_instructions = sanitize_input(request.form.get("usage_instructions", "")) or None
            product.warnings = sanitize_input(request.form.get("warnings", "")) or None
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
        product = db.session.get(Product, product_id)
        if not product:
            flash("Product not found.", "error")
            return redirect(request.referrer or url_for("admin_products"))
        
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
        page = request.args.get('page', 1, type=int)
        
        query = Order.query.order_by(Order.created_at.desc())
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        paginated_orders = query.paginate(page=page, per_page=app.config["ORDERS_PER_PAGE"], error_out=False)
        
        return render_template("admin/orders.html", 
                             orders=paginated_orders.items,
                             pagination=paginated_orders,
                             status_filter=status_filter)

    @app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_order_detail(order_id):
        from models import Order
        order = db.session.get(Order, order_id)
        if not order:
            flash("Order not found.", "error")
            return redirect(url_for("admin_orders"))
        
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
        page = request.args.get('page', 1, type=int)
        
        query = User.query.order_by(User.name)
        if search:
            query = query.filter(User.name.contains(search) | User.email.contains(search))
        
        paginated_users = query.paginate(page=page, per_page=20, error_out=False)
        
        return render_template("admin/users.html", 
                             users=paginated_users.items,
                             pagination=paginated_users,
                             search=search)

    @app.route("/admin/practitioners")
    @login_required
    @admin_required
    def admin_practitioners():
        from models import Practitioner
        page = request.args.get('page', 1, type=int)
        
        paginated_practitioners = Practitioner.query.order_by(Practitioner.name).paginate(
            page=page, per_page=app.config["PRODUCTS_PER_PAGE"], error_out=False
        )
        
        return render_template("admin/practitioners.html", 
                             practitioners=paginated_practitioners.items,
                             pagination=paginated_practitioners)

    @app.route("/admin/practitioners/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_practitioner_new():
        from models import Practitioner
        if request.method == "POST":
            name = sanitize_input(request.form.get("name", ""))
            title = sanitize_input(request.form.get("title", ""))
            bio = sanitize_input(request.form.get("bio", ""))
            specialties = sanitize_input(request.form.get("specialties", ""))
            image_url = sanitize_input(request.form.get("image_url", ""))
            email = sanitize_input(request.form.get("email", ""))
            phone = sanitize_input(request.form.get("phone", ""))
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
        practitioner = db.session.get(Practitioner, practitioner_id)
        if not practitioner:
            flash("Practitioner not found.", "error")
            return redirect(url_for("admin_practitioners"))
        
        if request.method == "POST":
            practitioner.name = sanitize_input(request.form.get("name", ""))
            practitioner.title = sanitize_input(request.form.get("title", "")) or None
            practitioner.bio = sanitize_input(request.form.get("bio", "")) or None
            practitioner.specialties = sanitize_input(request.form.get("specialties", "")) or None
            practitioner.image_url = sanitize_input(request.form.get("image_url", "")) or None
            practitioner.email = sanitize_input(request.form.get("email", "")) or None
            practitioner.phone = sanitize_input(request.form.get("phone", "")) or None
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
        practitioner = db.session.get(Practitioner, practitioner_id)
        if not practitioner:
            flash("Practitioner not found.", "error")
            return redirect(request.referrer or url_for("admin_practitioners"))
        
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
        page = request.args.get('page', 1, type=int)
        
        query = Appointment.query.order_by(Appointment.appointment_date.desc())
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        paginated_appointments = query.paginate(page=page, per_page=app.config["APPOINTMENTS_PER_PAGE"], error_out=False)
        
        return render_template("admin/appointments.html", 
                             appointments=paginated_appointments.items,
                             pagination=paginated_appointments,
                             status_filter=status_filter)

    @app.route("/admin/sales")
    @login_required
    @admin_required
    def admin_sales():
        from datetime import timedelta
        from models import Order
        
        date_from_str = request.args.get("date_from", "").strip()
        date_to_str = request.args.get("date_to", "").strip()
        delivered_only = request.args.get("delivered_only") == "on"
        page = request.args.get('page', 1, type=int)
        
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
        
        order_count = query.count()
        revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)).filter(
            query.whereclause
        ).scalar() or 0 if query.whereclause else 0
        
        paginated_orders = query.order_by(Order.created_at.desc()).paginate(
            page=page, per_page=50, error_out=False
        )
        
        total_all_time = db.session.query(db.func.coalesce(db.func.sum(Order.total_amount), 0)).scalar() or 0
        total_orders_all_time = Order.query.count()
        
        return render_template(
            "admin/sales.html",
            date_from=date_from_str,
            date_to=date_to_str,
            delivered_only=delivered_only,
            order_count=order_count,
            revenue=float(revenue) if revenue else 0,
            total_orders_all_time=total_orders_all_time,
            total_revenue_all_time=float(total_all_time) if total_all_time else 0,
            orders=paginated_orders.items,
            pagination=paginated_orders,
        )

    # ========== CLI COMMANDS ==========
    @app.cli.command("init-db")
    def init_db():
        from models import User

        db.create_all()
        admin_email = os.getenv("ADMIN_EMAIL", "admin@shifaaherbal.com")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                name="System Admin",
                email=admin_email,
                role="admin",
                password_hash=generate_password_hash(admin_password, method="pbkdf2:sha256"),
            )
            db.session.add(admin)
            db.session.commit()
            print(f"Created default admin user: {admin_email} / {admin_password}")
        else:
            print("Admin user already exists.")

        print("Database initialized.")

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='127.0.0.1', port=5000, debug=True)