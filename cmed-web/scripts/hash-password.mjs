/**
 * Generate a scrypt password hash for AIMS_DOCTORS.
 *
 *   node scripts/hash-password.mjs "the password"
 *
 * Prints "salt:hash". Put that in the doctor's `password` field. The plaintext is
 * never stored anywhere, and each run produces a different salt.
 */
import { scryptSync, randomBytes } from 'crypto';

const password = process.argv[2];

if (!password) {
  console.error('Usage: node scripts/hash-password.mjs "the password"');
  process.exit(1);
}

if (password.length < 12) {
  console.error('Refusing: use at least 12 characters for a clinical account.');
  process.exit(1);
}

const salt = randomBytes(16);
const hash = scryptSync(password, salt, 64);

console.log(`${salt.toString('hex')}:${hash.toString('hex')}`);
console.error('\nAdd to AIMS_DOCTORS, for example:');
console.error(JSON.stringify([{
  doctor_id: 'DR001',
  name: 'Dr Example',
  hospital_ids: ['HOSP001'],
  password: `${salt.toString('hex')}:${hash.toString('hex')}`,
}]));
