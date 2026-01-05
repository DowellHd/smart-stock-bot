'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function VerifyEmailSentPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-8 text-center">
        <div className="space-y-4">
          <div className="text-6xl">📧</div>
          <h1 className="text-3xl font-bold tracking-tight">Check your email</h1>
          <p className="text-muted-foreground">
            We&apos;ve sent a verification link to your email address. Please check your inbox and
            click the link to verify your account.
          </p>
        </div>

        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Didn&apos;t receive the email? Check your spam folder or
          </p>
          <Button variant="outline" asChild>
            <Link href="/auth/login">Back to sign in</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
