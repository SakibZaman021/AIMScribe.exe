"""
Manuscript Figure 2 - sequence diagram, with trigger corroboration.

Opening a patient now sends two messages from the EHR node: the trigger to the
daemon (1a) and a corroborating notice to the backend (1b). The notice crosses
the daemon's lifeline, which is conventional in UML sequence diagrams; its label
sits to the left of the crossing so it never lies on the lifeline.
"""
from genfigs import Fig, ACCENT

f = Fig(660, 900,
        "Sequence diagram of the acquisition pathway. Opening a patient sends a "
        "trigger to the local daemon and, at the same moment, a corroborating notice "
        "from the EHR server to the backend. Acquisition begins immediately; the "
        "backend authorises the recording only if the daemon's request matches the "
        "notice exactly. Segments are sealed, uploaded and verified throughout, and "
        "local material is deleted on the purge receipt.")

L = [(110, "EHR node"), (330, "aimscribe.exe"), (550, "AIMS Lab backend")]
for x, n in L:
    f.box(x - 95, 44, 190, 32, [(n, 10.5, True)])
    f.parts.append(f'<line x1="{x}" y1="76" x2="{x}" y2="800" stroke="currentColor" '
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


# --- the two simultaneous messages
m(106, 0, 1, "1a · trigger (loopback)", accent=True, bold=True)
f.path("M115,140 L545,140", color=ACCENT, sw=1.9)
f.text(122, 134, "1b · notice: same five fields", size=9, bold=True, color=ACCENT)

# --- parallel block
f.rect(214, 160, 436, 196, rx=5, sw=1.1, dash="4 4", op="0.7")
f.text(224, 175, "par — capture is not deferred to authorisation", size=8.5,
       italic=True)
act(186, 1, "2 · acquisition begins (t = 0)", accent=True)
m(246, 1, 2, "3 · request authorisation")
act(262, 2, "4 · match notice exactly;", sub="check device and clinic")
m(334, 2, 1, "5 · signed authorisation, 60 s")

m(384, 1, 2, "6 · open session + chain entry 0")

# --- segment loop
f.rect(214, 410, 436, 170, rx=5, sw=1.1, dash="4 4", op="0.7")
f.text(224, 425, "loop — every 30 to 60 s until the encounter ends", size=8.5,
       italic=True)
act(436, 1, "7 · seal segment (AES-256-GCM)")
m(496, 1, 2, "8 · upload over TLS + digest")
act(512, 2, "9 · re-read and re-hash to verify")

# --- close
m(614, 0, 1, "10 · encounter concluded", accent=True, bold=True)
m(652, 1, 2, "11 · close session + chain tail")
act(668, 2, "12 · verify the whole chain")
m(726, 2, 1, "13 · purge receipt", accent=True)
act(742, 1, "14 · delete local copy", sub="immediately on receipt", accent=True)

# --- notes, below the lifelines
f.text(20, 832, "1a and 1b are sent together. Authorisation needs the request to "
                "match 1b; acquisition waits for neither.", size=9)
f.text(20, 848, "A request with no matching notice keeps recording, and is withheld "
                "from the dataset as unconfirmed.", size=9)
f.text(20, 878, "Local material is deleted only on the purge receipt (step 13).",
       size=9.5, bold=True, color=ACCENT)
f.write("ms_fig2_sequence.svg")
