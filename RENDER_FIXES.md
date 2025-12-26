# Render Deployment Fixes

## Common Issues & Solutions

### Issue 1: Build Command Fails
**Problem**: `flask --app app:create_app init-db` fails during build

**Solution**: Removed from build command. Database initialization now happens in `wsgi.py` on startup.

### Issue 2: Port Configuration
**Problem**: Render uses `$PORT` environment variable, not hardcoded 5000

**Solution**: Updated start command to use `$PORT`:
```bash
gunicorn --bind 0.0.0.0:$PORT wsgi:app
```

### Issue 3: Database Not Initialized
**Problem**: Database tables not created on first deploy

**Solution**: `wsgi.py` now initializes database and creates admin user on startup.

### Issue 4: Import Errors
**Problem**: Missing imports or circular dependencies

**Solution**: All models imported in `wsgi.py` before database operations.

## Updated Render Settings

### Build Command:
```bash
pip install -r requirements.txt
```

### Start Command:
```bash
gunicorn --bind 0.0.0.0:$PORT wsgi:app
```

### Alternative Start Command (if above fails):
```bash
gunicorn -c gunicorn_config.py wsgi:app
```

## Environment Variables (Required)

- `FLASK_ENV` = `production`
- `SECRET_KEY` = (auto-generated or set manually)
- `ADMIN_EMAIL` = `admin@shifaa.local`
- `ADMIN_PASSWORD` = (your secure password)

## Testing Locally Before Deploy

1. Test wsgi.py locally:
```bash
gunicorn wsgi:app
```

2. Check if database initializes:
```bash
python -c "from wsgi import app; print('OK')"
```

## If Deployment Still Fails

1. Check Render logs for specific error
2. Verify all files are committed to Git
3. Ensure `requirements.txt` has all dependencies
4. Check that `wsgi.py` imports work correctly

