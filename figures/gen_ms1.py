"""
Manuscript Figure 1, redrawn.

The previous version drew the EHR-to-backend path struck out, because at the time
no such path existed. Clinical data now travels server to server, so the figure
asserts a channel where it used to assert an absence. A right-hand corridor is
kept clear so that channel can run the height of the figure without crossing the
workstation.
"""
from genfigs import Fig, ACCENT

f = Fig(680, 880,
        "Architecture block diagram. The third-party electronic health record node "
        "serves the clinical page to the consulting-room workstation over HTTPS, and "
        "sends clinical data directly to the AIMS Lab backend over a server-to-server "
        "channel. The page signals the aimscribe.exe tray daemon over a loopback "
        "channel confined to the same machine. Audio travels only from the workstation "
        "to the backend, and never towards the EHR node.")

# --- EHR node
f.rect(150, 34, 350, 78, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(150, 26, "THIRD-PARTY EHR NODE", size=11, bold=True)
f.box(168, 50, 314, 48, [("CMED · Aalo · Amader Susastho", 11, True),
                         ("one interface contract, three vendors", 9)])

# --- workstation
f.rect(20, 150, 565, 386, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(20, 142, "CONSULTING-ROOM WORKSTATION", size=11, bold=True)
f.box(36, 176, 250, 56, [("Microphone array", 11, True),
                         ("fixed placement, no processing", 8.5)])
f.box(318, 176, 250, 56, [("EHR page in browser", 11, True),
                          ("dispatches the trigger", 9)])
f.rect(36, 262, 532, 256, rx=6, sw=1.8)
f.text(302, 282, "aimscribe.exe — tray daemon", size=11.5, bold=True, anchor="middle")
f.box(54, 294, 496, 34, [("Acquisition · linear PCM at native rate", 10)])
f.box(54, 338, 496, 34, [("Segmentation · adaptive noise floor", 10)])
f.box(54, 382, 496, 34, [("Encrypted buffer · AES-256-GCM", 10)])
f.box(54, 426, 496, 34, [("Hash chain · Ed25519, per session", 10)])
f.box(54, 470, 496, 34, [("Asynchronous transport", 10)])

f.path("M302,112 L302,170")
f.text(312, 136, "HTTPS page delivery", size=9)
f.path("M443,232 L443,256", color=ACCENT, sw=2.2)
f.text(453, 248, "Channel A", size=9, bold=True, color=ACCENT)
f.path("M161,232 L161,288")
f.text(171, 256, "analogue audio", size=9)
for y in (328, 372, 416, 460):
    f.path(f"M302,{y} L302,{y+10}")

# --- backend
f.rect(20, 594, 565, 258, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(20, 586, "AIMS LAB BACKEND", size=11, bold=True)
f.box(36, 620, 250, 52, [("API", 11, True), ("authorisation · verification", 9)])
f.box(318, 620, 250, 52, [("Clinical store", 11, True), ("prescriptions · notes", 9)])
f.box(36, 700, 250, 52, [("Object store", 11, True), ("sealed segments", 9)])
f.box(318, 700, 250, 52, [("Archive", 11, True), ("verified recordings", 9)])
f.box(36, 780, 532, 46, [("Server-side verification", 10.5, True),
                         ("every segment re-read and re-hashed before acceptance", 8.5)])
f.path("M161,672 L161,694")
f.path("M443,672 L443,694")
f.path("M161,752 L161,774")
f.path("M443,752 L443,774")

# --- audio upload
f.path("M302,518 L302,614", color=ACCENT, sw=2.4)
f.text(312, 552, "audio, encrypted", size=9, color=ACCENT)
f.text(312, 566, "TLS · device token", size=9, color=ACCENT)

# --- Channel B, down the reserved corridor
f.path("M500,73 L640,73 L640,646 L592,646", color=ACCENT, sw=2.4)
f.text(590, 100, "Channel B", size=8.5, bold=True, color=ACCENT)
f.text(590, 113, "clinical", size=8.5, color=ACCENT)
f.text(590, 126, "data", size=8.5, color=ACCENT)

f.text(20, 872, "Accented pathways are encrypted and mutually authenticated. "
                "Audio never travels towards the EHR node.", size=9, color=ACCENT)
f.write("ms_fig1_architecture.svg")
