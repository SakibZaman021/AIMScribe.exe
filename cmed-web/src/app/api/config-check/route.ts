/**
 * GET /api/config-check - is this deployment configured?
 *
 * Reports whether each required variable is present and well-formed. It never
 * returns a value, a key, or any part of one: only booleans, lengths, and for
 * the doctor directory the identifiers it parsed.
 *
 * This exists because a misconfigured deployment is indistinguishable from a
 * working one from the outside. Every failure mode is deliberately silent -
 * authentication returns the same message whether the doctor does not exist or
 * the password is wrong, so that nobody can enumerate valid doctor IDs - and
 * that same design makes "the environment variable never arrived" look exactly
 * like "you typed the wrong password".
 */
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function present(name: string) {
  const value = process.env[name];
  return { set: Boolean(value), length: value ? value.length : 0 };
}

export async function GET() {
  const doctors = process.env.AIMS_DOCTORS;
  let directory: Record<string, unknown>;

  if (!doctors) {
    directory = { set: false, problem: 'AIMS_DOCTORS is not set in this environment' };
  } else {
    try {
      const parsed = JSON.parse(doctors);
      if (!Array.isArray(parsed)) {
        directory = { set: true, valid: false, problem: 'parsed, but is not an array' };
      } else {
        directory = {
          set: true,
          valid: true,
          length: doctors.length,
          count: parsed.length,
          // Identifiers only. Never the password hash.
          doctors: parsed.map((d: { doctor_id?: string; hospital_ids?: string[]; password?: string }) => ({
            doctor_id: d.doctor_id ?? '(missing)',
            hospital_ids: d.hospital_ids ?? [],
            password_format:
              typeof d.password === 'string' && d.password.split(':').length === 2
                ? 'salt:hash'
                : 'MALFORMED - expected salt:hash',
          })),
        };
      }
    } catch (error) {
      directory = {
        set: true,
        valid: false,
        length: doctors.length,
        startsWith: doctors.slice(0, 2),
        endsWith: doctors.slice(-2),
        problem: `not valid JSON: ${(error as Error).message}`,
        hint: 'Vercel stores the value literally. Surrounding quotes break JSON.parse.',
      };
    }
  }

  const grant = process.env.AIMS_GRANT_PRIVATE_KEY ?? '';
  const session = process.env.AIMS_SESSION_SECRET ?? '';

  return NextResponse.json({
    ok:
      Boolean(process.env.AIMS_DOCTORS) &&
      session.length >= 32 &&
      grant.includes('BEGIN PRIVATE KEY'),
    doctors: directory,
    grant_key: {
      set: Boolean(grant),
      length: grant.length,
      looks_like_pem: grant.includes('BEGIN PRIVATE KEY'),
      // A PEM pasted with \n escapes instead of real line breaks parses as one
      // line and fails at signing time, not at startup.
      has_real_newlines: grant.includes('\n'),
      has_escaped_newlines: grant.includes('\\n'),
    },
    session_secret: {
      ...present('AIMS_SESSION_SECRET'),
      long_enough: session.length >= 32,
    },
    webhook_secret: present('AIMSCRIBE_WEBHOOK_SECRET'),
    grant_issuer: process.env.AIMS_GRANT_ISSUER ?? '(not set)',
    grant_audience: process.env.AIMS_GRANT_AUDIENCE ?? '(not set)',
    backend_url: process.env.NEXT_PUBLIC_BACKEND_URL ?? '(not set)',
    recorder_ws: process.env.NEXT_PUBLIC_RECORDER_WS ?? '(default) ws://localhost:5050/ws',
  });
}
