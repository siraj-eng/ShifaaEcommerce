# Shifaa Herbal Commerce Portal

A comprehensive e-commerce platform for herbal medicine store with user and admin portals.

## Features

- **User Portal**: Product browsing, shopping cart, orders, appointments with practitioners
- **Admin Portal**: Management dashboard
- **Authentication**: Secure login/registration with email validation (@shifaaherbal.com domain)
- **Database**: SQLite with SQLAlchemy ORM

## Installation

1. **Install dependencies**
```bash
pip install -r requirements.txt
```

2. **Initialize database**
```bash
flask --app app:create_app init-db
```

## Running the Application

Simply run:
```bash
python app.py
```

The server will start at: **http://127.0.0.1:5000**

Press `Ctrl+C` to stop the server.

## Default Admin Account

- Email: `admin@shifaa.local`
- Password: `admin123`

## User Registration

Users must register with email ending in `@shifaaherbal.com`
(Enter just the username part, e.g., "siraj" becomes "siraj@shifaaherbal.com")

## Project Structure

```
ShifaaHerbalCommerce/
├── app.py                 # Main application file
├── models.py              # Database models
├── extensions.py          # Flask extensions
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates
├── static/                # Static files (CSS, JS, images)
└── shifaa.db             # SQLite database
```

## Technologies

- Flask 3.0.3
- SQLAlchemy
- Flask-Login
- Bootstrap 5
- Font Awesome

## Development

The application runs in development mode with:
- Auto-reload on code changes
- Debug mode enabled
- SQLite database
