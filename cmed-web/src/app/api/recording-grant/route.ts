/**
 * POST /api/recording-grant
 *
 * Issues the signed authorisation the AIMScribe agent needs before it will record.
 * The agent will not start without one, and only this route can produce one.
 *
 * There is no doctor login. The hospital belongs to the machine - an
 * administrator enrols each PC to one, and a PC does not move between hospitals.
 *
 * The doctor does not belong to the machine. A consulting room is shared and the
 * rota changes, so the page names the doctor for each consultation, chosen from
 * the register the agent supplies. That name is not trusted here: the backend
 * checks it against the hospital's register when the session opens and refuses a
 * doctor who is not credentialed to record there. Free text never reaches the
 * archive.
 *
 * This route still matters, because the agent refuses to record without a grant
 * - so a random page the doctor visits cannot start a recording, even though
 * this one no longer proves who is asking.
 *
 * Consent is required here, again on the agent, and again by a CHECK constraint
 * in the database.
 */
import { NextRequest, NextResponse } from 'next/server';
import { mintGrant, assertSafeIdentifier } from '@/lib/grant';

// Node runtime: grant signing uses Ed25519 via jose, and the private key must
// never be exposed to an edge deployment we do not control.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface GrantRequestBody {
  patient_ref?: string;
  doctor_id?: string;
  hospital_id?: string;
  consent_obtained?: boolean;
  consent_method?: string;
}

export async function POST(request: NextRequest) {
  let body: GrantRequestBody;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body.' }, { status: 400 });
  }

  if (!body.consent_obtained) {
    return NextResponse.json(
      { error: "Record the patient's consent before starting a recording." },
      { status: 400 }
    );
  }

  let patientRef: string;
  let doctorId = '';
  try {
    patientRef = assertSafeIdentifier(String(body.patient_ref ?? ''), 'patient_ref');
    // Optional: a PC with one regular doctor need not name one, and the agent
    // falls back to its enrolment.
    if (body.doctor_id) {
      doctorId = assertSafeIdentifier(String(body.doctor_id), 'doctor_id');
    }
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Invalid identifier.' },
      { status: 400 }
    );
  }

  try {
    // The hospital is left empty on purpose: this server does not know it and
    // must not guess. The agent fills it from its enrolment.
    const { grant, expiresIn } = await mintGrant({
      doctorId,
      doctorName: '',
      hospitalId: '',
      patientRef,
      consentObtained: true,
      consentMethod: String(body.consent_method ?? 'verbal_at_reception').slice(0, 64),
    });

    return NextResponse.json(
      { grant, expires_in: expiresIn },
      { headers: { 'Cache-Control': 'no-store' } }
    );
  } catch (error) {
    // The message may name the missing environment variable, which belongs in
    // the log and not in a response to the browser.
    console.error('[grant] mint failed:', error);
    return NextResponse.json(
      { error: 'Recording could not be authorised. Contact support.' },
      { status: 500 }
    );
  }
}
