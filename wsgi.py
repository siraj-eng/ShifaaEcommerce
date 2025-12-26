"""
WSGI entry point for Render deployment
"""
import os
from app import create_app

# Create the Flask application instance
app = create_app()

# Initialize database on startup
with app.app_context():
    from extensions import db
    from models import User, Product, Order, Appointment, Practitioner, CartItem, OrderItem
    
    # Create all tables
    db.create_all()
    
    # Create admin user if it doesn't exist
    admin_email = os.getenv("ADMIN_EMAIL", "admin@shifaa.local")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    
    if not User.query.filter_by(email=admin_email).first():
        from werkzeug.security import generate_password_hash
        admin = User(
            name="Admin",
            email=admin_email,
            role="admin",
            password_hash=generate_password_hash(admin_password),
        )
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Created admin user: {admin_email}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
