from datetime import datetime
from flask_login import UserMixin
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)  # Added index
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    role = db.Column(db.String(20), default='user', index=True)  # Added index
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='user', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.email}>'


class Product(db.Model):
    __tablename__ = 'product'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)  # Added index
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0, index=True)  # Added index
    category = db.Column(db.String(100), index=True)  # Added index
    image_url = db.Column(db.String(500))
    usage_instructions = db.Column(db.Text)
    warnings = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)  # Added index
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='product', lazy='dynamic')
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
    @property
    def in_stock(self):
        return self.stock > 0 and self.is_active


class CartItem(db.Model):
    __tablename__ = 'cart_item'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # Added index
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, index=True)  # Added index
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite index for faster lookups
    __table_args__ = (
        db.Index('idx_cart_user_product', 'user_id', 'product_id'),
    )
    
    def __repr__(self):
        return f'<CartItem User:{self.user_id} Product:{self.product_id} Qty:{self.quantity}>'


class Order(db.Model):
    __tablename__ = 'order'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)  # Added index
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # Added index
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(50), default='pending', index=True)  # Added index
    shipping_address = db.Column(db.Text, nullable=False)
    delivery_option = db.Column(db.String(50), default='standard')
    payment_method = db.Column(db.String(50), default='mpesa')
    payment_status = db.Column(db.String(50), default='pending', index=True)  # Added index
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)  # Added index
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    
    # Composite index for common queries
    __table_args__ = (
        db.Index('idx_order_user_status', 'user_id', 'status'),
        db.Index('idx_order_created_status', 'created_at', 'status'),
    )
    
    def __repr__(self):
        return f'<Order {self.order_number} Status:{self.status}>'
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items)


class OrderItem(db.Model):
    __tablename__ = 'order_item'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)  # Added index
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, index=True)  # Added index
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)  # Price at time of purchase
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Composite index for faster joins
    __table_args__ = (
        db.Index('idx_orderitem_order_product', 'order_id', 'product_id'),
    )
    
    def __repr__(self):
        return f'<OrderItem Order:{self.order_id} Product:{self.product_id} Qty:{self.quantity}>'
    
    @property
    def subtotal(self):
        return self.price * self.quantity


class Practitioner(db.Model):
    __tablename__ = 'practitioner'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)  # Added index
    title = db.Column(db.String(100))
    bio = db.Column(db.Text)
    specialties = db.Column(db.String(200), index=True)  # Added index
    image_url = db.Column(db.String(500))
    email = db.Column(db.String(120), unique=True, index=True)  # Added index
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True, index=True)  # Added index
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    appointments = db.relationship('Appointment', backref='practitioner', lazy='dynamic')
    
    def __repr__(self):
        return f'<Practitioner {self.name}>'


class Appointment(db.Model):
    __tablename__ = 'appointment'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # Added index
    practitioner_id = db.Column(db.Integer, db.ForeignKey('practitioner.id'), nullable=False, index=True)  # Added index
    appointment_type = db.Column(db.String(100), default='general advice')
    appointment_date = db.Column(db.DateTime, nullable=False, index=True)  # Added index
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='scheduled', index=True)  # Added index
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite indexes for common queries
    __table_args__ = (
        db.Index('idx_appointment_user_status', 'user_id', 'status'),
        db.Index('idx_appointment_practitioner_date', 'practitioner_id', 'appointment_date'),
        db.Index('idx_appointment_date_status', 'appointment_date', 'status'),
    )
    
    def __repr__(self):
        return f'<Appointment User:{self.user_id} Practitioner:{self.practitioner_id} Date:{self.appointment_date}>'
    
    @property
    def is_upcoming(self):
        return self.appointment_date > datetime.utcnow() and self.status == 'scheduled'
    
    @property
    def is_past(self):
        return self.appointment_date < datetime.utcnow()


# Optional: Add a Review/Rating model for products
class ProductReview(db.Model):
    __tablename__ = 'product_review'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    is_verified_purchase = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Composite index
    __table_args__ = (
        db.Index('idx_review_product_user', 'product_id', 'user_id'),
        db.Index('idx_review_rating', 'rating'),
    )
    
    def __repr__(self):
        return f'<ProductReview Product:{self.product_id} Rating:{self.rating}>'


# Optional: Add a Wishlist model
class Wishlist(db.Model):
    __tablename__ = 'wishlist'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Composite unique index to prevent duplicates
    __table_args__ = (
        db.UniqueConstraint('user_id', 'product_id', name='unique_user_product'),
        db.Index('idx_wishlist_user', 'user_id'),
    )
    
    def __repr__(self):
        return f'<Wishlist User:{self.user_id} Product:{self.product_id}>'


# Optional: Add Notification model
class Notification(db.Model):
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info', index=True)  # info, success, warning, error
    is_read = db.Column(db.Boolean, default=False, index=True)
    link = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Composite index
    __table_args__ = (
        db.Index('idx_notification_user_read', 'user_id', 'is_read'),
        db.Index('idx_notification_created', 'created_at'),
    )
    
    def __repr__(self):
        return f'<Notification User:{self.user_id} Title:{self.title[:50]}>'
    
    def mark_as_read(self):
        self.is_read = True
        db.session.commit()