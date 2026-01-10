# Stripe Production Deployment Guide

This guide covers deploying the Smart Stock Bot billing system with Stripe integration to production.

## Prerequisites

- [x] Stripe account activated in production mode
- [x] Production Stripe API keys obtained
- [x] Subscription plans created in Stripe Dashboard
- [x] Price IDs obtained for all plans (Free, Starter, Pro)
- [x] Webhook endpoint URL configured
- [ ] Production database accessible
- [ ] Redis instance configured
- [ ] Production environment variables set

## 1. Stripe Dashboard Configuration

### 1.1 Create Products and Prices

Verify the following products and prices exist in your Stripe Dashboard:

**Free Plan**:
- Product: "Free Plan"
- Price: $0.00/month
- Copy the Price ID from Stripe Dashboard

**Starter Plan**:
- Product: "Starter Plan"
- Monthly Price: $19.99/month
- Yearly Price: $199.99/year
- Copy both Price IDs from Stripe Dashboard

**Pro Plan**:
- Product: "Pro Plan"
- Monthly Price: $49.99/month
- Yearly Price: $479.99/year
- Copy both Price IDs from Stripe Dashboard

**Note**: You can find Price IDs in Stripe Dashboard → Products → [Select Product] → Pricing → Copy Price ID button next to each price.

### 1.2 Configure Webhook Endpoint

1. Navigate to: Stripe Dashboard → Developers → Webhooks
2. Click "Add endpoint"
3. Endpoint URL: `https://api.smartstockbot.app/api/v1/billing/webhooks/stripe`
4. Select events to listen to:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
   - `invoice.payment_succeeded`
   - `customer.updated`
5. Copy the webhook signing secret (starts with `whsec_`)

### 1.3 Configure Customer Portal

1. Navigate to: Stripe Dashboard → Settings → Billing → Customer Portal
2. Enable customer portal
3. Configure settings:
   - Allow customers to update payment methods: **Yes**
   - Allow customers to update billing info: **Yes**
   - Allow customers to cancel subscriptions: **Yes**
   - Cancellation behavior: **At period end** (no immediate cancellation)
   - Invoice history: **Show all invoices**
4. Save settings

## 2. Environment Configuration

### 2.1 Set Production Environment Variables

Add the following to your production `.env` file or secrets manager:

```bash
# Stripe Production Keys (from Stripe Dashboard → Developers → API Keys)
STRIPE_SECRET_KEY=<your-stripe-secret-key>
STRIPE_PUBLISHABLE_KEY=<your-stripe-publishable-key>
STRIPE_WEBHOOK_SECRET=<your-webhook-signing-secret>

# Stripe Price IDs (from Stripe Dashboard → Products → Select Product → Copy Price ID)
STRIPE_PRICE_FREE_MONTHLY=<free-plan-monthly-price-id>
STRIPE_PRICE_STARTER_MONTHLY=<starter-plan-monthly-price-id>
STRIPE_PRICE_STARTER_YEARLY=<starter-plan-yearly-price-id>
STRIPE_PRICE_PRO_MONTHLY=<pro-plan-monthly-price-id>
STRIPE_PRICE_PRO_YEARLY=<pro-plan-yearly-price-id>
```

**Note**: Replace the placeholder values (in angle brackets) with your actual Stripe keys from the Stripe Dashboard. NEVER commit these keys to version control.

**Security Note**: Never commit these keys to version control. Use environment variables or a secrets manager.

### 2.2 Verify Other Required Environment Variables

```bash
# Application
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<your-secret-key>
API_PREFIX=/api/v1
ALLOWED_ORIGINS='["https://smartstockbot.app"]'

# Database
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<database>

# Redis
REDIS_URL=redis://<host>:<port>/0

# JWT Configuration
JWT_SECRET_KEY=<your-jwt-secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Encryption
ENCRYPTION_KEY=<your-encryption-key>
```

## 3. Database Migration

### 3.1 Run Billing Migrations

Ensure you have the latest billing migrations applied:

```bash
cd apps/api
alembic upgrade head
```

### 3.2 Seed Subscription Plans

Run the seed script to populate subscription plans:

```bash
cd apps/api
python scripts/seed_plans.py
```

