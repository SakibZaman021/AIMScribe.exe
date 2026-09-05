"""Figures 4-7: the diagrams the SRS still carried as mermaid source."""
from genfigs import Fig, ACCENT

# ---------------------------------------------------------------- Figure 4
f = Fig(1160, 300,
        "Trust boundaries. The partner page can only make claims; the agent proves "
        "its identity with a device token and an Ed25519 signature; the backend "
        "authorises with a signed grant and purge receipts.")
f.text(40, 34, "Nothing the page says is trusted on its own. Every claim is checked "
               "against a register the page cannot reach.", size=11)
zones = [(40, "UNTRUSTED", "Partner web page", "any page on the PC, really"),
         (460, "SEMI-TRUSTED · ENROLLED", "AIMScribe agent",
          "device token + private key"),
         (880, "TRUSTED · AIMS LAB", "AIMS LAB backend",
          "grant signing key + admin key")]
for x, tag, name, sub in zones:
    f.text(x, 62, tag, size=10, bold=True, color=ACCENT if x == 40 else "currentColor")
    f.box(x, 74, 240, 80, [(name, 12.5, True), (sub, 9.5)], sw=2 if x == 880 else 1.5)

f.path("M286,104 L454,104")
f.label(370, 96, "claims only — never trusted", size=9.5, slot=(292, 448))
f.path("M706,104 L874,104")
f.label(790, 96, "proves: token + signature", size=9.5, slot=(712, 868))
f.path("M874,138 L706,138")
f.label(790, 130, "authorises: grant + receipts", size=9.5, slot=(712, 868))

f.text(40, 200, "The agent is only semi-trusted: enrolment says the machine may record "
                "at all, not that any particular request to record is legitimate.",
       size=10.5)
f.text(40, 216, "That second question is the grant's, and the two must not be confused "
                "— an enrolled laptop with no grant check would record for any page "
                "the doctor visits.", size=10.5)
f.write("fig4_trust_boundaries.svg")

# ---------------------------------------------------------------- Figure 5
f = Fig(1120, 380,
        "Device enrolment lifecycle. A token is minted for a clinic, staged by the "
        "installer, redeemed at first start and replaced by a stored identity. An "
        "unreachable backend does not burn the token, and a crash before the identity "
        "is written returns the machine to the staged state.")
f.text(40, 34, "One token per laptop, consumed once. The machine receives its clinic; "
               "it never asserts one.", size=11)
ST = [(40, "Minted", "admin, per clinic"), (260, "Staged", "installer writes it"),
      (480, "Enrolled", "server issues identity"), (700, "Operating", "reads device.json"),
      (920, "Revoked", "credential cleared")]
for i, (x, name, sub) in enumerate(ST):
    f.box(x, 70, 150, 56, [(name, 12, True), (sub, 9)],
          sw=2 if name == "Revoked" else 1.5, rx=8)
    if i:
        f.path(f"M{x-70},98 L{x-6},98")
for cx, lbl in ((225, "install"), (445, "redeem"), (665, "first start"), (885, "revoke")):
    f.label(cx, 90, lbl, size=9, slot=(cx - 34, cx + 34))

f.box(260, 200, 150, 50, [("Expired", 11.5, True), ("TTL elapsed", 9)], rx=8,
      dash="5 4")
f.path("M335,126 L335,194")
f.text(345, 165, "unredeemed", size=9)

f.path("M480,126 L480,170 L410,170 L410,126", color=ACCENT, sw=1.8)
f.text(490, 166, "crashed before the identity file was written — the token may be "
                 "redeemed once more, by the same key, while the device has never "
                 "been seen", size=9.5, color=ACCENT)

f.text(40, 300, "A backend that is merely unreachable does not burn the token: it stays "
                "on disk and the agent retries at the next start.", size=10.5)
f.text(40, 316, "Burning it would strand a PC in another district with a credential "
                "that cannot be reissued remotely.", size=10.5)
f.write("fig5_enrolment_lifecycle.svg")

