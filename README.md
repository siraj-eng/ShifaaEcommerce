# Shifaa Herbal Commerce Portal

A lightweight Flask-based herbal e-commerce platform with user and admin portals.

## Features

- User product browsing, shopping cart, checkout, and orders
- Admin order and practitioner management
- Secure authentication with email validation
- SQLite database using SQLAlchemy

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your configuration.

3. Initialize the database:
```bash
flask --app app:create_app init-db
```

## Running the application

Run locally with:
```bash
python app.py
```
or with Gunicorn:
```bash
gunicorn --bind 0.0.0.0:5000 wsgi:app
```

Visit `http://127.0.0.1:5000` in your browser.

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
