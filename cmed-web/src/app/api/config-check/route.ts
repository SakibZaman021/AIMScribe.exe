/**
 * GET /api/config-check - is this deployment configured?
 *
 * Reports whether each required variable is present and well-formed. It never
 * returns a value, a key, or any part of one.
 *
 * This exists because a misconfigured deployment is indistinguishable from a
 * working one from the outside: recording simply refuses to start, with a
 * message that reads like user error.
 */
import { NextResponse } from 'next/server';
import { doctorRegister } from '@/lib/doctors';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const grant = process.env.AIMS_GRANT_PRIVATE_KEY ?? '';
  const webhook = process.env.AIMSCRIBE_WEBHOOK_SECRET ?? '';
  const register = doctorRegister();

  return NextResponse.json({
    ok: register.length > 0 && grant.includes('BEGIN PRIVATE KEY'),

    doctors: {
      configured: register.length > 0,
      count: register.length,
      // Identifiers and names only. There are no credentials here to leak:
      // doctors are selected, not authenticated.
      register: register,
      note:
        register.length === 0
          ? 'AIMS_DOCTORS is not set. No recording can be attributed to anyone.'
          : 'Format: DR001:Dr Name,DR002:Dr Other',
    },

    grant_key: {
      set: Boolean(grant),
      length: grant.length,
      looks_like_pem: grant.includes('BEGIN PRIVATE KEY'),
      // A PEM pasted with \n escapes instead of real line breaks parses as one
      // line and fails when the first grant is signed, not at startup.
      has_real_newlines: grant.includes('\n'),
      has_escaped_newlines: grant.includes('\\n'),
    },

    webhook_secret: { set: Boolean(webhook), length: webhook.length },

    grant_issuer: process.env.AIMS_GRANT_ISSUER ?? '(default) cmed',
    grant_audience: process.env.AIMS_GRANT_AUDIENCE ?? '(default) aimscribe-recorder',
    backend_url: process.env.NEXT_PUBLIC_BACKEND_URL ?? '(not set)',
    recorder_ws: process.env.NEXT_PUBLIC_RECORDER_WS ?? '(default) ws://localhost:5050/ws',
    hospital_id: process.env.NEXT_PUBLIC_HOSPITAL_ID ?? '(default) HOSP001',
  });
}
