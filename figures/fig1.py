"""Figure 1 - system architecture."""
from genfigs import Fig, ACCENT

f = Fig(1220, 700,
        "AIMScribe system architecture. A partner web page on the consulting-room PC "
        "sends a trigger and a prescription flag to the AIMScribe agent over a loopback "
        "WebSocket on the same machine. The agent captures, segments, encrypts, "
        "hash-chains and uploads audio; the backend verifies every segment by reading it "
        "back and re-hashing it; an archive worker inside AIMS LAB dials outward to "
        "collect verified sessions. No partner system connects to AIMS LAB.")

# ---- zone frames -------------------------------------------------------
f.rect(40, 66, 380, 590, rx=10, sw=1.4, dash="6 4", op="0.5")
f.rect(580, 66, 300, 590, rx=10, sw=1.4, dash="6 4", op="0.5")
f.rect(940, 66, 240, 590, rx=10, sw=1.4, dash="6 4", op="0.5")

f.text(40, 54, "CONSULTING ROOM — one of 14", size=12, bold=True)
f.text(580, 54, "AIMS LAB BACKEND", size=12, bold=True)
f.text(940, 54, "AIMS LAB SERVER", size=12, bold=True)

# ---- consulting room ---------------------------------------------------
f.box(60, 92, 138, 56, [("Speakerphone", 12, True), ("48 kHz mic array", 9.5)])
f.box(214, 88, 186, 64, [("Partner web page", 12, True),
                         ("CMED · Aalo · Amader Susastho", 9),
                         ("sends trigger + flag", 9)])

f.rect(60, 188, 340, 448, rx=8, sw=2)
f.text(230, 210, "AIMScribe_Agent.exe", size=12.5, bold=True, anchor="middle")
f.text(230, 226, "enrolled to exactly one clinic", size=9.5, anchor="middle")

f.box(80, 240, 300, 42, [("Capture · native rate, no resample", 10.5)])
f.box(80, 296, 300, 42, [("Segmenter · 30–60 s on a silent gap", 10.5)])
f.box(80, 352, 300, 42, [("Spool · AES-256-GCM, 40 GB", 10.5)])
f.box(80, 408, 300, 42, [("Hash chain · Ed25519 per session", 10.5)])
f.box(80, 464, 300, 42, [("Uploader · store and forward", 10.5)])
f.box(80, 552, 300, 56, [("Recording overlay", 11.5, True),
                         ("Stop · Pause · all doctor messages", 9.5)])

for y0 in (282, 338, 394, 450):
    f.path(f"M230,{y0} L230,{y0+14}")

f.path("M129,148 L129,232")                       # speakerphone -> capture
f.path("M307,152 L307,188", color=ACCENT, sw=2.4)  # page -> agent (the integration)

# ---- backend -----------------------------------------------------------
f.box(600, 140, 260, 62, [("PostgreSQL", 12, True),
                          ("sessions · devices · audit log", 9.5)])
f.box(600, 300, 260, 62, [("API", 12, True),
                          ("grants · sessions · verification", 9.5)])
f.box(600, 460, 260, 62, [("Object store", 12, True),
                          ("encrypted segments", 9.5)])

f.path("M420,331 L594,331")                       # agent -> API
f.path("M420,491 L594,491")                       # agent -> object store
f.path("M726,300 L726,208")                       # API -> db
f.path("M700,362 L700,454")                       # API -> object store

f.label(500, 322, "HTTPS · device token", slot=(422, 578))
f.label(500, 482, "presigned PUT", slot=(422, 578))
f.text(736, 258, "reads · writes", size=9.5)
f.text(710, 400, "reads back", size=9.5)
f.text(710, 414, "and re-hashes", size=9.5)

# ---- AIMS LAB server ---------------------------------------------------
f.box(960, 300, 200, 62, [("Archive worker", 12, True),
                          ("no inbound port", 9.5)])
f.box(960, 460, 200, 62, [("Archive volume", 12, True),
                          ("raw WAV, never re-encoded", 9.5)])
f.box(960, 570, 200, 52, [("ASR + NER", 11, True),
                          ("out of scope", 9.5)], dash="5 4", sw=1.3)

f.path("M954,331 L866,331")                       # worker -> API (outbound)
f.path("M1060,362 L1060,454")
f.path("M1060,522 L1060,564", dash="5 4")
f.label(910, 322, "polls", slot=(884, 936))
f.text(1070, 412, "verified WAV", size=9.5)

# ---- the claim ---------------------------------------------------------
f.text(40, 682, "The red arrow is the entire partner integration: a WebSocket to "
                "127.0.0.1 on the doctor’s own PC.", size=11.5, bold=True,
       color=ACCENT)
f.text(40, 697, "No partner system connects to AIMS LAB. Partners hold no key, store no "
                "audio, and expose no endpoint to us.", size=11)

f.write("fig1_architecture.svg")
