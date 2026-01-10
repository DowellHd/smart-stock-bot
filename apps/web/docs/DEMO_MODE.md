# Demo Mode Documentation

## Overview

Demo Mode allows the Smart Stock Bot frontend to run completely standalone without requiring a backend API connection. This is perfect for:

- **Portfolio showcases** - Demonstrate the UI/UX without infrastructure
- **Development** - Work on frontend features without backend dependencies
- **Testing** - Verify UI behavior with predictable mock data
- **Presentations** - Show the platform to potential investors or users

## How It Works

When `NEXT_PUBLIC_DEMO_MODE=true`, the API client intercepts all outgoing requests and returns realistic mock data instead of calling the backend. This happens transparently - your components make the same API calls, but get instant responses with generated data.

### Architecture

```
┌─────────────────────────────────────────┐
│         React Components                │
│  (make normal API calls via apiClient)  │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│          API Client Layer               │
│  ┌───────────────────────────────────┐  │
│  │  Is DEMO_MODE enabled?            │  │
│  │  ├─ Yes → Return mock data        │  │
│  │  └─ No  → Forward to backend      │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
   ┌──────────┐      ┌──────────────┐
   │ Mock Data│      │ Real Backend │
   │Generator │      │   API (8000) │
   └──────────┘      └──────────────┘
```

## Enabling Demo Mode

### Quick Start

```bash
# Create .env.local in apps/web/
echo "NEXT_PUBLIC_DEMO_MODE=true" > apps/web/.env.local

# Start the frontend
npm run dev
```

Visit http://localhost:3000 - the app will work with zero backend dependencies!

### Configuration

**apps/web/.env.local**
```bash
# Enable demo mode
NEXT_PUBLIC_DEMO_MODE=true

# These are not used in demo mode but keep them for when you disable it
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_PREFIX=/api/v1
```

## Mock Data Features

### Authentication
- Any email/password combination will "log in" successfully
- Returns a mock JWT token (not validated, just for state management)
- Mock user profile with free plan

### Market Data
- **Quotes**: Realistic bid/ask spreads for any symbol
- **Historical Data**: Generated OHLCV bars with random walk + volatility
- **Market Status**: Returns mock market hours

### Trading Signals
- **SMA Crossover**: Generates buy/sell/hold signals with explanations
- **Bulk Signals**: Supports multiple symbols
- **Delayed Signals**: Free plan users get 15-minute delay (as in production)

### Portfolio & Trading
- **Positions**: 4 mock positions (AAPL, MSFT, GOOGL, NVDA) with P&L
- **Account Balance**: ~$40K total portfolio value
- **Orders**: Recent order history with various statuses
- **Paper Trading**: All orders are marked as "paper" mode

### Billing
- **Plans**: Free ($0), Starter ($19.99), Pro ($49.99)
- **Subscription**: Mock subscription showing free plan status

## Customizing Mock Data

All mock data generators are in `apps/web/src/lib/mock-data.ts`:

### Example: Change Mock Portfolio

```typescript
// apps/web/src/lib/mock-data.ts
export function generateMockPortfolio(): MockPortfolio {
  const positions: MockPosition[] = [
    {
      symbol: 'YOUR_SYMBOL',
      quantity: 100,
      avg_entry_price: 50.00,
      current_price: 55.00,
      // ... calculate market_value, unrealized_pl, etc
    },
    // Add more positions
  ];
  // ... rest of portfolio calculation
}
```

### Example: Add New Mock Endpoint

```typescript
// apps/web/src/lib/api-client.ts
private async handleDemoRequest(config: InternalAxiosRequestConfig): Promise<any> {
  // ... existing handlers

  // Add your new endpoint
  if (url.includes('/your-new-endpoint')) {
    return {
      your: 'mock data',
    };
  }
}
```

## Network Simulation

Demo mode includes realistic network delays:

```typescript
// Simulates 300ms - 1000ms latency
await new Promise((resolve) => setTimeout(resolve, 300 + Math.random() * 700));
```

This makes the demo feel like a real application with network requests.

## Demo Mode Indicators

**Recommended**: Add a visual indicator when in demo mode:

```typescript
// components/DemoModeBanner.tsx
export function DemoModeBanner() {
  if (process.env.NEXT_PUBLIC_DEMO_MODE !== 'true') return null;

  return (
    <div className="bg-yellow-500 text-black px-4 py-2 text-center font-semibold">
      🎭 Demo Mode - All data is simulated
    </div>
  );
}
```

## Testing Demo Mode

### Verify It's Working

1. **Check Console**: Look for network requests in DevTools
   - In demo mode: Requests complete instantly (no actual HTTP)
   - In production: Real HTTP requests to localhost:8000

2. **Check Data**: Look for mock IDs in responses
   - Demo: `id: "mock-signal-0"`, `id: "mock-order-1"`
   - Production: Real UUIDs from database

3. **Test Login**: Try logging in with fake credentials
   - Demo: Any email/password works
   - Production: Only valid credentials work

### Common Issues

**Issue**: Demo mode not working, getting CORS errors

**Solution**: Check `.env.local` has `NEXT_PUBLIC_DEMO_MODE=true` (must be NEXT_PUBLIC_ prefix!)

---

**Issue**: Mock data not realistic enough

**Solution**: Update generators in `mock-data.ts` with better algorithms or real historical patterns

---

**Issue**: Some pages still need backend

**Solution**: Check `handleDemoRequest()` in `api-client.ts` - you may need to add mock handlers for new endpoints

## Deployment with Demo Mode

### Vercel / Netlify

Add environment variable in your hosting dashboard:

```
NEXT_PUBLIC_DEMO_MODE=true
```

This creates a public demo site requiring zero backend infrastructure!

### GitHub Pages

Demo mode is perfect for GitHub Pages since it's static-only:

```bash
# Build with demo mode
NEXT_PUBLIC_DEMO_MODE=true npm run build

# Deploy to gh-pages
npm run deploy
```

## Disabling Demo Mode

Simply remove or set to false:

```bash
# apps/web/.env.local
NEXT_PUBLIC_DEMO_MODE=false
```

The app will immediately switch to making real API calls to the backend.

## Security Considerations

- Demo mode is **client-side only** - never use for real user authentication
- Mock tokens are not validated and should never reach a real backend
- Always disable demo mode in production environments handling real data
- Demo mode data is randomly generated each time - no persistence

## Use Cases

### 1. Job Applications / Portfolio

Deploy on Vercel with demo mode enabled:
- Recruiters can interact with the full platform
- No backend/database costs
- Instant page loads
- Professional demonstration of UI/UX skills

### 2. Investor Presentations

Run locally with demo mode:
- Show platform capabilities without live trading risk
- Consistent, predictable data for demos
- No API dependencies during presentations

### 3. Frontend Development

Develop UI features without backend:
- No need to run Docker containers
- Faster iteration cycles
- Work offline
- Test edge cases with controlled mock data

## Further Reading

- `apps/web/src/lib/mock-data.ts` - All mock data generators
- `apps/web/src/lib/api-client.ts` - Demo mode interceptor logic
- Project README - Full project documentation
