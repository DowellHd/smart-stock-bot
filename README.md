# Smart Stock Bot

Production-ready stock trading and portfolio management application with AI-powered insights, real-time market data, and comprehensive security features.

## Features

- **Secure Authentication**: Multi-factor authentication (TOTP), email verification, session management, and role-based access control
- **Privacy-First**: Encrypted sensitive data, GDPR-compliant data export/deletion, audit logs, and granular consent controls
- **Real-Time Market Data**: Live quotes, WebSocket streaming, interactive charts with technical indicators
- **Trading**: Paper and live trading modes with comprehensive guardrails, order management, and portfolio tracking
- **Bank & Brokerage Integration**: Plaid for bank linking, Alpaca for trading, secure token management
- **Smart AI Bot**: Trade suggestion engine with backtesting, risk management, and auto-trade capabilities (with safeguards)
- **Production-Ready**: Comprehensive testing, CI/CD, Docker deployment, structured logging, and monitoring

## Architecture

```
smart-stock-bot/
├── apps/
│   ├── web/                 # Next.js frontend (App Router + TypeScript)
│   │   ├── src/
│   │   │   ├── app/         # Pages and layouts
│   │   │   ├── components/  # Reusable components
│   │   │   └── lib/         # Utilities and API client
│   │   └── Dockerfile.dev
│   └── api/                 # FastAPI backend
│       ├── app/
│       │   ├── api/         # API routes
│       │   ├── core/        # Config, database, security
│       │   ├── models/      # SQLAlchemy models
│       │   ├── services/    # Business logic
│       │   ├── middleware/  # Custom middleware
│       │   └── main.py      # Application entry point
│       ├── alembic/         # Database migrations
│       ├── tests/           # Test suite
│       └── Dockerfile
├── packages/                # Shared packages (optional)
├── docker-compose.yml       # Local development setup
└── .github/                 # CI/CD workflows
```

## Tech Stack

### Frontend
- **Framework**: Next.js 14 (App Router) + TypeScript
- **Styling**: TailwindCSS + shadcn/ui components
- **State Management**: React Query (TanStack Query) + Zustand
- **Charts**: TradingView Lightweight Charts
- **HTTP Client**: Axios with interceptors

### Backend
- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL + SQLAlchemy 2.0 (async)
- **Cache**: Redis
- **Authentication**: OAuth2 + JWT + Argon2id password hashing
- **Background Jobs**: Celery + Redis (or FastAPI BackgroundTasks)
- **Logging**: structlog (structured JSON logging)

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **CI/CD**: GitHub Actions
- **Migrations**: Alembic

### Integrations
- **Market Data**: Alpaca Market Data API
- **Trading**: Alpaca Trading API (paper + live)
- **Bank Linking**: Plaid
- **Payments**: Stripe (for card tokenization)

## Getting Started

### Prerequisites

- Node.js >= 18.0.0
- Python >= 3.11
- Docker and Docker Compose
- npm or pnpm

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd smart-stock-bot
   ```

2. **Set up environment variables**
   ```bash
   # Root .env
   cp .env.example .env

   # API .env
   cp apps/api/.env.example apps/api/.env

   # Web .env
   cp apps/web/.env.example apps/web/.env.local
   ```

3. **Edit environment variables**
   - Generate secure keys for `SECRET_KEY`, `JWT_SECRET_KEY`, and `ENCRYPTION_KEY`
   - Add API credentials for Alpaca, Plaid, and Stripe (if using)
   - Configure email SMTP settings for verification emails

4. **Start services with Docker Compose**
   ```bash
   docker compose up -d
   ```

   This will start:
   - PostgreSQL (port 5432)
   - Redis (port 6379)
   - FastAPI backend (port 8000)
   - Next.js frontend (port 3000)

5. **Run database migrations**
   ```bash
   npm run db:migrate
   ```

6. **Seed demo data (optional)**
   ```bash
   npm run db:seed
   ```

7. **Access the application**
   - Frontend: http://localhost:3000
   - API Docs: http://localhost:8000/api/v1/docs
   - API Health: http://localhost:8000/healthz

### Demo Mode (No Backend Required)

Want to try the platform without setting up the backend? Enable demo mode to run the frontend with realistic mock data:

```bash
# Navigate to frontend
cd apps/web

# Create .env.local with demo mode enabled
echo "NEXT_PUBLIC_DEMO_MODE=true" > .env.local

# Install dependencies and start
npm install
npm run dev
```

Visit http://localhost:3000 - the app works fully with zero backend dependencies!

**Demo Mode Features:**
- ✅ Realistic mock portfolio with positions and P&L
- ✅ Trading signals with SMA crossover strategy
- ✅ Historical charts with OHLCV data
- ✅ Order management and paper trading
- ✅ Subscription plans and billing UI
- ✅ All UI components fully functional

Perfect for:
- 📊 Portfolio showcases and presentations
- 🚀 Quick demos to investors or users
- 💻 Frontend development without backend
- 🧪 Testing UI/UX changes

See [Demo Mode Documentation](./apps/web/docs/DEMO_MODE.md) for details.

## Security Model

### Authentication & Authorization
- **Password Hashing**: Argon2id (OWASP recommended)
- **MFA**: TOTP (Time-based One-Time Password) with backup codes
- **Sessions**: JWT access tokens (short-lived) + refresh tokens (httpOnly cookies)
- **Token Rotation**: Refresh tokens rotate on use with reuse detection
- **Rate Limiting**: Per-IP sliding window rate limiting on all endpoints

### Data Protection
- **Encryption at Rest**: Sensitive data (API tokens, bank tokens) encrypted with AES-256-GCM
- **Encryption in Transit**: TLS 1.2+ required in production
- **Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- **CSRF Protection**: SameSite cookies + CSRF tokens for state-changing requests
- **Input Validation**: Pydantic schemas validate all inputs

## Trading Modes

### Paper Trading (Default)
- Simulated trading with fake money
- Safe for testing and learning
- No financial risk
- Enabled by default

### Live Trading (Requires Configuration)
⚠️ **WARNING**: Live trading involves real money and financial risk.

To enable live trading:
1. Set `ENABLE_LIVE_TRADING=true` in API `.env`
2. Configure real Alpaca API credentials
3. Admin must approve user for live trading
4. User must acknowledge risk disclaimers
5. MFA must be enabled

## Disclaimer

⚠️ **IMPORTANT RISK DISCLOSURE**

This software is provided for educational and informational purposes only. Trading stocks and other financial instruments involves substantial risk of loss and is not suitable for every investor.

- This is NOT financial advice
- Past performance is not indicative of future results
- Only trade with money you can afford to lose
- The developers are not responsible for financial losses
- Always conduct your own research and consult with licensed financial advisors

By using this software, you acknowledge and accept all risks associated with trading financial instruments.

---

Built with ❤️ for the trading community
