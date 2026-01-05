'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { getCurrentUser, logout, getSessions, revokeSession, type User, type SessionInfo } from '@/lib/api/auth';
import { getErrorMessage } from '@/lib/api-client';

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadUser();
    loadSessions();
  }, []);

  const loadUser = async () => {
    try {
      const userData = await getCurrentUser();
      setUser(userData);
    } catch (error) {
      toast.error('Please sign in');
      router.push('/auth/login');
    } finally {
      setLoading(false);
    }
  };

  const loadSessions = async () => {
    try {
      const data = await getSessions();
      setSessions(data.sessions);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      toast.success('Logged out successfully');
      router.push('/');
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await revokeSession(sessionId);
      toast.success('Session revoked');
      await loadSessions();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-lg">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <h1 className="text-xl font-bold">Smart Stock Bot</h1>
          <Button variant="outline" onClick={handleLogout}>
            Sign out
          </Button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="max-w-4xl space-y-8">
          {/* User Info */}
          <div className="rounded-lg border p-6">
            <h2 className="mb-4 text-2xl font-bold">Welcome, {user.full_name || user.email}!</h2>
            <div className="space-y-2 text-sm">
              <p>
                <strong>Email:</strong> {user.email}
                {user.email_verified ? (
                  <span className="ml-2 text-green-600">✓ Verified</span>
                ) : (
                  <span className="ml-2 text-yellow-600">⚠ Not verified</span>
                )}
              </p>
              <p>
                <strong>MFA:</strong>{' '}
                {user.mfa_enabled ? (
                  <span className="text-green-600">Enabled</span>
                ) : (
                  <span className="text-muted-foreground">Disabled</span>
                )}
              </p>
              <p>
                <strong>Role:</strong> {user.role}
              </p>
              <p>
                <strong>Trading Access:</strong>{' '}
                {user.paper_trading_approved && 'Paper Trading '}
                {user.live_trading_approved && 'Live Trading'}
                {!user.paper_trading_approved && !user.live_trading_approved && 'None'}
              </p>
            </div>
          </div>

          {/* Active Sessions */}
          <div className="rounded-lg border p-6">
            <h2 className="mb-4 text-xl font-bold">Active Sessions</h2>
            <div className="space-y-3">
              {sessions.length === 0 ? (
                <p className="text-muted-foreground">No active sessions</p>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    className="flex items-center justify-between rounded-md border p-4"
                  >
                    <div>
                      <p className="font-medium">
                        {session.device_info.user_agent || 'Unknown device'}
                        {session.is_current && (
                          <span className="ml-2 text-xs text-green-600">(Current)</span>
                        )}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        IP: {session.device_info.ip_address || 'Unknown'}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Last used: {new Date(session.last_used_at).toLocaleString()}
                      </p>
                    </div>
                    {!session.is_current && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleRevokeSession(session.id)}
                      >
                        Revoke
                      </Button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="rounded-lg border p-6">
            <h2 className="mb-4 text-xl font-bold">Quick Actions</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Button variant="outline" className="h-auto flex-col items-start p-4">
                <span className="font-semibold">Enable MFA</span>
                <span className="text-xs text-muted-foreground">
                  Add extra security to your account
                </span>
              </Button>
              <Button variant="outline" className="h-auto flex-col items-start p-4">
                <span className="font-semibold">Change Password</span>
                <span className="text-xs text-muted-foreground">Update your password</span>
              </Button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
