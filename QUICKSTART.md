# Quick Start Guide

Get Smart Stock Bot running in 5 minutes!

## Prerequisites

- Docker and Docker Compose
- Node.js 18+ and npm
- Python 3.11+

## Option 1: Docker Compose (Recommended)

### 1. Start All Services

```bash
docker compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Redis (port 6379)
- FastAPI backend (port 8000)
- Next.js frontend (port 3000)

### 2. Run Database Migration

```bash
# Install Python dependencies first
cd apps/api
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run migration
alembic upgrade head
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/v1/docs
- **Health Check**: http://localhost:8000/healthz

## Option 2: Manual Setup

### 1. Start Database Services

```bash
docker compose up -d postgres redis
```

### 2. Set Up Backend

```bash
cd apps/api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file (already configured with dev keys)
cp .env.example .env

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload
```

API will be available at http://localhost:8000

### 3. Set Up Frontend

```bash
cd apps/web

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local

# Start development server
npm run dev
```

Frontend will be available at http://localhost:3000

## First Steps

### 1. Create an Account

1. Visit http://localhost:3000/auth/signup
2. Fill in your details
3. Click "Sign up"
4. Check the **API console logs** for the verification email (in dev mode, emails are logged to console)
5. Look for a message like:
   ```
   📧 DEV EMAIL TO: your@email.com
   📧 SUBJECT: Verify your email - Smart Stock Bot
   ════════════════════════════════════════
   http://localhost:3000/auth/verify-email?token=LONG_TOKEN_HERE
   ```

### 2. Verify Email (Dev Mode)

Since we're in development mode without SMTP configured:

1. Copy the verification URL from the API console
2. Paste it in your browser
3. Email will be verified

### 3. Login

1. Go to http://localhost:3000/auth/login
2. Enter your credentials
3. You'll be redirected to the dashboard

### 4. Explore Dashboard

- View your user information
- See active sessions
- Enable MFA (optional but recommended)
- Revoke sessions from other devices

## Testing MFA

### Enable MFA

1. From dashboard, click "Enable MFA"
2. Enter your password
3. Scan the QR code with an authenticator app:
   - Google Authenticator
   - Authy
   - Microsoft Authenticator
   - Any TOTP-compatible app

4. Enter the 6-digit code from your app
5. **Save your backup codes** (displayed once!)

### Test MFA Login

1. Logout
2. Login with email + password
3. You'll be prompted for MFA code
4. Enter code from authenticator app
5. Successfully logged in!

## Troubleshooting

### Database Connection Error

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check logs
docker logs smart-stock-bot-db

# Restart if needed
docker compose restart postgres
```

### Redis Connection Error

```bash
# Check if Redis is running
docker ps | grep redis

# Restart if needed
docker compose restart redis
```

### Frontend Can't Connect to API

1. Make sure API is running on port 8000:
   ```bash
   curl http://localhost:8000/healthz
   ```

2. Check CORS settings in `apps/api/.env`:
   ```
   ALLOWED_ORIGINS=http://localhost:3000
   ```

### Migration Fails

```bash
# Reset database (WARNING: deletes all data)
cd apps/api
alembic downgrade base
alembic upgrade head
```

## Next Steps

- **Enable Production SMTP**: Configure real email in `apps/api/.env`
- **Explore API**: Visit http://localhost:8000/api/v1/docs
- **Add Trading Features**: Continue with Phase 3+
- **Deploy**: See README.md for production deployment guide

## Development Tips

### Viewing Email in Dev Mode

All emails are logged to the API console. Watch the terminal running `uvicorn` to see:
- Verification emails
- Password reset emails
- MFA enabled notifications

### Useful Commands

```bash
# View API logs
docker compose logs -f api

# View all logs
docker compose logs -f

# Restart a service
docker compose restart api

# Stop all services
docker compose down

# Stop and remove volumes (fresh start)
docker compose down -v
```

### Database Access

```bash
# Connect to PostgreSQL
docker exec -it smart-stock-bot-db psql -U stockbot stockbot_dev

# View users
SELECT id, email, email_verified, mfa_enabled FROM users;

# View sessions
SELECT id, user_id, is_revoked, created_at FROM sessions;
```

## Help & Support

- **Documentation**: See README.md
- **Phase 2 Details**: See PHASE2_AUTH_COMPLETE.md
- **Issues**: File an issue on GitHub

Happy trading! 🚀
