# Deployment Guide

## Overview

This guide covers deploying the Smart Stock Bot API to production environments. The platform is designed for containerized deployment with support for various cloud providers.

## Table of Contents

- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Deployment Options](#deployment-options)
- [Post-Deployment](#post-deployment)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

## Pre-Deployment Checklist

### Security

- [ ] **Environment Variables**: All secrets stored in secure vault (AWS Secrets Manager, HashiCorp Vault, etc.)
- [ ] **API Keys**: Rotate all default/development keys
  - [ ] `SECRET_KEY` - New secure random key (256-bit)
  - [ ] `JWT_SECRET_KEY` - New secure random key (256-bit)
  - [ ] `ENCRYPTION_KEY` - New Fernet key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- [ ] **Database**: Strong password, not default
- [ ] **Redis**: Password protected, not exposed publicly
- [ ] **SSL/TLS**: HTTPS configured with valid certificates
- [ ] **CORS**: `ALLOWED_ORIGINS` set to production frontend URLs only
- [ ] **Debug Mode**: `DEBUG=false` in production

### Third-Party Services

- [ ] **Alpaca**: Production API keys configured (separate from paper trading)
- [ ] **Stripe**: Production API keys and webhooks configured
- [ ] **Email**: SMTP credentials for production email service
- [ ] **Monitoring**: Sentry DSN configured

### Database

- [ ] Migrations run successfully
- [ ] Subscription plans seeded
- [ ] Admin users created
- [ ] Backups configured

### Testing

- [ ] Integration tests pass
- [ ] Load testing completed
- [ ] Security audit performed

## Environment Configuration

### Required Environment Variables

```bash
# Application
ENVIRONMENT=production
DEBUG=false
API_PREFIX=/api/v1

# Security
SECRET_KEY=<256-bit-secret-key>
JWT_SECRET_KEY=<256-bit-jwt-key>
ENCRYPTION_KEY=<fernet-key>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://:password@host:6379/0
REDIS_POOL_SIZE=10

# CORS & Hosts
ALLOWED_ORIGINS=["https://yourdomain.com"]
ALLOWED_HOSTS=["yourdomain.com","api.yourdomain.com"]

# Email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=<sendgrid-api-key>
EMAIL_FROM=noreply@yourdomain.com

# Alpaca (Production)
ALPACA_API_KEY=<production-key>
ALPACA_API_SECRET=<production-secret>
ALPACA_BASE_URL=https://api.alpaca.markets
ALPACA_MARKET_DATA_URL=https://data.alpaca.markets

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# Feature Flags
ENABLE_LIVE_TRADING=false  # Only enable after thorough testing
RATE_LIMIT_ENABLED=true

# Monitoring
SENTRY_DSN=https://...@sentry.io/...

# Admin
ADMIN_EMAILS=["admin@yourdomain.com"]
```

### Generating Secure Keys

```bash
# SECRET_KEY and JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Database Setup

### Production Database Requirements

- **PostgreSQL 15+**
- **Connection Pooling**: Use PgBouncer or RDS Proxy
- **SSL**: Require SSL connections
- **Backups**: Automated daily backups with point-in-time recovery
- **Monitoring**: Query performance monitoring enabled

### Running Migrations

```bash
# Inside API container or on deployment server
cd /app
alembic upgrade head
```

### Seeding Initial Data

```bash
# Create subscription plans
python scripts/seed_plans.py

# Create admin users
python scripts/create_admin.py
```

## Deployment Options

### Option 1: AWS (Recommended)

#### Architecture

```
┌─────────────────────────────────────────────────────┐
│                  CloudFront (CDN)                   │
└──────────────────┬──────────────────────────────────┘
                   │
    ┌──────────────┴───────────────┐
    ▼                              ▼
┌────────────┐              ┌────────────┐
│   S3       │              │    ALB     │
│ (Frontend) │              │            │
└────────────┘              └──────┬─────┘
                                   │
                        ┌──────────┴───────────┐
                        ▼                      ▼
                  ┌──────────┐          ┌──────────┐
                  │   ECS    │          │   ECS    │
                  │ (API 1)  │          │ (API 2)  │
                  └────┬─────┘          └────┬─────┘
                       │                     │
            ┌──────────┴──────────────────────┴──────┐
            ▼                                          ▼
      ┌──────────┐                              ┌──────────┐
      │   RDS    │                              │ElastiCache│
      │PostgreSQL│                              │  (Redis) │
      └──────────┘                              └──────────┘
```

#### Services

- **Compute**: ECS Fargate (containerized API)
- **Database**: RDS PostgreSQL (Multi-AZ)
- **Cache**: ElastiCache Redis (cluster mode)
- **Load Balancer**: Application Load Balancer
- **Secrets**: AWS Secrets Manager
- **Monitoring**: CloudWatch + X-Ray
- **CDN**: CloudFront

#### Deployment Steps

1. **Create RDS PostgreSQL Instance**
   ```bash
   # Via AWS Console or Terraform
   - Engine: PostgreSQL 15
   - Instance: db.t3.medium (or larger)
   - Multi-AZ: Enabled
   - Backup retention: 7 days
   - SSL: Required
   ```

2. **Create ElastiCache Redis Cluster**
   ```bash
   - Engine: Redis 7.x
   - Node type: cache.t3.medium
   - Cluster mode: Enabled (for production)
   ```

3. **Build and Push Docker Image**
   ```bash
   # Build
   docker build -t smart-stock-bot-api:latest -f apps/api/Dockerfile .

   # Tag for ECR
   docker tag smart-stock-bot-api:latest \
     <account-id>.dkr.ecr.<region>.amazonaws.com/smart-stock-bot-api:latest

   # Push to ECR
   aws ecr get-login-password --region <region> | \
     docker login --username AWS --password-stdin \
     <account-id>.dkr.ecr.<region>.amazonaws.com

   docker push <account-id>.dkr.ecr.<region>.amazonaws.com/smart-stock-bot-api:latest
   ```

4. **Create ECS Task Definition**
   ```json
   {
     "family": "smart-stock-bot-api",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "1024",
     "memory": "2048",
     "containerDefinitions": [
       {
         "name": "api",
         "image": "<ecr-image-url>",
         "portMappings": [{"containerPort": 8000}],
         "environment": [
           {"name": "ENVIRONMENT", "value": "production"}
         ],
         "secrets": [
           {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."},
           {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/smart-stock-bot-api",
             "awslogs-region": "<region>",
             "awslogs-stream-prefix": "api"
           }
         }
       }
     ]
   }
   ```

5. **Create ECS Service**
   ```bash
   aws ecs create-service \
     --cluster smart-stock-bot \
     --service-name api \
     --task-definition smart-stock-bot-api \
     --desired-count 2 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
     --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=api,containerPort=8000"
   ```

6. **Configure Auto Scaling**
   ```bash
   # Target tracking based on CPU/memory
   aws application-autoscaling register-scalable-target \
     --service-namespace ecs \
     --scalable-dimension ecs:service:DesiredCount \
     --resource-id service/smart-stock-bot/api \
     --min-capacity 2 \
     --max-capacity 10
   ```

### Option 2: Render

Render provides a simpler deployment experience with managed services.

#### Services Needed

- **Web Service**: API deployment
- **PostgreSQL**: Managed database
- **Redis**: Managed cache

#### Deployment Steps

1. **Create New Web Service**
   - Connect GitHub repository
   - Select `apps/api` as root directory
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

2. **Add Environment Variables**
   - Add all required variables from `.env.example`
   - Use Render's secret management

3. **Create PostgreSQL Database**
   - Select PostgreSQL 15
   - Copy connection string to `DATABASE_URL`

4. **Create Redis Instance**
   - Copy connection string to `REDIS_URL`

5. **Deploy**
   - Push to main branch
   - Render auto-deploys

### Option 3: Digital Ocean App Platform

Similar to Render with droplet-based deployment.

#### Deployment

```yaml
# app.yaml
name: smart-stock-bot-api

services:
- name: api
  github:
    repo: your-username/smart-stock-bot
    branch: main
    deploy_on_push: true
  dockerfile_path: apps/api/Dockerfile
  http_port: 8000
  instance_count: 2
  instance_size_slug: professional-xs
  envs:
  - key: ENVIRONMENT
    value: production
  - key: DATABASE_URL
    value: ${db.DATABASE_URL}
  - key: REDIS_URL
    value: ${redis.DATABASE_URL}

databases:
- name: db
  engine: PG
  version: "15"

- name: redis
  engine: REDIS
  version: "7"
```

## Post-Deployment

### Initial Setup

1. **Run Database Migrations**
   ```bash
   docker exec <container-id> alembic upgrade head
   ```

2. **Seed Subscription Plans**
   ```bash
   docker exec <container-id> python scripts/seed_plans.py
   ```

3. **Create Admin User**
   ```bash
   docker exec <container-id> python scripts/create_admin.py
   ```

4. **Configure Stripe Webhooks**
   - Go to Stripe Dashboard → Developers → Webhooks
   - Add endpoint: `https://api.yourdomain.com/api/v1/billing/webhooks/stripe`
   - Select events:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_failed`
   - Copy webhook secret to `STRIPE_WEBHOOK_SECRET`

### Health Checks

```bash
# Application health
curl https://api.yourdomain.com/healthz

# Database connectivity
curl https://api.yourdomain.com/readyz

# API documentation (if DEBUG=true)
curl https://api.yourdomain.com/api/v1/docs
```

## Monitoring & Maintenance

### Monitoring

1. **Application Metrics**
   - Request rate, latency, error rate
   - Active users, API usage per plan
   - Cache hit/miss ratio

2. **Infrastructure Metrics**
   - CPU, memory, disk usage
   - Database connections, query performance
   - Redis memory usage

3. **Business Metrics**
   - New signups per day
   - Free → Paid conversion rate
   - Active subscriptions
   - Churn rate

### Logging

Structured logs with `structlog` include:
- Request ID for tracing
- User ID for auditing
- Error context for debugging

Send logs to:
- **AWS**: CloudWatch Logs
- **Render**: Built-in logging
- **Self-hosted**: ELK Stack or Grafana Loki

### Alerts

Set up alerts for:
- High error rate (> 1%)
- High latency (p95 > 1s)
- Low disk space (< 20%)
- Failed database connections
- Stripe webhook failures
- Alpaca API errors

### Backups

- **Database**: Automated daily backups, 7-day retention
- **Redis**: Regular snapshots (if persistence enabled)
- **Secrets**: Backup environment variables securely

### Maintenance Windows

- Schedule during low-traffic periods
- Notify users in advance
- Use blue-green deployment for zero downtime

## Troubleshooting

### Common Issues

**Issue**: Database connection errors

**Solution**:
```bash
# Check connection string
echo $DATABASE_URL

# Verify database is accessible
docker exec -it api psql $DATABASE_URL -c "SELECT 1;"

# Check connection pool
# Look for "too many connections" errors
```

---

**Issue**: Stripe webhooks failing

**Solution**:
```bash
# Verify webhook secret
echo $STRIPE_WEBHOOK_SECRET

# Check Stripe dashboard for failed deliveries
# Verify endpoint is publicly accessible

# Test webhook locally
stripe listen --forward-to localhost:8000/api/v1/billing/webhooks/stripe
```

---

**Issue**: High memory usage

**Solution**:
```bash
# Check for memory leaks
# Monitor /metrics endpoint

# Increase container memory
# Or scale horizontally

# Check Redis memory
redis-cli INFO memory
```

---

**Issue**: Slow API responses

**Solution**:
```bash
# Check database query performance
# Enable slow query logging

# Verify Redis cache is working
# Check cache hit rate

# Add database indexes
# Optimize N+1 queries
```

## Security Best Practices

1. **Rotate Secrets Regularly**: Change API keys, database passwords every 90 days
2. **Limit Network Access**: Use VPC, security groups, firewall rules
3. **Monitor Suspicious Activity**: Track failed logins, unusual API usage
4. **Keep Dependencies Updated**: Regularly update Python packages
5. **Run Security Scans**: Use tools like `safety`, `bandit`
6. **Enable WAF**: Use AWS WAF or Cloudflare to block attacks
7. **Rate Limiting**: Protect against DDoS and brute force
8. **Audit Logs**: Retain audit logs for compliance

## Scaling Recommendations

### Vertical Scaling

- Start: 1 vCPU, 2GB RAM
- Low traffic: 2 vCPU, 4GB RAM
- Medium traffic: 4 vCPU, 8GB RAM
- High traffic: 8+ vCPU, 16GB+ RAM

### Horizontal Scaling

- **Stateless API**: Scale to multiple instances behind load balancer
- **Database**: Use read replicas for read-heavy workloads
- **Redis**: Use cluster mode for distributed caching
- **Background Jobs**: Use Celery with multiple workers

### Cost Optimization

- Use reserved instances for predictable workloads
- Enable auto-scaling to handle traffic spikes
- Use spot instances for non-critical tasks
- Monitor and right-size resources

## Compliance

### GDPR

- Data export endpoint: `/api/v1/privacy/export`
- Data deletion endpoint: `/api/v1/privacy/delete`
- Consent management: User preferences
- Audit logs: All user actions tracked

### Financial Regulations

- **Disclaimer**: Display risk warnings prominently
- **Audit Trail**: Log all trades and signals
- **Data Retention**: Keep records for regulatory period
- **User Approval**: Require acknowledgment for live trading

## Support

For deployment issues:
- Check documentation: [README.md](../README.md)
- Review logs: Application and infrastructure
- Contact support: support@yourdomain.com
