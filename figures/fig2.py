"""Figure 2 - life of a consultation."""
from genfigs import Fig, ACCENT

W, H = 1140, 1090
f = Fig(W, H,
        "Life of a consultation. The partner page sends a trigger; the microphone opens "
        "immediately while authorisation proceeds in parallel. Segments are sealed, "
        "uploaded and verified by server-side read-back every thirty to sixty seconds. A "
        "prescription-built flag arms the gate; until it arrives a stray trigger is "
        "refused and the recording continues. Once armed the next trigger closes one "
        "session and opens the next with no gap. Local audio is deleted only after the "
        "chain verifies and purge receipts are issued.")

LANES = [(140, "Partner page"), (430, "AIMScribe agent"),
         (740, "AIMS LAB backend"), (1010, "Archive")]

for x, name in LANES:
    f.box(x - 105, 24, 210, 40, [(name, 12.5, True)])
    f.parts.append(f'<line x1="{x}" y1="64" x2="{x}" y2="{H-24}" stroke="currentColor" '
                   f'stroke-width="1" stroke-dasharray="3 4" opacity="0.5"/>')


def msg(y, a, b, text, *, accent=False, dash=None, size=10.5, bold=False):
    x0, x1 = LANES[a][0], LANES[b][0]
    d = 6 if x1 > x0 else -6
    col = ACCENT if accent else "currentColor"
    f.path(f"M{x0+d},{y} L{x1-d},{y}", color=col, sw=2 if accent else 1.5, dash=dash)
    f.label((x0 + x1) / 2, y - 7, text, size=size, bold=bold, color=col,
            slot=(min(x0, x1) + 4, max(x0, x1) - 4))


def selfact(y, lane, text, *, accent=False, size=10.5, sub=None):
    x = LANES[lane][0]
    lines = [(text, size, True, ACCENT if accent else "currentColor")]
    if sub:
        lines.append((sub, 9.5, False, "currentColor"))
    f.box(x - 122, y, 244, 30 if not sub else 40, lines,
          color=ACCENT if accent else "currentColor", sw=1.8 if accent else 1.4)


def band(y0, y1, note):
    f.rect(300, y0, 560, y1 - y0, rx=6, sw=1.2, dash="5 4", op="0.7")
    f.text(312, y0 + 15, note, size=9.5, italic=True)


# --- opening: capture and authorisation in parallel ---------------------
msg(104, 0, 1, "1 · trigger — 5 fields", bold=True)
band(120, 300, "capture and authorisation run in parallel — a slow link never costs "
                "the opening seconds")
selfact(148, 1, "2 · microphone opens — t = 0")
msg(196, 1, 2, "3 · mint grant (device token)")
selfact(212, 2, "4 · check doctor · clinic · device")
msg(272, 2, 1, "5 · signed grant · 60 s · single use")

msg(324, 1, 2, "6 · session/open + chain entry 0")
msg(360, 2, 1, "7 · session_id (ULID)")
msg(396, 1, 0, "8 · 200 RECORDING_STARTED", bold=True)

# --- the segment loop ----------------------------------------------------
band(420, 600, "repeats every 30–60 s until the consultation ends")
msg(456, 1, 2, "9 · segment/authorize")
msg(492, 1, 2, "10 · PUT encrypted segment")
msg(528, 1, 2, "11 · commit + declared SHA-256")
selfact(552, 2, "12 · read back · re-hash · compare")

# --- the gate ------------------------------------------------------------
msg(636, 0, 1, "13 · consultation_complete", accent=True, bold=True)
selfact(652, 1, "14 · GATE ARMED", accent=True)
msg(716, 0, 1, "15a · trigger while gate NOT armed", accent=True)
msg(748, 1, 0, "409 GATE_NOT_ARMED — recording continues", accent=True, dash="5 3")
msg(792, 0, 1, "15b · trigger, gate armed", accent=True, bold=True)
selfact(808, 1, "16 · close N, open N+1", sub="parallel threads — no gap in capture")

# --- close, verify, purge ------------------------------------------------
msg(878, 1, 2, "17 · session/close + chain tail")
selfact(894, 2, "18 · verify the whole chain")
msg(954, 2, 1, "19 · purge receipts")
selfact(970, 1, "20 · delete local audio", sub="only now, after a 24 h grace window")

msg(1040, 2, 3, "21 · verified session")
f.box(888, 1056, 244, 32, [("22 · concatenate · verify · file", 10.5, True)])

f.write("fig2_consultation_flow.svg")
