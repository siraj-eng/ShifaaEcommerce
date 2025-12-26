# Deploying to Render

## Quick Deploy Steps

1. **Create a Render Account**
   - Go to https://render.com
   - Sign up or log in

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository (or deploy from public repo)

3. **Configure Build Settings**
   - **Name**: `shifaa-herbal-commerce` (or your choice)
   - **Environment**: `Python 3`
   - **Build Command**: 
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**: 
     ```bash
     gunicorn --bind 0.0.0.0:$PORT wsgi:app
     ```

4. **Set Environment Variables**
   Click "Environment" tab and add:
   - `FLASK_ENV` = `production`
   - `SECRET_KEY` = (Generate a random secret key - Render can auto-generate)
   - `ADMIN_EMAIL` = `admin@shifaa.local` (or your choice)
   - `ADMIN_PASSWORD` = (Set a secure password)

5. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy your app
   - Your app will be available at: `https://your-app-name.onrender.com`

## Using render.yaml (Alternative)

If you have `render.yaml` in your repo:
- Render will automatically detect it
- Just connect your repo and deploy
- Settings will be auto-configured

## Important Notes

- **Free Tier**: Apps on free tier spin down after 15 minutes of inactivity
- **Database**: SQLite works but consider PostgreSQL for production
- **Static Files**: Make sure static files are committed to repo
- **First Deploy**: Takes 5-10 minutes

## Troubleshooting

- **Build Fails**: Check build logs for missing dependencies
- **App Crashes**: Check runtime logs
- **Database Issues**: Ensure `init-db` runs in build command
- **Port Issues**: Render uses PORT env variable (gunicorn handles this)

## Post-Deployment

1. Visit your app URL
2. Login with admin credentials you set
3. Test user registration
4. Monitor logs in Render dashboard

