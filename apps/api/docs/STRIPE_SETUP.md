# Stripe Integration Setup Guide

This guide walks through setting up Stripe for subscription billing in the Smart Stock Bot API.

## Prerequisites

- Stripe account (sign up at https://stripe.com)
- Access to Stripe Dashboard
- Database already seeded with subscription plans (Free, Starter, Pro)

## Step 1: Create Products in Stripe Dashboard

### 1.1 Navigate to Products

1. Log in to Stripe Dashboard
2. Go to **Products** in the left sidebar
3. Click **Add product**

### 1.2 Create Starter Plan Product

**Product Details:**
- Name: `Starter Plan`
- Description: `Real-time signals and basic trading features for beginners`
- Statement descriptor: `SMARTSTOCK STARTER`

**Pricing:**
- Create **two** prices for this product:
  1. **Monthly**: $19.99 USD, recurring monthly
  2. **Yearly**: $199.99 USD, recurring yearly (17% discount)

**Save the Price IDs:**
After creating, note down:
- Monthly Price ID: `price_XXXXXXXXXX`
- Yearly Price ID: `price_YYYYYYYYYY`

### 1.3 Create Pro Plan Product

**Product Details:**
- Name: `Pro Plan`
- Description: `Full access with real-time signals, live trading, and premium features`
- Statement descriptor: `SMARTSTOCK PRO`

**Pricing:**
- Create **two** prices for this product:
  1. **Monthly**: $49.99 USD, recurring monthly
  2. **Yearly**: $479.99 USD, recurring yearly (20% discount)

**Save the Price IDs:**
After creating, note down:
- Monthly Price ID: `price_XXXXXXXXXX`
- Yearly Price ID: `price_YYYYYYYYYY`

## Step 2: Update Database with Price IDs

Once you have the real Stripe price IDs, update the database:

```sql
-- Connect to database
psql -U stockbot -d stockbot_dev

-- Update Starter plan
UPDATE subscription_plans
SET
  stripe_price_id_monthly = 'price_XXXXXXXXXX',  -- Replace with real ID
  stripe_price_id_yearly = 'price_YYYYYYYYYY'    -- Replace with real ID
WHERE name = 'starter';

-- Update Pro plan
UPDATE subscription_plans
SET
  stripe_price_id_monthly = 'price_XXXXXXXXXX',  -- Replace with real ID
  stripe_price_id_yearly = 'price_YYYYYYYYYY'    -- Replace with real ID
WHERE name = 'pro';

-- Verify updates
SELECT name, stripe_price_id_monthly, stripe_price_id_yearly
FROM subscription_plans
WHERE name IN ('starter', 'pro');
```

## Step 3: Configure Stripe API Keys

### 3.1 Get API Keys

1. In Stripe Dashboard, go to **Developers** → **API keys**
2. Copy your **Secret key** (starts with `sk_test_` for test mode or `sk_live_` for live mode)
3. Reveal and copy your **Publishable key** (starts with `pk_test_` or `pk_live_`)

### 3.2 Update Environment Variables

Edit `apps/api/.env`:

```bash
# Stripe Configuration
STRIPE_API_KEY=sk_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
STRIPE_WEBHOOK_SECRET=  # Will configure this in Step 4
```

### 3.3 Restart API

```bash
docker compose restart api
```

## Step 4: Configure Webhooks

Stripe webhooks notify your API of subscription events (payment succeeded, subscription canceled, etc.).

### 4.1 Create Webhook Endpoint

1. In Stripe Dashboard, go to **Developers** → **Webhooks**
2. Click **Add endpoint**
3. Enter endpoint URL:
   - **Development**: `https://your-dev-tunnel.ngrok.io/api/v1/billing/webhooks/stripe`
   - **Production**: `https://api.youromain.com/api/v1/billing/webhooks/stripe`

### 4.2 Select Events to Listen

Check the following events:
- `checkout.session.completed` - New subscription created
- `customer.subscription.updated` - Subscription changed (upgrade/downgrade)
- `customer.subscription.deleted` - Subscription canceled
- `invoice.payment_succeeded` - Payment successful
- `invoice.payment_failed` - Payment failed

### 4.3 Get Webhook Signing Secret

1. After creating the webhook, click on it to view details
2. Copy the **Signing secret** (starts with `whsec_`)
3. Update `.env`:

```bash
STRIPE_WEBHOOK_SECRET=whsec_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

4. Restart API:

```bash
docker compose restart api
```

## Step 5: Test Stripe Integration

### 5.1 Test Checkout Flow

```bash
# Get your access token
TOKEN="your_jwt_token_here"

# Create checkout session for Starter monthly
curl -X POST http://localhost:8000/api/v1/billing/checkout \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_name": "starter",
    "billing_cycle": "monthly",
    "success_url": "http://localhost:3000/billing/success",
    "cancel_url": "http://localhost:3000/billing/cancel"
  }'