# ---------------------------------------------------------------- Figure 6
f = Fig(980, 420,
        "Grant minting moves to the AIMS LAB backend. The partner page sends five "
        "plain unsigned fields; the backend validates them against its own register "
        "and returns a short-lived single-use grant. The partner holds no key.")
f.text(40, 32, "The change that matters most to a partner: you hold no key, sign "
               "nothing, and expose no endpoint.", size=11, bold=True)
L = [(150, "Partner page"), (470, "AIMScribe agent"), (800, "AIMS LAB backend")]
for x, n in L:
    f.box(x - 110, 54, 220, 36, [(n, 12, True)])
    f.parts.append(f'<line x1="{x}" y1="90" x2="{x}" y2="366" stroke="currentColor" '
                   f'stroke-width="1" stroke-dasharray="3 4" opacity="0.5"/>')

def m(y, a, b, t, accent=False, bold=False):
    x0, x1 = L[a][0], L[b][0]
    d = 6 if x1 > x0 else -6
    c = ACCENT if accent else "currentColor"
    f.path(f"M{x0+d},{y} L{x1-d},{y}", color=c, sw=2 if accent else 1.5)
    f.label((x0 + x1) / 2, y - 7, t, size=10, bold=bold, color=c,
            slot=(min(x0, x1) + 4, max(x0, x1) - 4))

m(126, 0, 1, "trigger — 5 plain fields, unsigned", accent=True, bold=True)
m(170, 1, 2, "POST /grant/mint  (device token)")
f.box(680, 190, 240, 84, [("validate against OUR register", 10.5, True),
                          ("doctor exists and is active", 9),
                          ("doctor practises at that clinic", 9),
                          ("clinic matches THIS device", 9),
                          ("consent flag present", 9)])
m(300, 2, 1, "signed grant · 60 s · single use")
f.box(360, 320, 220, 40, [("verify against the pinned", 9.5),
                          ("backend public key, then record", 9.5)])
f.text(40, 396, "Before, the agent trusted what a page claimed. Now the backend checks "
                "every claim against a register the page cannot reach.", size=10.5)
f.write("fig6_grant_minting.svg")

# ---------------------------------------------------------------- Figure 7
f = Fig(1000, 360,
        "The consultation gate. A session begins un-armed; a stray trigger is refused "
        "and the recording continues. Only the prescription-built flag arms the gate, "
        "after which the next trigger hands over with no gap in capture.")
f.text(40, 32, "A new patient cannot end the current recording until that "
               "consultation's prescription has been built.", size=11, bold=True)
f.box(70, 120, 200, 64, [("RECORDING", 12.5, True), ("gate not armed", 9.5)], rx=10)
f.box(400, 120, 200, 64, [("ARMED", 12.5, True, ACCENT),
                          ("handover permitted", 9.5)], rx=10, color=ACCENT, sw=2)
f.box(730, 120, 200, 64, [("CLOSED", 12.5, True), ("reason recorded", 9.5)], rx=10,
      sw=2)

f.path("M276,152 L394,152", color=ACCENT, sw=2)
f.label(335, 144, "consultation_complete", size=9.5, color=ACCENT, slot=(280, 390))
f.path("M606,152 L724,152")
f.label(665, 144, "doctor presses Stop", size=9.5, slot=(610, 720))

f.path("M120,120 L120,86 L220,86 L220,120")
f.text(230, 90, "stray trigger — refused, 409 GATE_NOT_ARMED, recording continues",
       size=9.5)

f.path("M500,184 L500,232 L170,232 L170,184", color=ACCENT, sw=2)
f.text(510, 228, "next trigger — close this session, open the next on a parallel "
                 "thread, no gap", size=9.5, color=ACCENT)

f.text(40, 300, "Residual risk: a patient who leaves before a prescription is built "
                "never arms the gate, and the session stays open until the doctor "
                "stops it.", size=10.5)
f.text(40, 316, "That is why the overlay's Stop button is always visible.", size=10.5)
f.write("fig7_consultation_gate.svg")