**Expected Output**:
```
======================================================================
Subscription Plans Seed Script
======================================================================

Seeding subscription plans...
  ✓ Created Free plan with 7 features
  ✓ Created Starter plan with 7 features
  ✓ Created Pro plan with 9 features

✓ Successfully seeded 3 subscription plans with production Stripe price IDs

Plans created:
  • Free Plan    ($0/mo) - Price ID: price_XXXXX
  • Starter Plan ($19.99/mo or $199.99/yr)
    - Monthly: price_XXXXX
    - Yearly:  price_XXXXX
  • Pro Plan     ($49.99/mo or $479.99/yr)
    - Monthly: price_XXXXX
    - Yearly:  price_XXXXX

Stripe integration ready for production use.

======================================================================
Seed completed successfully!
======================================================================
```

### 3.3 Verify Database State

```sql
-- Check that plans were created
SELECT name, display_name, price_monthly, price_yearly, is_active
FROM subscription_plans;

-- Check that features were created
SELECT sp.name, COUNT(pf.id) as feature_count
FROM subscription_plans sp
LEFT JOIN plan_features pf ON sp.id = pf.plan_id
GROUP BY sp.name;
```

## 4. Testing

### 4.1 Test Webhook Endpoint

Use Stripe CLI to test webhook delivery:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login to Stripe
stripe login

# Forward webhooks to local endpoint (for testing)
stripe listen --forward-to https://api.smartstockbot.app/api/v1/billing/webhooks/stripe

# Trigger test events
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger invoice.payment_succeeded
```

### 4.2 Test Subscription Flow

1. **Create Checkout Session**:
   ```bash
   curl -X POST https://api.smartstockbot.app/api/v1/billing/checkout \
     -H "Authorization: Bearer <your-jwt-token>" \
     -H "Content-Type: application/json" \
     -d '{
       "plan_name": "pro",
       "billing_cycle": "monthly"
     }'
   ```

2. **Complete Checkout**:
   - Open the returned `checkout_url` in a browser
   - Use Stripe test card: `4242 4242 4242 4242`
   - Complete the payment

3. **Verify Subscription**:
   ```bash
   curl -X GET https://api.smartstockbot.app/api/v1/billing/subscription \
     -H "Authorization: Bearer <your-jwt-token>"
   ```

4. **Test Customer Portal**:
   ```bash
   curl -X POST https://api.smartstockbot.app/api/v1/billing/portal \
     -H "Authorization: Bearer <your-jwt-token>"
   ```

5. **Test Cancellation**:
   ```bash
   curl -X POST https://api.smartstockbot.app/api/v1/billing/cancel \
     -H "Authorization: Bearer <your-jwt-token>"
   ```

### 4.3 Monitor Logs

Check application logs for successful webhook processing:

```bash
# Look for these log events:
# - stripe_webhook_verified
# - stripe_webhook_handled_successfully
# - subscription_activated
# - subscription_updated
# - payment_succeeded
```

## 5. Production Checklist

- [ ] All environment variables set in production
- [ ] Database migrations applied
- [ ] Subscription plans seeded
- [ ] Stripe webhook endpoint configured and verified
- [ ] Customer portal configured in Stripe Dashboard
- [ ] Test subscription flow completed successfully
- [ ] Webhook delivery verified (check Stripe Dashboard → Developers → Webhooks)
- [ ] Logging configured (structlog + CloudWatch/Sentry)
- [ ] Error monitoring enabled (Sentry)
- [ ] Rate limiting enabled on API endpoints
- [ ] SSL/TLS certificate valid for API domain
- [ ] CORS configured for frontend domain

## 6. Monitoring and Alerts

### 6.1 Key Metrics to Monitor

- **Subscription Events**:
  - Checkout sessions created
  - Checkout sessions completed
  - Subscriptions activated
  - Subscriptions canceled
  - Payment failures
  - Payment successes

- **Webhook Health**:
  - Webhook delivery success rate
  - Webhook processing time
  - Failed webhook deliveries
  - Idempotency check hits

- **Business Metrics**:
  - Free → Starter conversion rate
  - Free → Pro conversion rate
  - Starter → Pro upgrade rate
  - Churn rate
  - MRR (Monthly Recurring Revenue)
  - ARR (Annual Recurring Revenue)

### 6.2 Set Up Alerts

Configure alerts for:

1. **Critical**:
   - Webhook delivery failures > 5% over 5 minutes
   - Payment processing errors > 1% over 15 minutes
   - Database connection failures

2. **Warning**:
   - Webhook latency > 5 seconds
   - Stripe API errors
   - Unusual subscription cancellation spike

3. **Info**:
   - New Pro subscription
   - Subscription downgrade
   - Payment method update

## 7. Common Issues and Solutions

### Issue 1: Webhook Signature Verification Failed

**Symptoms**: `stripe_webhook_invalid_signature` errors in logs

**Solution**:
- Verify `STRIPE_WEBHOOK_SECRET` is correct
- Check that webhook endpoint URL matches Stripe Dashboard configuration
- Ensure raw request body is used for signature verification

### Issue 2: Subscription Not Activated After Payment

**Symptoms**: User paid but subscription not showing in database

**Solution**:
- Check Stripe Dashboard → Webhooks for delivery status
- Verify `checkout.session.completed` webhook was delivered
- Check application logs for webhook processing errors
- Manually trigger webhook retry from Stripe Dashboard

### Issue 3: Entitlements Cache Not Invalidating

**Symptoms**: User upgraded but still seeing free plan features

**Solution**:
- Verify Redis connection is working
- Check that `invalidate_entitlements_cache()` is called after subscription changes
- Manually clear cache: `redis-cli DEL "entitlements:<user-id>"`

### Issue 4: Customer Portal Not Working

**Symptoms**: 400 error when accessing customer portal

**Solution**:
- Verify customer portal is enabled in Stripe Dashboard
- Check that user has a `stripe_customer_id` in database
- Verify return URL domain is allowed in Stripe settings

## 8. Rollback Plan

If issues arise, follow this rollback procedure:

1. **Disable Webhook Endpoint**:
   - Go to Stripe Dashboard → Developers → Webhooks
   - Disable the production webhook endpoint

2. **Revert Code Changes**:
   ```bash
   git revert <commit-hash>
   git push origin main
   ```

3. **Rollback Database** (if needed):
   ```bash
   alembic downgrade -1
   ```

4. **Notify Users**:
   - If subscriptions were affected, contact users directly
   - Offer refunds or credits if appropriate

## 9. Support and Debugging

### Useful Stripe Dashboard Links

- **Webhooks**: https://dashboard.stripe.com/webhooks
- **Subscriptions**: https://dashboard.stripe.com/subscriptions
- **Customers**: https://dashboard.stripe.com/customers
- **Logs**: https://dashboard.stripe.com/logs
- **Events**: https://dashboard.stripe.com/events

### Debugging Commands

```bash
# Check user subscription in database
psql $DATABASE_URL -c "SELECT * FROM user_subscriptions WHERE user_id = '<user-id>';"