# Response will include checkout_url - open in browser to test
```

### 5.2 Use Test Cards

Stripe provides test card numbers for development:

**Success scenarios:**
- `4242 4242 4242 4242` - Successful payment
- `4000 0025 0000 3155` - Requires authentication (3D Secure)

**Failure scenarios:**
- `4000 0000 0000 9995` - Declined card
- `4000 0000 0000 0341` - Expired card

**Card details for testing:**
- Expiry: Any future date (e.g., `12/34`)
- CVC: Any 3 digits (e.g., `123`)
- ZIP: Any 5 digits (e.g., `12345`)

### 5.3 Verify Webhook Delivery

1. After completing a test checkout, go to **Developers** → **Webhooks** in Stripe Dashboard
2. Click on your webhook endpoint
3. View recent webhook deliveries
4. Verify `checkout.session.completed` was sent with HTTP 200 response

## Step 6: Verify Subscription Created

```bash
# Check user's subscription
curl -X GET http://localhost:8000/api/v1/billing/subscription \
  -H "Authorization: Bearer $TOKEN"

# Should return active subscription with Starter or Pro plan
```

## Step 7: Production Checklist

Before going live:

### 7.1 Switch to Live Mode

1. In Stripe Dashboard, toggle **Test mode** to **off** (top right)
2. Get live API keys from **Developers** → **API keys**
3. Update production `.env` with live keys (`sk_live_...` and `pk_live_...`)

### 7.2 Update Webhooks

1. Create new webhook endpoint with production URL
2. Select same events as test mode
3. Update `STRIPE_WEBHOOK_SECRET` with new signing secret

### 7.3 Test Live Integration

1. Use a real credit card with small amount ($1 test charge)
2. Verify webhook delivery
3. Immediately cancel test subscription
4. Refund test charge

### 7.4 Security Checklist

- [ ] Verify webhook signature in production (already implemented)
- [ ] Use HTTPS for all webhook endpoints
- [ ] Never log full credit card numbers
- [ ] Store only Stripe customer IDs and subscription IDs (no card data)
- [ ] Enable Stripe Radar for fraud detection
- [ ] Set up email notifications for failed payments

## Troubleshooting

### Webhook Not Receiving Events

1. Check webhook URL is publicly accessible
2. Verify endpoint returns HTTP 200
3. Check API logs for errors: `docker compose logs api | grep webhook`
4. Use Stripe CLI for local testing:
   ```bash
   stripe listen --forward-to localhost:8000/api/v1/billing/webhooks/stripe
   ```

### Invalid Price ID Error

- Ensure price IDs in database match Stripe Dashboard
- Verify using correct mode (test vs live)
- Check price IDs don't have typos

### Subscription Not Created

1. Check `user_subscriptions` table: `SELECT * FROM user_subscriptions;`
2. Verify webhook was received: Check API logs
3. Check Stripe logs in Dashboard → **Events**

## Support

- **Stripe Docs**: https://stripe.com/docs/billing/subscriptions/overview
- **Stripe Support**: https://support.stripe.com
- **Test Cards**: https://stripe.com/docs/testing#cards
