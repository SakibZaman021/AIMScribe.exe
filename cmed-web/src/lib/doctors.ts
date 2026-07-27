/**
 * The doctor register.
 *
 * There is no login: doctors are selected, not authenticated. This list exists
 * so that the selection is constrained to real people rather than free text.
 *
 * That distinction matters more than it sounds. Without it, `doctor_id` is
 * whatever the browser sends, and a live database already shows what that
 * produces: DR001, DR_DEMO_001, DR_TEST_001, DR_DIAG_001, DR003 - five
 * "doctors", no register, and an archive tree with a folder for each. The
 * archive is filed by doctor, so a typo creates a folder that nobody will ever
 * look in again.
 *
 * Format, comma separated:
 *     AIMS_DOCTORS=DR001:Dr Sakib Zaman,DR002:Dr Ayesha Rahman
 *
 * Deliberately not JSON. A JSON blob in a hosting dashboard is easy to break
 * with a stray quote and gives no error anyone can act on.
 *
 * What this does NOT do is prove who is at the keyboard. Anyone who can open
 * the page can pick any name on the list, and the recording will carry it. If
 * attribution ever has to hold up - a complaint, an audit, a dispute about what
 * was said - replace this with the hospital's identity provider. The seam is
 * `resolveDoctor` and nothing else needs to change.
 */

export interface Doctor {
  doctor_id: string;
  name: string;
}

const ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

export function doctorRegister(): Doctor[] {
  const raw = process.env.AIMS_DOCTORS ?? '';
  if (!raw.trim()) return [];

  return raw
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [id, ...rest] = entry.split(':');
      return { doctor_id: (id ?? '').trim(), name: rest.join(':').trim() };
    })
    .filter((d) => {
      if (!ID_PATTERN.test(d.doctor_id)) {
        console.warn(`[doctors] ignoring malformed entry: ${JSON.stringify(d.doctor_id)}`);
        return false;
      }
      return true;
    })
    .map((d) => ({ doctor_id: d.doctor_id, name: d.name || d.doctor_id }));
}

/**
 * Resolve a submitted doctor_id against the register.
 *
 * An empty register means the deployment is unconfigured. It returns null
 * rather than waving the request through: a recording nobody can attribute is
 * worse than a recording that did not start, because the failure is silent and
 * only discovered when someone needs the audio.
 */
export function resolveDoctor(doctorId: string): Doctor | null {
  const register = doctorRegister();
  if (register.length === 0) {
    console.error('[doctors] AIMS_DOCTORS is not set - no recording can be attributed');
    return null;
  }
  return register.find((d) => d.doctor_id === doctorId) ?? null;
}
