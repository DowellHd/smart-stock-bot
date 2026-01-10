/**
 * Mock data generator for demo mode.
 * Generates realistic-looking trading data without backend connection.
 */

export interface MockSignal {
  id: string;
  symbol: string;
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  reason: string;
  strategy: string;
  current_price: number;
  sma_50?: number;
  sma_200?: number;
  timestamp: string;
  available_at: string;
  delayed: boolean;
  delay_minutes: number;
}

export interface MockPosition {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  cost_basis: number;
  unrealized_pl: number;
  unrealized_pl_percent: number;
}

export interface MockPortfolio {
  account: {
    cash: number;
    buying_power: number;
    equity: number;
    portfolio_value: number;
    currency: string;
    daytrade_count: number;
    pattern_day_trader: boolean;
  };
  positions: MockPosition[];
  total_positions: number;
  total_market_value: number;
  total_unrealized_pl: number;
  total_unrealized_pl_percent: number;
}

export interface MockOHLCVBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface MockQuote {
  symbol: string;
  bid_price: number;
  ask_price: number;
  bid_size: number;
  ask_size: number;
  timestamp: string;
}

/**
 * Generate mock trading signals.
 */
export function generateMockSignals(count: number = 20, delayed: boolean = false): MockSignal[] {
  const symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META', 'AMD', 'NFLX', 'SPY'];
  const actions: Array<'buy' | 'sell' | 'hold'> = ['buy', 'sell', 'hold'];
  const strategies = ['sma_crossover'];

  return Array.from({ length: count }, (_, i) => {
    const symbol = symbols[Math.floor(Math.random() * symbols.length)];
    const action = actions[Math.floor(Math.random() * actions.length)];
    const confidence = 0.55 + Math.random() * 0.4; // 0.55 to 0.95
    const currentPrice = 50 + Math.random() * 450;
    const sma50 = currentPrice * (0.95 + Math.random() * 0.1);
    const sma200 = currentPrice * (0.90 + Math.random() * 0.15);

    const timestamp = new Date(Date.now() - i * 3600000); // Hours ago
    const availableAt = delayed
      ? new Date(timestamp.getTime() + 15 * 60000) // +15 min for free users
      : timestamp;

    let reason = '';
    if (action === 'buy') {
      reason = `Golden cross detected: 50-day SMA ($${sma50.toFixed(2)}) crossed above 200-day SMA ($${sma200.toFixed(2)})`;
    } else if (action === 'sell') {
      reason = `Death cross detected: 50-day SMA ($${sma50.toFixed(2)}) crossed below 200-day SMA ($${sma200.toFixed(2)})`;
    } else {
      reason = sma50 > sma200
        ? `Uptrend continues: 50-day SMA ($${sma50.toFixed(2)}) above 200-day SMA ($${sma200.toFixed(2)})`
        : `Downtrend continues: 50-day SMA ($${sma50.toFixed(2)}) below 200-day SMA ($${sma200.toFixed(2)})`;
    }

    return {
      id: `mock-signal-${i}`,
      symbol,
      action,
      confidence: parseFloat(confidence.toFixed(2)),
      reason,
      strategy: strategies[0],
      current_price: parseFloat(currentPrice.toFixed(2)),
      sma_50: parseFloat(sma50.toFixed(2)),
      sma_200: parseFloat(sma200.toFixed(2)),
      timestamp: timestamp.toISOString(),
      available_at: availableAt.toISOString(),
      delayed,
      delay_minutes: delayed ? 15 : 0,
    };
  });
}

/**
 * Generate mock portfolio with positions.
 */
export function generateMockPortfolio(): MockPortfolio {
  const positions: MockPosition[] = [
    {
      symbol: 'AAPL',
      quantity: 50,
      avg_entry_price: 180.50,
      current_price: 185.25,
      market_value: 9262.50,
      cost_basis: 9025.00,
      unrealized_pl: 237.50,
      unrealized_pl_percent: 2.63,
    },
    {
      symbol: 'MSFT',
      quantity: 30,
      avg_entry_price: 350.00,
      current_price: 360.75,
      market_value: 10822.50,
      cost_basis: 10500.00,
      unrealized_pl: 322.50,
      unrealized_pl_percent: 3.07,
    },
    {
      symbol: 'GOOGL',
      quantity: 25,
      avg_entry_price: 140.00,
      current_price: 138.50,
      market_value: 3462.50,
      cost_basis: 3500.00,
      unrealized_pl: -37.50,
      unrealized_pl_percent: -1.07,
    },
    {
      symbol: 'NVDA',
      quantity: 15,
      avg_entry_price: 480.00,
      current_price: 525.30,
      market_value: 7879.50,
      cost_basis: 7200.00,
      unrealized_pl: 679.50,
      unrealized_pl_percent: 9.44,
    },
  ];

  const totalMarketValue = positions.reduce((sum, p) => sum + p.market_value, 0);
  const totalUnrealizedPL = positions.reduce((sum, p) => sum + p.unrealized_pl, 0);
  const totalUnrealizedPLPercent = (totalUnrealizedPL / (totalMarketValue - totalUnrealizedPL)) * 100;

  const cash = 8573.00;
  const portfolioValue = totalMarketValue + cash;

  return {
    account: {
      cash,
      buying_power: cash * 2, // 2x margin
      equity: portfolioValue,
      portfolio_value: portfolioValue,
      currency: 'USD',
      daytrade_count: 2,
      pattern_day_trader: false,
    },
    positions,
    total_positions: positions.length,
    total_market_value: totalMarketValue,
    total_unrealized_pl: totalUnrealizedPL,
    total_unrealized_pl_percent: parseFloat(totalUnrealizedPLPercent.toFixed(2)),
  };
}

