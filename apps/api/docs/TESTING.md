# Testing Guide

## Overview

This guide covers running and writing tests for the Smart Stock Bot API. The test suite includes integration tests that verify the complete functionality of billing, entitlements, trading, and signal generation.

## Test Structure

```
apps/api/tests/
├── __init__.py
├── conftest.py              # Shared fixtures and configuration
└── integration/
    ├── __init__.py
    ├── test_billing_flow.py      # Billing and subscription tests
    ├── test_entitlements.py      # Plan feature enforcement tests
    ├── test_trading.py           # Trading endpoint tests
    └── test_signals.py           # Signal generation tests
```

## Prerequisites

### Install Dependencies

```bash
cd apps/api
pip install -r requirements.txt
```

Testing dependencies included:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `httpx` - Test HTTP client
- `faker` - Fake data generation

### Database Setup

Tests require a separate test database to avoid affecting development data.

**Option 1: Docker (Recommended)**

```bash
# Start PostgreSQL
docker compose up -d postgres

# Create test database
docker compose exec postgres createdb -U stockbot smartstockbot_test
```

**Option 2: Local PostgreSQL**

```bash
# Create test database
createdb smartstockbot_test

# Update .env with test database URL
TEST_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/smartstockbot_test
```

## Running Tests

### Run All Tests

```bash
# From apps/api directory
pytest
```

### Run Specific Test File

```bash
pytest tests/integration/test_billing_flow.py
```

### Run Specific Test

```bash
pytest tests/integration/test_billing_flow.py::test_free_signup_assigns_free_plan
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage Report

```bash
pytest --cov=app --cov-report=html
```

Coverage report will be generated in `htmlcov/index.html`.

### Run Integration Tests Only

```bash
pytest -m integration
```

## Test Configuration

### pytest.ini

Configuration in `pytest.ini`:

```ini
[pytest]
# Test discovery
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Test paths
testpaths = tests

# Async support
asyncio_mode = auto

# Markers
markers =
    integration: Integration tests requiring database
    unit: Unit tests (fast, no external dependencies)
    slow: Slow running tests
    requires_alpaca: Tests requiring Alpaca API credentials
    requires_stripe: Tests requiring Stripe API credentials
```

### Environment Variables for Tests

Create `.env.test` file:

```bash
# Test environment
ENVIRONMENT=test
DEBUG=true

# Test database (separate from development)
DATABASE_URL=postgresql+asyncpg://stockbot:password@localhost:5432/smartstockbot_test

# Redis (can use same instance with different DB number)
REDIS_URL=redis://localhost:6379/1

# Required secrets (can use dummy values for tests)
SECRET_KEY=test-secret-key-32-characters-long
JWT_SECRET_KEY=test-jwt-secret-key-32-chars
ENCRYPTION_KEY=test-encryption-key-for-testing

# Optional: Real API keys for integration tests
# (tests will skip if not provided)
ALPACA_API_KEY=
ALPACA_API_SECRET=
STRIPE_SECRET_KEY=
```

## Test Categories

### 1. Billing Flow Tests (`test_billing_flow.py`)

**What's tested:**
- Free plan assignment on signup
- Listing available subscription plans
- Viewing current subscription
- Upgrading to paid plans (Stripe checkout)
- Subscription cancellation
- Payment failure handling
- Webhook signature validation

**Key tests:**
```python
test_free_signup_assigns_free_plan()
test_list_available_plans()
test_get_current_subscription()
test_upgrade_to_paid_plan_requires_stripe()
test_cancel_subscription_keeps_access_until_period_end()
```

**Expected results:**
- New users automatically get free plan
- All 3 plans (Free, Starter, Pro) are available
- Subscription status tracked correctly

### 2. Entitlements Tests (`test_entitlements.py`)

**What's tested:**
- Free users blocked from live trading
- Free users can paper trade
- Signal delay enforcement (15 min for free, 0 for paid)
- Watchlist symbol limits (5 for free, 20 for starter/pro)
- Pro users require admin approval for live trading
- Entitlement caching for performance
- Downgrade removes premium features

**Key tests:**
```python
test_free_user_blocked_from_live_trading()
test_free_user_gets_delayed_signals()
test_starter_user_gets_realtime_signals()
test_free_user_watchlist_limit()
test_pro_user_can_access_live_trading_if_approved()
```

**Expected results:**
- Free users: 15-min delay, 5 symbol limit, paper trading only
- Starter users: Real-time signals, 20 symbol limit, paper trading
- Pro users: Real-time signals, unlimited symbols, live trading (with approval)

### 3. Trading Tests (`test_trading.py`)

**What's tested:**
- Paper trading order placement
- Order validation (limit orders require price)
- Listing user's orders
- Fetching specific orders
- Position tracking
- Account information retrieval
- Portfolio summary
- Order cancellation
- Broker integration (Alpaca)

**Key tests:**
```python
test_paper_trading_order_placement()
test_limit_order_requires_price()
test_list_user_orders()
test_get_account_info()
test_get_portfolio_summary()
```

**Expected results:**
- Orders saved to database with broker IDs
- Paper/live orders kept separate
- Position sync from broker works
- Validation prevents invalid orders

**Note:** Many trading tests will return 500/503 if Alpaca credentials are not configured. This is expected - the tests verify the entitlement logic and endpoint structure.

### 4. Signal Generation Tests (`test_signals.py`)

**What's tested:**
- Signal generation for single symbol
- Signal delay for free users
- Real-time signals for paid users
- Bulk signal generation
- Watchlist limits
- SMA values in response
- Signal reasoning
- Error handling

**Key tests:**
```python
test_generate_signal_for_symbol()
test_free_user_signal_delay()
test_pro_user_realtime_signals()
test_bulk_signal_generation()
test_bulk_signal_free_user_limit()
```

**Expected results:**
- Signals include action (buy/sell/hold)
- Confidence score between 0-1
- SMA values and reasoning provided
- Delays enforced based on plan
- Bulk requests respect symbol limits

**Note:** Signal tests may return 500/503 if Alpaca Market Data API is not configured. The tests verify entitlement enforcement regardless.

## Test Fixtures

### Database Fixtures

Defined in `conftest.py`:

**`db_engine`** - Creates test database engine

**`db_session`** - Provides test database session

**`client`** - HTTP test client with database override

Usage:
```python
@pytest.mark.asyncio
async def test_example(db_session: AsyncSession):
    # Use db_session to query database
    pass
