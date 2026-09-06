"""
Manuscript figures 1 and 2, drawn for print rather than for a screen.

A figure reproduced at a 170 mm text width scales by (170 / canvas width) mm per
unit. At the 1,100-unit widths used elsewhere in this project, 10-unit label text
lands at roughly 4 pt on the page, which no journal accepts and no reviewer can
read. Holding the canvas near 660 units puts the same labels at about 7.5 pt.
The constraint is therefore on layout density, not on font size: fewer elements
per row, stacked vertically, with shorter labels.
"""
from genfigs import Fig, ACCENT

# ============================ Figure 1 - architecture block diagram
f = Fig(660, 880,
        "Architecture block diagram. The third-party electronic health record node "
        "serves the clinical page to the consulting-room workstation over HTTPS. That "
        "page signals the aimscribe.exe tray daemon over a loopback channel confined "
        "to the same machine. Encrypted, mutually authenticated pathways carry sealed "
        "audio and control traffic to the AIMS Lab backend. No network path exists "
        "between the EHR node and the backend.")

# --- EHR node
f.rect(150, 34, 360, 78, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(150, 26, "THIRD-PARTY EHR NODE", size=11, bold=True)
f.box(168, 50, 324, 48, [("CMED · Aalo · Amader Susastho", 11, True),
                         ("one interface contract, three vendors", 9)])

# --- workstation
f.rect(20, 150, 620, 386, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(20, 142, "CONSULTING-ROOM WORKSTATION", size=11, bold=True)
f.box(40, 176, 268, 56, [("Microphone array", 11, True),
                         ("fixed placement, no vendor processing", 8.5)])
f.box(352, 176, 268, 56, [("EHR page in browser", 11, True),
                          ("dispatches the trigger", 9)])
f.rect(40, 262, 580, 256, rx=6, sw=1.8)
f.text(330, 282, "aimscribe.exe — tray daemon", size=11.5, bold=True, anchor="middle")
f.box(58, 294, 544, 34, [("Acquisition · linear PCM at native rate", 10)])
f.box(58, 338, 544, 34, [("Segmentation · adaptive noise floor", 10)])
f.box(58, 382, 544, 34, [("Encrypted spool · AES-256-GCM, 40 GB", 10)])
f.box(58, 426, 544, 34, [("Hash chain · Ed25519, per session", 10)])
f.box(58, 470, 544, 34, [("Asynchronous transport", 10)])

f.path("M330,112 L330,170")
f.text(340, 136, "HTTPS page delivery", size=9)
f.path("M486,232 L486,256", color=ACCENT, sw=2.2)
f.text(496, 248, "loopback trigger", size=9, color=ACCENT)
f.path("M174,232 L174,288")
f.text(184, 256, "analogue audio", size=9)
for y in (328, 372, 416, 460):
    f.path(f"M330,{y} L330,{y+10}")

# --- backend
f.rect(20, 594, 620, 258, rx=8, sw=1.3, dash="5 4", op="0.55")
f.text(20, 586, "AIMS LAB BACKEND", size=11, bold=True)
f.box(40, 620, 268, 52, [("API", 11, True), ("authorisation · verification", 9)])
f.box(352, 620, 268, 52, [("Metadata store", 11, True), ("sessions · audit log", 9)])
f.box(40, 700, 268, 52, [("Object store", 11, True), ("sealed segments", 9)])
f.box(352, 700, 268, 52, [("Archive", 11, True), ("verified recordings", 9)])
f.box(40, 780, 580, 46, [("Server-side verification", 10.5, True),
                         ("every segment re-read and re-hashed before acceptance", 8.5)])
f.path("M308,646 L346,646")
f.path("M174,672 L174,694")
f.path("M308,726 L346,726")
f.path("M174,752 L174,774")
f.path("M486,752 L486,774")

# encrypted pathway from the workstation to the backend
f.path("M330,518 L330,614", color=ACCENT, sw=2.4)
f.text(340, 560, "TLS · device token", size=9, color=ACCENT)
f.text(340, 574, "sealed payload", size=9, color=ACCENT)

# the absent path
f.path("M510,73 L572,73", dash="4 5", arrow=False, sw=1.3)
f.path("M580,63 L600,83", color=ACCENT, sw=2.2, arrow=False)
f.path("M600,63 L580,83", color=ACCENT, sw=2.2, arrow=False)
f.text(515, 96, "no path exists between", size=9, bold=True, color=ACCENT)
f.text(515, 109, "the EHR node and backend", size=9, color=ACCENT)

f.text(20, 872, "Accented pathways are encrypted and mutually authenticated.",
       size=9, color=ACCENT)
f.write("ms_fig1_architecture.svg")


# ============================ Figure 2 - UML sequence diagram
f = Fig(660, 900,
        "Sequence diagram of the acquisition pathway. Selection of patient details "
        "dispatches a trigger to the local daemon. Acquisition begins immediately "
        "while authorisation is validated by the backend in parallel. Segments are "
        "sealed, uploaded and verified by server-side re-hashing throughout. Local "
        "material is released for deletion only against a purge receipt.")

L = [(110, "EHR page"), (330, "aimscribe.exe"), (550, "AIMS Lab backend")]
for x, n in L:
    f.box(x - 95, 44, 190, 32, [(n, 10.5, True)])
    f.parts.append(f'<line x1="{x}" y1="76" x2="{x}" y2="866" stroke="currentColor" '
                   f'stroke-width="1" stroke-dasharray="3 4" opacity="0.5"/>')
f.text(20, 26, "Clinician selects patient details in the record system",
       size=9.5, italic=True)
f.path("M110,30 L110,40", sw=1.3)


def m(y, a, b, t, accent=False, bold=False):
    x0, x1 = L[a][0], L[b][0]
    d = 5 if x1 > x0 else -5
    c = ACCENT if accent else "currentColor"
    f.path(f"M{x0+d},{y} L{x1-d},{y}", color=c, sw=1.9 if accent else 1.4)
    f.label((x0 + x1) / 2, y - 6, t, size=9, bold=bold, color=c,
            slot=(min(x0, x1) + 3, max(x0, x1) - 3))


def act(y, i, t, sub=None, accent=False):
    x = L[i][0]
    lines = [(t, 9.5, True, ACCENT if accent else "currentColor")]
    if sub:
        lines.append((sub, 8.5, False, "currentColor"))
    f.box(x - 100, y, 200, 26 if not sub else 36, lines,
          color=ACCENT if accent else "currentColor", sw=1.6 if accent else 1.3)


m(106, 0, 1, "1 · trigger: patient, doctor, clinic", accent=True, bold=True)

f.rect(214, 126, 436, 190, rx=5, sw=1.1, dash="4 4", op="0.7")
f.text(224, 141, "par — capture is not deferred to authorisation", size=8.5,
       italic=True)
act(152, 1, "2 · acquisition begins (t = 0)", accent=True)
m(212, 1, 2, "3 · request authorisation")
act(228, 2, "4 · validate device, clinic,", sub="clinician and consent")
m(300, 2, 1, "5 · signed authorisation, 60 s")

m(348, 1, 2, "6 · open session + chain entry 0")

f.rect(214, 376, 436, 174, rx=5, sw=1.1, dash="4 4", op="0.7")
f.text(224, 391, "loop — every 30 to 60 s until the encounter ends", size=8.5,
       italic=True)
act(402, 1, "7 · seal segment (AES-256-GCM)")
m(462, 1, 2, "8 · upload over TLS + digest")
act(478, 2, "9 · re-read and re-hash to verify")

m(586, 0, 1, "10 · encounter concluded", accent=True, bold=True)
m(626, 1, 2, "11 · close session + chain tail")
act(642, 2, "12 · verify the whole chain")
m(702, 2, 1, "13 · purge receipt", accent=True)
act(718, 1, "14 · delete local copy", sub="after a 24 h grace window", accent=True)

f.text(20, 806, "Acquisition, authorisation and transmission proceed concurrently;",
       size=9)
f.text(20, 820, "no step in the pathway blocks the consultation in progress.", size=9)
f.text(20, 848, "Local material is released for deletion only at step 13.",
       size=9.5, bold=True, color=ACCENT)
f.write("ms_fig2_sequence.svg")
