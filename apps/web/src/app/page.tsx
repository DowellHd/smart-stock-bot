import Link from 'next/link';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="max-w-5xl w-full">
        <div className="text-center space-y-8">
          <h1 className="text-6xl font-bold tracking-tight">
            Smart Stock Bot
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Production-ready stock trading and portfolio management platform
            with AI-powered insights and real-time market data.
          </p>

          <div className="flex gap-4 justify-center mt-8">
            <Link
              href="/auth/signup"
              className="inline-flex items-center justify-center rounded-md bg-primary px-8 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Get Started
            </Link>
            <Link
              href="/auth/login"
              className="inline-flex items-center justify-center rounded-md border border-input bg-background px-8 py-3 text-sm font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              Sign In
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16">
            <div className="border rounded-lg p-6 space-y-2">
              <div className="text-2xl font-semibold">Secure Trading</div>
              <p className="text-muted-foreground">
                Multi-factor authentication, encrypted data, and industry-standard security practices.
              </p>
            </div>
            <div className="border rounded-lg p-6 space-y-2">
              <div className="text-2xl font-semibold">Real-Time Data</div>
              <p className="text-muted-foreground">
                Live market quotes, interactive charts, and instant order execution.
              </p>
            </div>
            <div className="border rounded-lg p-6 space-y-2">
              <div className="text-2xl font-semibold">Smart AI Bot</div>
              <p className="text-muted-foreground">
                AI-powered trade suggestions with backtesting and risk management.
              </p>
            </div>
          </div>

          <div className="mt-12 p-4 bg-warning/10 border border-warning rounded-lg">
            <p className="text-sm text-warning-foreground">
              <strong>Disclaimer:</strong> Trading stocks involves risk. This platform is for educational
              and informational purposes only. Not financial advice.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
