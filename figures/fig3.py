"""Figure 3 - chain of custody, including what quarantine actually does."""
from genfigs import Fig, ACCENT

f = Fig(1180, 800,
        "Chain of custody. Each session carries an Ed25519-signed hash chain whose "
        "entries embed the previous entry's digest. A segment is encrypted and uploaded "
        "automatically, then read back and re-hashed by the server; a mismatch "
        "quarantines the session, raises a critical alert and withholds the purge "
        "receipt, so both copies are kept and a human decides. The archived WAV is "
        "bit-identical to capture and is the hashed evidence; the recognition rendition "
        "is derived from it and never hashed. Local audio is deleted only on a purge "
        "receipt.")

# ============ A · the chain ============
f.text(40, 34, "A · THE SESSION HASH CHAIN — one per consultation, signed by the device key",
       size=12, bold=True)

CH = [("open", "doctor · clinic", "patient · consent"),
      ("segment 1", "audio SHA-256", "bytes · level"),
      ("segment 2", "audio SHA-256", "bytes · level"),
      ("pause", "reason", "authorised by"),
      ("resume", "resumed at", ""),
      ("segment 3", "audio SHA-256", "is_final"),
      ("close", "close reason", "entry count")]
x = 40
for i, (t, s1, s2) in enumerate(CH):
    lines = [(t, 11.5, True), (s1, 9)] + ([(s2, 9)] if s2 else [])
    f.box(x, 52, 140, 64, lines)
    if i:
        f.path(f"M{x-20},84 L{x-6},84")
    x += 160
f.text(40, 138, "Every entry embeds the previous entry’s digest and carries its own "
                "signature, so a removed, reordered or edited entry is detectable. "
                "The backend verifies the complete chain at close.", size=10.5)

# ============ B · the audio ============
f.text(40, 186, "B · WHAT HAPPENS TO THE AUDIO — uploaded automatically, deleted only "
                "by proof", size=12, bold=True)

f.box(40, 210, 190, 62, [("Sealed on the PC", 11.5, True),
                         ("AES-256-GCM", 9.5), ("key wrapped by DPAPI", 9.5)])
f.box(272, 210, 172, 62, [("Object store", 11.5, True),
                          ("presigned PUT", 9.5), ("no human step", 9.5)])
f.box(486, 210, 210, 62, [("Server reads it back", 11.5, True),
                          ("re-hashes and compares", 9.5)])
f.box(750, 210, 200, 62, [("Archived WAV", 11.5, True),
                          ("bit-identical to capture", 9.5),
                          ("this is the evidence", 9.5)], sw=2.2)

f.path("M230,241 L266,241")
f.path("M444,241 L480,241")
f.path("M696,241 L744,241")
f.label(720, 233, "match", size=9.5, slot=(700, 744))

f.path("M591,272 L591,318", color=ACCENT, sw=2)
f.box(486, 318, 210, 58, [("QUARANTINED", 11.5, True, ACCENT),
                          ("critical alert raised", 9.5),
                          ("no purge receipt issued", 9.5)],
      color=ACCENT, sw=1.8)
f.text(601, 300, "mismatch", size=9.5, color=ACCENT)

f.path("M850,272 L850,318", color=ACCENT, sw=1.8, dash="6 4")
f.box(750, 318, 200, 58, [("ASR rendition", 11, True, ACCENT),
                          ("derived · 16 kHz", 9.5),
                          ("never hashed", 9.5)], color=ACCENT, sw=1.6, dash="6 4")

f.text(40, 400, "The upload is automatic and needs no human. Verification happens on "
                "arrival, not before it — so a bad segment reaches storage, and is then "
                "caught there.", size=10.5)
f.text(40, 416, "What a mismatch withholds is the purge receipt. Both copies survive, "
                "the session is never archived, and an operator decides what happens "
                "next.", size=10.5)

# ============ C · deletion ============
f.text(40, 470, "C · WHEN LOCAL AUDIO MAY BE DELETED", size=12, bold=True)

ST = [(40, "PENDING"), (290, "COMMITTED"), (540, "RECEIPTED"), (790, "PURGED")]
for i, (sx, name) in enumerate(ST):
    f.box(sx, 500, 170, 48, [(name, 12, True)], rx=24,
          sw=2.2 if name == "PURGED" else 1.5)
    if i:
        f.path(f"M{sx-80},524 L{sx-6},524")

f.label(250, 505, "server verified", size=9, slot=(212, 288))
f.label(250, 516, "the hash", size=9, slot=(212, 288))
f.label(500, 505, "archive copy", size=9, slot=(462, 538))
f.label(500, 516, "verified", size=9, slot=(462, 538))
f.label(750, 505, "24 h grace", size=9, slot=(712, 788))
f.label(750, 516, "elapsed", size=9, slot=(712, 788))

f.path("M375,548 L375,592", color=ACCENT, sw=2)
f.box(290, 592, 200, 46, [("QUARANTINED", 11.5, True, ACCENT)], rx=23,
      color=ACCENT, sw=1.8)
f.text(385, 574, "hash mismatch", size=9, color=ACCENT)
f.text(500, 620, "never deleted automatically — a human decides, and until they do "
                 "both copies are kept", size=10)

f.text(40, 690, "A purge receipt is the only authority to delete audio.", size=12,
       bold=True, color=ACCENT)
f.text(40, 708, "Nothing on the consulting-room PC is removed until the server has "
                "proved, by re-hashing the stored bytes, that an archived copy exists "
                "and matches.", size=11)
f.text(40, 724, "A quarantined session therefore holds its local audio indefinitely. "
                "That is deliberate: the disk fills before the evidence disappears.",
       size=11)

f.write("fig3_chain_of_custody.svg")