# Check entitlements cache
redis-cli GET "entitlements:<user-id>"

# Check webhook processing cache
redis-cli KEYS "webhook_processed:*"

# View recent audit logs
psql $DATABASE_URL -c "SELECT * FROM audit_logs WHERE action LIKE 'subscription%' ORDER BY created_at DESC LIMIT 20;"
```

## 10. Next Steps

After successful deployment:

1. **Monitor for 48 hours** - Watch for errors, performance issues
2. **Review metrics** - Check subscription conversion rates
3. **Gather feedback** - Get user feedback on checkout flow
4. **Optimize** - Improve conversion funnel based on data
5. **Plan Phase 8** - Trading integration, signals, ML models

## Security Notes

- **Never log sensitive data**: Stripe keys, customer payment info, full credit card numbers
- **Use HTTPS only**: All communication with Stripe must be over HTTPS
- **Validate webhook signatures**: Always verify webhook signatures before processing
- **Implement rate limiting**: Prevent abuse of checkout endpoints
- **Regular security audits**: Review code for security vulnerabilities
- **PCI compliance**: If handling card data directly, ensure PCI DSS compliance (current implementation uses Stripe Checkout, which is PCI compliant)

## Support

For issues:
- Stripe Support: https://support.stripe.com
- Internal Issues: Create GitHub issue in private repository
- Critical Production Issues: Contact on-call engineer

---

**Last Updated**: 2025-01-10
**Version**: 1.0
**Author**: Development Team
