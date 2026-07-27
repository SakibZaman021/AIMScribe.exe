/**
 * GET /api/doctors - the register, for the selector on the dashboard.
 *
 * Names and identifiers only. There are no credentials to leak because there
 * are no credentials: doctors are selected here, not authenticated.
 */
import { NextResponse } from 'next/server';
import { doctorRegister } from '@/lib/doctors';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const doctors = doctorRegister();
  return NextResponse.json(
    { doctors, count: doctors.length },
    { headers: { 'Cache-Control': 'no-store' } }
  );
}
