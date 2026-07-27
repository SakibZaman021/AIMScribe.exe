'use client';

/**
 * Doctor sign-in.
 *
 * New in v2. Previously the dashboard had no login at all: doctor_id and
 * hospital_id were free-text fields on the patient entry form, which meant a
 * consultation's attribution - whose it was, at which hospital - was whatever the
 * browser typed. For a record with medico-legal weight that is not defensible,
 * and the archive tree is hospital-first, so a wrong value misfiles it too.
 *
 * The session cookie set here is httpOnly, so JavaScript cannot read it, and
 * every recording grant is minted from it server-side.
 */

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const router = useRouter();
  const [doctorId, setDoctorId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ doctor_id: doctorId.trim(), password }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data.error || 'Sign in failed.');
        return;
      }
      router.push('/');
    } catch {
      setError('Could not reach the server. Check your connection.');
    } finally {
      setBusy(false);
      setPassword('');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow p-8 w-full max-w-sm">
        <h1 className="text-2xl font-bold text-gray-800">CMED</h1>
        <p className="text-sm text-gray-600 mt-1 mb-6">
          Sign in to record and prescribe.
        </p>

        {error && (
          <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-3 mb-4 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="doctorId" className="block text-sm font-medium text-gray-700 mb-1">
              Doctor ID
            </label>
            <input
              id="doctorId"
              name="doctorId"
              autoComplete="username"
              required
              value={doctorId}
              onChange={(e) => setDoctorId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
              placeholder="DR001"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={busy}
            className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-300"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="text-xs text-gray-500 mt-6">
          Your session lasts 12 hours. Sign out when you leave a shared consulting
          room.
        </p>
      </div>
    </div>
  );
}
