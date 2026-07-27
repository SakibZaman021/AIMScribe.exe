/**
 * Doctor sessions.
 *
 * A signed, httpOnly cookie. The dashboard previously kept the doctor's identity
 * and the patient's demographics in `sessionStorage`, where any cross-site
 * scripting flaw could read them and where the values were freely editable by the
 * user. Identity now lives server-side and the browser only holds an opaque,
 * signed token it cannot forge or modify.
 *
 * `authenticateDoctor` is the single seam for a real identity provider. It
 * currently checks a scrypt-hashed credential list from the environment, which is
 * genuine authentication but not a substitute for the hospital's own directory.
 * Replace that one function with an OIDC callback and everything else still holds.
 */
import { SignJWT, jwtVerify } from 'jose';
import { cookies } from 'next/headers';
import { scryptSync, timingSafeEqual, randomBytes } from 'crypto';

export const SESSION_COOKIE = 'cmed_session';
const SESSION_HOURS = 12;

export interface DoctorSession {
  doctorId: string;
  doctorName: string;
  hospitalId: string;
  /** Hospitals this doctor may work at. A grant is refused for anything else. */
  hospitalIds: string[];
}

function secret(): Uint8Array {
  const value = process.env.AIMS_SESSION_SECRET;
  if (!value || value.length < 32) {
    throw new Error('AIMS_SESSION_SECRET must be set to at least 32 characters.');
  }
  return new TextEncoder().encode(value);
}

// ============================================================
// Session cookie
// ============================================================

export async function createSession(doctor: DoctorSession): Promise<string> {
  return new SignJWT({
    doctor_name: doctor.doctorName,
    hospital_id: doctor.hospitalId,
    hospital_ids: doctor.hospitalIds,
  })
    .setProtectedHeader({ alg: 'HS256' })
    .setSubject(doctor.doctorId)
    .setIssuedAt()
    .setExpirationTime(`${SESSION_HOURS}h`)
    .sign(secret());
}

export async function readSession(): Promise<DoctorSession | null> {
  const token = cookies().get(SESSION_COOKIE)?.value;
  if (!token) return null;

  try {
    const { payload } = await jwtVerify(token, secret());
    return {
      doctorId: String(payload.sub),
      doctorName: String(payload.doctor_name ?? ''),
      hospitalId: String(payload.hospital_id ?? ''),
      hospitalIds: Array.isArray(payload.hospital_ids)
        ? (payload.hospital_ids as string[])
        : [],
    };
  } catch {
    // Expired or tampered with. Treat exactly the same as no session at all.
    return null;
  }
}

export function sessionCookieOptions() {
  return {
    httpOnly: true,          // unreadable from JavaScript, so XSS cannot steal it
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const, // blocks cross-site use while allowing normal navigation
    path: '/',
    maxAge: SESSION_HOURS * 3600,
  };
}

// ============================================================
// Credential check - the seam for a real identity provider
// ============================================================

interface DoctorRecord {
  doctor_id: string;
  name: string;
  hospital_ids: string[];
  /** scrypt as "salt_hex:hash_hex". Generate with scripts/hash-password.mjs. */
  password: string;
}

function doctorDirectory(): DoctorRecord[] {
  const raw = process.env.AIMS_DOCTORS;
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    console.error('[auth] AIMS_DOCTORS is not valid JSON');
    return [];
  }
}

function verifyPassword(supplied: string, stored: string): boolean {
  const [saltHex, hashHex] = String(stored).split(':');
  if (!saltHex || !hashHex) return false;

  const expected = Buffer.from(hashHex, 'hex');
  const actual = scryptSync(supplied, Buffer.from(saltHex, 'hex'), expected.length);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

export async function authenticateDoctor(
  doctorId: string,
  password: string
): Promise<DoctorSession | null> {
  const record = doctorDirectory().find((d) => d.doctor_id === doctorId);

  // Hash regardless of whether the doctor exists, so response timing does not
  // reveal which identifiers are valid.
  const stored = record?.password ?? `${randomBytes(16).toString('hex')}:${'00'.repeat(64)}`;
  const ok = verifyPassword(password, stored);

  if (!record || !ok) return null;

  return {
    doctorId: record.doctor_id,
    doctorName: record.name,
    hospitalId: record.hospital_ids[0] ?? '',
    hospitalIds: record.hospital_ids ?? [],
  };
}
