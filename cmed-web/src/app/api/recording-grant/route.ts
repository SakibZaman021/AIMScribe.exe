/**
 * POST /api/recording-grant
 *
 * Issues the signed authorisation the AIMScribe agent needs before it will record.
 * The agent will not start without one, and only this route can produce one.
 *
 * There is no doctor login. The doctor is selected on the page and checked
 * against the register in `AIMS_DOCTORS`, so the value is a real person rather
 * than free text - but it is a selection, not proof of who is at the keyboard.
 *
 * Two things still constrain a recording, and neither is in the browser's gift:
 *
 *   hospital  The agent cross-checks the grant's hospital against the hospital
 *             its device was enrolled at (session_controller.py) and raises an
 *             integrity alert on mismatch. A page cannot file a consultation
 *             under a hospital the machine does not belong to.
 *
 *   consent   Required here, again on the agent, and again by a CHECK
 *             constraint in the database.
 */
import { NextRequest, NextResponse } from 'next/server';
import { mintGrant, assertSafeIdentifier } from '@/lib/grant';
import { resolveDoctor } from '@/lib/doctors';

// Node runtime: grant signing uses Ed25519 via jose, and the private key must
// never be exposed to an edge deployment we do not control.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface GrantRequestBody {
  doctor_id?: string;
  patient_ref?: string;
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

  const doctor = resolveDoctor(String(body.doctor_id ?? '').trim());
  if (!doctor) {
    return NextResponse.json(
      { error: 'Select a doctor from the list before starting a recording.' },
      { status: 400 }
    );
  }

  if (!body.consent_obtained) {
    return NextResponse.json(
      { error: "Record the patient's consent before starting a recording." },
      { status: 400 }
    );
  }

  let patientRef: string;
  let hospitalId: string;
  try {
    patientRef = assertSafeIdentifier(String(body.patient_ref ?? ''), 'patient_ref');
    // Reaches a filesystem path on the archive volume, so it is validated to the
    // same standard as the patient reference.
    hospitalId = assertSafeIdentifier(String(body.hospital_id ?? ''), 'hospital_id');
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Invalid identifier.' },
      { status: 400 }
    );
  }

  try {
    const { grant, expiresIn } = await mintGrant({
      doctorId: doctor.doctor_id,
      doctorName: doctor.name,
      hospitalId,
      patientRef,
      consentObtained: true,
      consentMethod: String(body.consent_method ?? 'verbal_at_reception').slice(0, 64),
    });

    return NextResponse.json(
      {
        grant,
        expires_in: expiresIn,
        doctor_id: doctor.doctor_id,
        hospital_id: hospitalId,
      },
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