/**
 * Generate mock OHLCV historical data for charting.
 */
export function generateMockOHLCV(symbol: string, days: number = 100): MockOHLCVBar[] {
  const data: MockOHLCVBar[] = [];
  let basePrice = 150 + Math.random() * 200; // Random starting price

  for (let i = 0; i < days; i++) {
    const time = Date.now() - (days - i) * 86400000; // Days ago in ms

    // Random walk with slight upward bias
    const change = (Math.random() - 0.48) * 10; // Slight upward bias
    const open = basePrice;
    const close = basePrice + change;

    // Generate high and low
    const dayRange = Math.abs(change) + Math.random() * 5;
    const high = Math.max(open, close) + Math.random() * dayRange;
    const low = Math.min(open, close) - Math.random() * dayRange;

    // Random volume
    const volume = Math.floor(1000000 + Math.random() * 5000000);

    data.push({
      time: Math.floor(time / 1000), // Unix timestamp in seconds
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume,
    });

    basePrice = close; // Next day starts where previous closed
  }

  return data;
}

/**
 * Generate mock quote data.
 */
export function generateMockQuote(symbol: string): MockQuote {
  const midPrice = 100 + Math.random() * 400;
  const spread = 0.05 + Math.random() * 0.20;

  return {
    symbol,
    bid_price: parseFloat((midPrice - spread / 2).toFixed(2)),
    ask_price: parseFloat((midPrice + spread / 2).toFixed(2)),
    bid_size: Math.floor(100 + Math.random() * 900),
    ask_size: Math.floor(100 + Math.random() * 900),
    timestamp: new Date().toISOString(),
  };
}

/**
 * Generate mock subscription plans.
 */
export function generateMockPlans() {
  return [
    {
      id: 'mock-free-plan',
      name: 'free',
      display_name: 'Free Plan',
      description: '15-minute delayed signals, perfect for learning',
      price_monthly: 0,
      price_yearly: 0,
      is_active: true,
      features: [
        '15-minute delayed signals',
        'Paper trading only',
        'Up to 5 watchlist symbols',
        '100 API requests/day',
        'Basic analytics',
      ],
    },
    {
      id: 'mock-starter-plan',
      name: 'starter',
      display_name: 'Starter Plan',
      description: 'Real-time signals and enhanced features for active traders',
      price_monthly: 19.99,
      price_yearly: 199.99,
      stripe_price_id_monthly: 'price_STARTER_MONTHLY',
      stripe_price_id_yearly: 'price_STARTER_YEARLY',
      is_active: true,
      features: [
        'Real-time signals',
        'Paper trading',
        'Up to 20 watchlist symbols',
        '1,000 API requests/day',
        'Advanced analytics',
        'Email alerts',
      ],
    },
    {
      id: 'mock-pro-plan',
      name: 'pro',
      display_name: 'Pro Plan',
      description: 'Full access with live trading and premium features',
      price_monthly: 49.99,
      price_yearly: 479.99,
      stripe_price_id_monthly: 'price_PRO_MONTHLY',
      stripe_price_id_yearly: 'price_PRO_YEARLY',
      is_active: true,
      features: [
        'Real-time signals',
        'Live trading (admin approval required)',
        'Unlimited watchlist symbols',
        '10,000 API requests/day',
        'Premium analytics',
        'Real-time alerts',
        'Backtesting tools',
        'Priority support',
      ],
    },
  ];
}

/**
 * Generate mock user data.
 */
export function generateMockUser(plan: 'free' | 'starter' | 'pro' = 'free') {
  return {
    id: 'mock-user-id',
    email: 'demo@example.com',
    full_name: 'Demo User',
    email_verified: true,
    mfa_enabled: false,
    role: 'user',
    paper_trading_approved: true,
    live_trading_approved: plan === 'pro',
    preferences: {},
    created_at: new Date(Date.now() - 30 * 86400000).toISOString(), // 30 days ago
    last_login_at: new Date().toISOString(),
  };
}

/**
 * Generate mock orders.
 */
export function generateMockOrders(count: number = 10) {
  const symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA'];
  const sides = ['buy', 'sell'];
  const statuses = ['filled', 'pending', 'canceled', 'partially_filled'];

  return Array.from({ length: count }, (_, i) => {
    const symbol = symbols[Math.floor(Math.random() * symbols.length)];
    const side = sides[Math.floor(Math.random() * sides.length)];
    const quantity = Math.floor(1 + Math.random() * 50);
    const price = 50 + Math.random() * 450;
    const status = statuses[Math.floor(Math.random() * statuses.length)];

    return {
      id: `mock-order-${i}`,
      user_id: 'mock-user-id',
      mode: 'paper',
      symbol,
      side,
      quantity,
      order_type: 'market',
      status,
      filled_quantity: status === 'filled' ? quantity : status === 'partially_filled' ? Math.floor(quantity / 2) : 0,
      filled_avg_price: status === 'filled' || status === 'partially_filled' ? price : null,
      broker_order_id: `mock-broker-${i}`,
      broker_name: 'alpaca',
      time_in_force: 'gtc',
      extended_hours: false,
      created_at: new Date(Date.now() - i * 3600000).toISOString(),
      updated_at: new Date(Date.now() - i * 3600000).toISOString(),
      filled_at: status === 'filled' ? new Date(Date.now() - i * 3600000).toISOString() : null,
    };
  });
}
