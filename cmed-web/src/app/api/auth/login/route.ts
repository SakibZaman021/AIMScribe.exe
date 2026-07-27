/**
 * POST /api/auth/login   -  sign a doctor in
 * DELETE /api/auth/login -  sign out
 * GET /api/auth/login    -  who am I
 *
 * Minimal but real: scrypt-verified credentials, a signed httpOnly session
 * cookie, and no identity ever taken from the browser afterwards.
 *
 * When the hospital's own identity provider is available, replace
 * `authenticateDoctor` in src/lib/session.ts with the OIDC callback. Nothing else
 * in the application needs to change.
 */
import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import {
  SESSION_COOKIE,
  authenticateDoctor,
  createSession,
  readSession,
  sessionCookieOptions,
} from '@/lib/session';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  let body: { doctor_id?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body.' }, { status: 400 });
  }

  const doctorId = String(body.doctor_id ?? '').trim();
  const password = String(body.password ?? '');

  if (!doctorId || !password) {
    return NextResponse.json(
      { error: 'Enter your doctor ID and password.' },
      { status: 400 }
    );
  }

  const doctor = await authenticateDoctor(doctorId, password);
  if (!doctor) {
    // One message for both cases: telling the caller which was wrong lets them
    // enumerate valid doctor IDs.
    return NextResponse.json(
      { error: 'Incorrect doctor ID or password.' },
      { status: 401 }
    );
  }

  const token = await createSession(doctor);
  cookies().set(SESSION_COOKIE, token, sessionCookieOptions());

  return NextResponse.json({
    doctor_id: doctor.doctorId,
    doctor_name: doctor.doctorName,
    hospital_ids: doctor.hospitalIds,
  });
}

export async function GET() {
  const session = await readSession();
  if (!session) {
    return NextResponse.json({ authenticated: false }, { status: 401 });
  }
  return NextResponse.json({
    authenticated: true,
    doctor_id: session.doctorId,
    doctor_name: session.doctorName,
    hospital_ids: session.hospitalIds,
  });
}

export async function DELETE() {
  cookies().set(SESSION_COOKIE, '', { ...sessionCookieOptions(), maxAge: 0 });
  return NextResponse.json({ signed_out: true });
}