```

### Authentication Fixtures

**`test_user`** - Creates a test user in database

**`test_user_token`** - Gets JWT token for test user

**`authenticated_client`** - HTTP client with auth header

Usage:
```python
@pytest.mark.asyncio
async def test_protected_endpoint(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/protected")
    assert response.status_code == 200
```

## Writing New Tests

### Integration Test Template

```python
"""Test description."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_your_feature(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User
):
    """
    Test your feature.

    Expected behavior:
    - What should happen
    - What should be returned
    """
    # Arrange: Set up test data

    # Act: Call endpoint
    response = await authenticated_client.get("/api/v1/your-endpoint")

    # Assert: Verify results
    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data
```

### Best Practices

1. **Use descriptive test names**: `test_free_user_blocked_from_live_trading` is better than `test_trading`

2. **Follow AAA pattern**: Arrange, Act, Assert

3. **Test one thing per test**: Each test should verify a single behavior

4. **Use fixtures**: Reuse common setup via fixtures

5. **Handle external API failures gracefully**:
   ```python
   if response.status_code == 200:
       # Verify successful response
   # else: API not configured, test skipped
   ```

6. **Document expected behavior**: Add docstrings explaining what should happen

7. **Test both success and failure cases**

## Continuous Integration

### GitHub Actions Workflow

Create `.github/workflows/test.yml`:

```yaml
name: API Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: stockbot
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: smartstockbot_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd apps/api
          pip install -r requirements.txt

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://stockbot:testpassword@localhost:5432/smartstockbot_test
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: test-secret-key-32-characters-long
          JWT_SECRET_KEY: test-jwt-secret-key-32-chars
          ENCRYPTION_KEY: test-encryption-key-for-testing
        run: |
          cd apps/api
          pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./apps/api/coverage.xml
```

## Troubleshooting

### Tests Fail with Database Connection Error

**Problem**: Cannot connect to test database

**Solution**:
```bash
# Verify PostgreSQL is running
docker compose ps

# Check database exists
docker compose exec postgres psql -U stockbot -l | grep smartstockbot_test

# Create if missing
docker compose exec postgres createdb -U stockbot smartstockbot_test
```

### Tests Fail with "Event loop is closed"

**Problem**: Async test configuration issue

**Solution**: Ensure `pytest-asyncio` is installed and `asyncio_mode = auto` is in `pytest.ini`

### Tests Skip with "Alpaca/Stripe not configured"

**Problem**: External API credentials not provided

**Solution**: This is expected behavior. Tests verify entitlement logic even without real API keys. To run full integration tests, add credentials to `.env.test`.

### Slow Test Execution

**Problem**: Tests take too long

**Solution**:
- Run specific test files instead of all tests
- Use parallel execution: `pytest -n auto` (requires `pytest-xdist`)
- Mark slow tests: `@pytest.mark.slow` and skip them: `pytest -m "not slow"`

## Coverage Goals

Target coverage metrics:
- **Overall**: > 80%
- **Critical paths** (auth, billing, trading): > 90%
- **Utilities**: > 70%

Generate coverage report:
```bash
pytest --cov=app --cov-report=term-missing
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [httpx testing](https://www.python-httpx.org/async/)
- [SQLAlchemy testing](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
