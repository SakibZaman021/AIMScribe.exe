/**
 * POST /api/recording-grant
 *
 * Issues the signed authorisation the AIMScribe agent needs before it will record.
 *
 * Everything that identifies who is recording comes from the server session, not
 * from the request body. The browser supplies only the patient reference and the
 * consent record; doctor and hospital are taken from the authenticated session and
 * checked against that doctor's permitted hospitals.
 *
 * That inversion is the point. The agent will not start without a grant, and only
 * this route can produce one.
 */
import { NextRequest, NextResponse } from 'next/server';
import { mintGrant, assertSafeIdentifier } from '@/lib/grant';
import { readSession } from '@/lib/session';

// Node runtime: grant signing uses Ed25519 via jose, and the private key must
// never be exposed to an edge deployment we do not control.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface GrantRequestBody {
  patient_ref?: string;
  hospital_id?: string;
  consent_obtained?: boolean;
  consent_method?: string;
}

export async function POST(request: NextRequest) {
  const session = await readSession();
  if (!session) {
    return NextResponse.json(
      { error: 'Not signed in. Please sign in again.' },
      { status: 401 }
    );
  }

  let body: GrantRequestBody;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body.' }, { status: 400 });
  }

  // Consent is a hard precondition, checked here, again on the agent, and again
  // by a CHECK constraint in the database.
  if (!body.consent_obtained) {
    return NextResponse.json(
      { error: 'Record the patient\'s consent before starting a recording.' },
      { status: 400 }
    );
  }

  let patientRef: string;
  try {
    patientRef = assertSafeIdentifier(String(body.patient_ref ?? ''), 'patient_ref');
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Invalid patient reference.' },
      { status: 400 }
    );
  }

  // A doctor may consult at more than one hospital, so the browser may choose -
  // but only from the hospitals this doctor is credentialed at. The archive tree
  // is hospital-first, so an unchecked value here misfiles the record permanently.
  const requested = String(body.hospital_id ?? '') || session.hospitalId;
  if (!session.hospitalIds.includes(requested)) {
    console.warn(
      `[grant] doctor ${session.doctorId} requested hospital ${requested}, ` +
      `which is not in their permitted list`
    );
    return NextResponse.json(
      { error: 'You are not registered to consult at that hospital.' },
      { status: 403 }
    );
  }

  try {
    const { grant, expiresIn } = await mintGrant({
      doctorId: session.doctorId,
      doctorName: session.doctorName,
      hospitalId: requested,
      patientRef,
      consentObtained: true,
      consentMethod: String(body.consent_method ?? 'verbal_at_reception').slice(0, 64),
    });

    return NextResponse.json(
      {
        grant,
        expires_in: expiresIn,
        doctor_id: session.doctorId,
        hospital_id: requested,
      },
      { headers: { 'Cache-Control': 'no-store' } }
    );
  } catch (error) {
    // The message may name the missing environment variable, which belongs in the
    // log and not in a response to the browser.
    console.error('[grant] mint failed:', error);
    return NextResponse.json(
      { error: 'Recording could not be authorised. Contact support.' },
      { status: 500 }
    );
  }
}
