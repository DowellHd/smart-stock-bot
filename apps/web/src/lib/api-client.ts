/**
 * API client for making requests to the backend.
 * Handles authentication, request/response interceptors, error handling, and demo mode.
 */
import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import {
  generateMockSignals,
  generateMockPortfolio,
  generateMockOHLCV,
  generateMockQuote,
  generateMockPlans,
  generateMockUser,
  generateMockOrders,
} from './mock-data';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1';
const IS_DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';

class APIClient {
  private client: AxiosInstance;
  private isDemoMode: boolean;

  constructor() {
    this.isDemoMode = IS_DEMO_MODE;

    this.client = axios.create({
      baseURL: `${API_URL}${API_PREFIX}`,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true, // Important for cookies (refresh tokens)
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor - handle demo mode and auth
    this.client.interceptors.request.use(
      async (config) => {
        // Demo mode: intercept and return mock data
        if (this.isDemoMode) {
          const mockResponse = await this.handleDemoRequest(config);
          if (mockResponse) {
            // Return a rejected promise with mock response attached
            // This will be caught by response interceptor
            return Promise.reject({
              config,
              response: {
                data: mockResponse,
                status: 200,
                statusText: 'OK',
                headers: {},
                config,
              },
              isAxiosError: true,
              toJSON: () => ({}),
              name: 'MockResponse',
              message: 'Demo mode mock response',
            });
          }
        }

        // Production mode: add access token from localStorage
        const accessToken = localStorage.getItem('access_token');
        if (accessToken) {
          config.headers.Authorization = `Bearer ${accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - handle demo mode, token refresh, and errors
    this.client.interceptors.response.use(
      (response) => response,
      async (error: any) => {
        // Handle demo mode mock responses
        if (this.isDemoMode && error.name === 'MockResponse') {
          return Promise.resolve(error.response);
        }

        // Production mode: handle 401 and token refresh
        const originalRequest: any = error.config;

        // If 401 and not already retried, try to refresh token
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            // Attempt token refresh
            const response = await axios.post(
              `${API_URL}${API_PREFIX}/auth/refresh`,
              {},
              { withCredentials: true }
            );

            const { access_token } = response.data;
            localStorage.setItem('access_token', access_token);

            // Retry original request with new token
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
            return this.client(originalRequest);
          } catch (refreshError) {
            // Refresh failed - redirect to login
            localStorage.removeItem('access_token');
            if (typeof window !== 'undefined') {
              window.location.href = '/auth/login';
            }
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Handle demo mode requests and return mock data.
   */
  private async handleDemoRequest(config: InternalAxiosRequestConfig): Promise<any> {
    const url = config.url || '';
    const method = config.method?.toLowerCase();

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 300 + Math.random() * 700));

    // Auth endpoints
    if (url.includes('/auth/login') && method === 'post') {
      const plan = 'free'; // Demo users get free plan
      return {
        access_token: 'demo_token_' + Date.now(),
        token_type: 'bearer',
        expires_in: 900,
        user: generateMockUser(plan),
        requires_mfa: false,
      };
    }

    if (url.includes('/auth/me')) {
      return generateMockUser('free');
    }

    // Billing endpoints
    if (url.includes('/billing/plans')) {
      return generateMockPlans();
    }

    if (url.includes('/billing/subscription')) {
      return {
        id: 'mock-subscription-id',
        plan: generateMockPlans()[0], // Free plan
        status: 'active',
        current_period_end: new Date(Date.now() + 30 * 86400000).toISOString(),
      };
    }

    // Market data endpoints
    if (url.includes('/market-data/quote/')) {
      const symbol = url.split('/').pop() || 'AAPL';
      return generateMockQuote(symbol);
    }

    if (url.includes('/market-data/quotes')) {
      // Parse symbols from query params
      const symbols = ['AAPL', 'GOOGL', 'MSFT'];
      return symbols.map((symbol) => generateMockQuote(symbol));
    }

    if (url.includes('/market-data/bars/')) {
      const symbol = url.split('/').pop()?.split('?')[0] || 'AAPL';
      return {
        symbol,
        timeframe: '1Day',
        bars: generateMockOHLCV(symbol, 100),
        count: 100,
      };
    }

    if (url.includes('/market-data/status')) {
      return {
        is_open: false,
        next_open: new Date(Date.now() + 12 * 3600000).toISOString(),
        next_close: new Date(Date.now() + 8 * 3600000).toISOString(),
        timestamp: new Date().toISOString(),
      };
    }

    // Signal endpoints
    if (url.includes('/signals/generate') && method === 'post') {
      const body = config.data ? JSON.parse(config.data) : {};
      const symbol = body.symbol || 'AAPL';
      return generateMockSignals(1, true)[0]; // Free users get delayed signals
    }

    if (url.includes('/signals/bulk') && method === 'post') {
      const body = config.data ? JSON.parse(config.data) : {};
      const symbols = body.symbols || ['AAPL', 'GOOGL', 'MSFT'];
      return {
        signals: generateMockSignals(symbols.length, true),
        total: symbols.length,
      };
    }

    if (url.includes('/signals/delay-info')) {
      return {
        plan: 'free',
        delay_minutes: 15,
        is_realtime: false,
        message: 'Signals are delayed by 15 minutes on your current plan',
      };
    }

    // Trading endpoints
    if (url.includes('/trading/portfolio')) {
      return generateMockPortfolio();
    }

    if (url.includes('/trading/positions')) {
      return generateMockPortfolio().positions;
    }

    if (url.includes('/trading/account')) {
      return generateMockPortfolio().account;
    }

    if (url.includes('/trading/orders') && method === 'get') {
      return generateMockOrders(10);
    }

    if (url.includes('/trading/orders') && method === 'post') {
      const body = config.data ? JSON.parse(config.data) : {};
      return {
        id: 'mock-order-new',
        ...body,
        status: 'pending',
        created_at: new Date().toISOString(),
      };
    }

    // Default: return null to proceed with actual request
    return null;
  }

  getInstance(): AxiosInstance {
    return this.client;
  }
}

export const apiClient = new APIClient().getInstance();

// Helper function to extract error message
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.message || error.response?.data?.detail || error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unknown error occurred';
}
